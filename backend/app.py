from flask import Flask, render_template, request, send_file, make_response
import os
import threading
import time
import uuid
import json
from pathlib import Path
import shutil
from flask_cors import CORS
# Note: Do NOT import the heavy `procesador` module at top-level. We import
# it lazily inside the `/procesar` handler so lightweight endpoints (like
# `/health`) start immediately without loading Playwright/pandas.
import tempfile
import io

app = Flask(__name__)
cors = CORS(app)

# Start an optional external pinger if PING_URL is set in the environment.
# This pings the provided URL periodically (default every 5 minutes) so
# external uptime monitors aren't required. The pinger is silent and
# non-blocking (daemon thread). It only runs if `PING_URL` is configured.
def _pinger_loop(url, interval_s):
    try:
        import requests
    except Exception:
        print("[pinger] requests not available; pinger disabled")
        return

    while True:
        try:
            requests.get(url, timeout=10)
        except Exception as e:
            # Don't raise — just log and continue
            print(f"[pinger] error pinging {url}: {e}")
        time.sleep(interval_s)


def start_pinger_if_configured():
    url = os.getenv("PING_URL")
    if not url:
        return
    try:
        interval_min = int(os.getenv("PING_INTERVAL_MIN", "5"))
    except Exception:
        interval_min = 5
    interval_s = max(30, interval_min * 60)
    t = threading.Thread(target=_pinger_loop, args=(url, interval_s), daemon=True)
    t.start()
    print(f"[pinger] started pinging {url} every {interval_s} seconds")


# Kick off the pinger (no-op if PING_URL not set)
start_pinger_if_configured()

UPLOAD_FOLDER = "."

# Jobs directory for async processing (enqueue -> worker thread)
JOBS_DIR = Path(os.getenv("JOBS_DIR", "./jobs")).resolve()
JOBS_DIR.mkdir(parents=True, exist_ok=True)

def _job_meta_path(job_id: str) -> Path:
    return JOBS_DIR / job_id / "meta.json"

def _job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id

def save_job_meta(job_id: str, meta: dict):
    d = _job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    with open(_job_meta_path(job_id), "w", encoding="utf-8") as f:
        json.dump(meta, f)

def load_job_meta(job_id: str):
    try:
        with open(_job_meta_path(job_id), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _job_input_path(job_id: str) -> Path:
    return _job_dir(job_id) / "input.xlsx"

def _job_output_path(job_id: str) -> Path:
    return _job_dir(job_id) / "output.xlsx"

def _process_job_async(job_id: str):
    """Background worker that processes a saved input file and writes output.

    This runs in a daemon thread. It updates job meta with status and errors.
    """
    meta = {"status": "running", "started_at": time.time(), "error": None}
    save_job_meta(job_id, meta)
    try:
        # Lazy import (may be heavy)
        from procesador import procesar_excel

        inp = str(_job_input_path(job_id))
        out = str(_job_output_path(job_id))
        meta_path = str(_job_meta_path(job_id))
        # Pass meta_path so the processor can update progress per-row
        processed, errors = procesar_excel(inp, out, job_meta_path=meta_path)

        meta["status"] = "finished"
        meta["finished_at"] = time.time()
        meta["rows_processed"] = int(processed)
        meta["rows_errors"] = int(errors)
        save_job_meta(job_id, meta)
    except Exception as e:
        meta["status"] = "error"
        meta["error"] = str(e)
        meta["finished_at"] = time.time()
        save_job_meta(job_id, meta)

# Maximum upload size for files (bytes). Default 5 MB.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))


@app.route("/")
def index():
    # Serve a minimal landing response from the backend. The full frontend is
    # expected to be served separately (Netlify). Returning a simple HTML
    # avoids TemplateNotFound errors when `templates/index.html` is missing.
    return (
        "<html><head><meta charset=\"utf-8\"><title>Autosice API</title></head>"
        "<body><h3>Autosice backend</h3><p>Use the <a href=\"/health\">/health</a> endpoint.</p></body></html>"
    )


@app.route("/procesar", methods=["POST"])
def procesar():
    # Lazy import to avoid heavy startup cost (Playwright, pandas, etc.). If
    # the import fails, return a 500 so health checks still respond quickly.
    try:
        from procesador import procesar_excel
    except Exception:
        return "Error: backend not ready (failed to import processing module)", 500

    # Basic upload validation: check content-length header first (fast),
    # then validate filename extension and finally check saved file size.
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return "Error: file too large", 413

    file = request.files.get("file")
    if file is None:
        return "Error: no file uploaded", 400

    filename = (file.filename or "").lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
        return "Error: only Excel files are allowed (.xlsx, .xls)", 400

    # Use a temporary directory so uploaded input is not persisted in the backend folder
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.xlsx")
        output_path = os.path.join(tmpdir, "output.xlsx")

        # Guardar archivo temporalmente
        file.save(input_path)

        # Check actual saved size; reject if larger than allowed
        try:
            if os.path.getsize(input_path) > MAX_UPLOAD_BYTES:
                try:
                    os.remove(input_path)
                except Exception:
                    pass
                return "Error: file too large", 413
        except Exception:
            pass

        try:
            # Ejecutar tu script y obtener cuántas filas se procesaron/errores
            processed, errors = procesar_excel(input_path, output_path)

            # Leer el archivo de salida en memoria y devolverlo sin dejar ficheros en disco
            with open(output_path, "rb") as f:
                data = f.read()

            bio = io.BytesIO(data)
            bio.seek(0)

            response = make_response(send_file(bio, as_attachment=True, download_name="resultado.xlsx"))

            try:
                response.headers['X-Rows-Processed'] = str(int(processed))
            except Exception:
                response.headers['X-Rows-Processed'] = '0'

            try:
                response.headers['X-Rows-Errors'] = str(int(errors))
            except Exception:
                response.headers['X-Rows-Errors'] = '0'

            try:
                response.headers['X-Processing-Status'] = 'partial' if errors and int(errors) > 0 else 'completed'
            except Exception:
                response.headers['X-Processing-Status'] = 'completed'

            # Expose headers for CORS
            try:
                response.headers['Access-Control-Expose-Headers'] = 'X-Rows-Processed, X-Rows-Errors, X-Processing-Status'
            except Exception:
                pass

            return response

        except Exception as e:
            return f"Error: {str(e)}", 500


@app.route("/enqueue", methods=["POST"])
def enqueue():
    """Enqueue an uploaded file for background processing.

    Returns a job id immediately. Check status at `/job/<id>/status` and
    download the result at `/job/<id>/download` when ready.
    """
    # quick content-length check
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return {"error": "file too large"}, 413

    file = request.files.get("file")
    if file is None:
        return {"error": "no file uploaded"}, 400

    filename = (file.filename or "").lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
        return {"error": "only Excel files are allowed (.xlsx, .xls)"}, 400

    job_id = uuid.uuid4().hex
    d = _job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    inp = _job_input_path(job_id)
    file.save(str(inp))

    # verify saved size and cleanup if too large
    try:
        if inp.exists() and inp.stat().st_size > MAX_UPLOAD_BYTES:
            # remove job dir
            try:
                shutil.rmtree(str(d))
            except Exception:
                pass
            return {"error": "file too large"}, 413
    except Exception:
        pass

    # attempt to detect total rows for progress reporting
    total_rows = None
    try:
        import pandas as pd
        df = pd.read_excel(str(inp))
        total_rows = int(df.shape[0])
    except Exception:
        total_rows = None

    meta = {"status": "queued", "created_at": time.time(), "total_rows": total_rows, "rows_processed": 0, "rows_errors": 0}
    save_job_meta(job_id, meta)

    t = threading.Thread(target=_process_job_async, args=(job_id,), daemon=True)
    t.start()

    return {"job_id": job_id, "status_url": f"/job/{job_id}/status", "download_url": f"/job/{job_id}/download"}, 202


@app.route("/job/<job_id>/status", methods=["GET"])
def job_status(job_id):
    meta = load_job_meta(job_id)
    if not meta:
        return {"error": "job not found"}, 404
    return meta


@app.route("/job/<job_id>/download", methods=["GET"])
def job_download(job_id):
    out = _job_output_path(job_id)
    if not out.exists():
        return {"error": "result not ready"}, 404
    return send_file(str(out), as_attachment=True, download_name=f"resultado_{job_id}.xlsx")


@app.route("/health", methods=["GET"])
def health():
    """Lightweight health endpoint.

    This endpoint is intentionally minimal: it does not import or start
    Playwright or other heavy dependencies and returns quickly so uptime
    pingers keep the free Render instance awake.
    """
    return {"status": "ok"}, 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness probe: attempt to import the heavy processing module.

    - Returns 200 when `procesador` can be imported (module available).
    - Returns 500 with the import error message otherwise.
    Note: calling this will trigger imports in `procesador` (Playwright/pandas).
    """
    try:
        import importlib
        importlib.import_module("procesador")
        return {"status": "ready"}, 200
    except Exception as e:
        return {"status": "not ready", "error": str(e)}, 500


if __name__ == "__main__":
    app.run(debug=True)