"""HTTP route definitions (skeleton).

We will move the existing endpoints from `app.py` into this module in later steps.
For now these are lightweight placeholders to keep the structure clear.
"""
from flask import Blueprint, request, make_response, send_file, jsonify
import tempfile
import io
import os
import time
import uuid
import shutil
import threading

from config import MAX_UPLOAD_BYTES
from jobs.manager import job_dir as _job_dir, job_meta_path as _job_meta_path, job_input_path as _job_input_path, job_output_path as _job_output_path, save_job_meta, load_job_meta

bp = Blueprint('api_routes', __name__)


@bp.route('/health', methods=['GET'])
def health():
    return {"status": "ok"}, 200


@bp.route('/ready', methods=['GET'])
def ready():
    try:
        import importlib
        importlib.import_module('processors.impl')
        return {"status": "ready"}, 200
    except Exception as e:
        return {"status": "not ready", "error": str(e)}, 500


@bp.route('/procesar', methods=['POST'])
def procesar():
    try:
        from processors.procesador import procesar_excel
    except Exception:
        return "Error: backend not ready (failed to import processing module)", 500

    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return "Error: file too large", 413

    file = request.files.get('file')
    if file is None:
        return "Error: no file uploaded", 400

    filename = (file.filename or '').lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
        return "Error: only Excel files are allowed (.xlsx, .xls)", 400

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input.xlsx')
        output_path = os.path.join(tmpdir, 'output.xlsx')
        file.save(input_path)
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
            processed, errors = procesar_excel(input_path, output_path)
            with open(output_path, 'rb') as f:
                data = f.read()
            bio = io.BytesIO(data)
            bio.seek(0)
            response = make_response(send_file(bio, as_attachment=True, download_name='resultado.xlsx'))
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
            try:
                response.headers['Access-Control-Expose-Headers'] = 'X-Rows-Processed, X-Rows-Errors, X-Processing-Status'
            except Exception:
                pass
            return response
        except Exception as e:
            return f"Error: {str(e)}", 500


@bp.route('/enqueue', methods=['POST'])
def enqueue():
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return {"error": "file too large"}, 413
    file = request.files.get('file')
    if file is None:
        return {"error": "no file uploaded"}, 400
    filename = (file.filename or '').lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
        return {"error": "only Excel files are allowed (.xlsx, .xls)"}, 400

    job_id = uuid.uuid4().hex
    d = _job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    inp = _job_input_path(job_id)
    file.save(str(inp))
    try:
        if inp.exists() and inp.stat().st_size > MAX_UPLOAD_BYTES:
            try:
                shutil.rmtree(str(d))
            except Exception:
                pass
            return {"error": "file too large"}, 413
    except Exception:
        pass

    total_rows = None
    try:
        from services.excel import count_data_rows
        total_rows = int(count_data_rows(str(inp)))
    except Exception:
        total_rows = None

    meta = {"status": "queued", "created_at": time.time(), "total_rows": total_rows, "rows_processed": 0, "rows_errors": 0}
    save_job_meta(job_id, meta)

    try:
        from jobs.worker import start_job_worker
        import processors
        start_job_worker(job_id, processors.procesar_excel)
    except Exception:
        def _fallback_runner(jid):
            meta = {"status": "running", "started_at": time.time(), "error": None}
            save_job_meta(jid, meta)
            try:
                from processors.procesador import procesar_excel
                inp = str(_job_input_path(jid))
                out = str(_job_output_path(jid))
                meta_path = str(_job_meta_path(jid))
                processed, errors = procesar_excel(inp, out, job_meta_path=meta_path)

                meta["status"] = "finished"
                meta["finished_at"] = time.time()
                meta["rows_processed"] = int(processed)
                meta["rows_errors"] = int(errors)
                save_job_meta(jid, meta)
            except Exception as e:
                meta["status"] = "error"
                meta["error"] = str(e)
                meta["finished_at"] = time.time()
                save_job_meta(jid, meta)

        t = threading.Thread(target=_fallback_runner, args=(job_id,), daemon=True)
        t.start()

    return {"job_id": job_id, "status_url": f"/job/{job_id}/status", "download_url": f"/job/{job_id}/download", "total_rows": total_rows}, 202


@bp.route('/job/<job_id>/status', methods=['GET'])
def job_status(job_id):
    meta = load_job_meta(job_id)
    if not meta:
        return {"error": "job not found"}, 404
    return meta


@bp.route('/job/<job_id>/download', methods=['GET'])
def job_download(job_id):
    out = _job_output_path(job_id)
    if not out.exists():
        return {"error": "result not ready"}, 404
    return send_file(str(out), as_attachment=True, download_name=f"resultado_{job_id}.xlsx")
