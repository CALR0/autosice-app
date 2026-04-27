from flask import Flask, render_template, request, send_file, make_response
import os
import threading
import time
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

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/procesar", methods=["POST"])
def procesar():
    # Lazy import to avoid heavy startup cost (Playwright, pandas, etc.). If
    # the import fails, return a 500 so health checks still respond quickly.
    try:
        from procesador import procesar_excel
    except Exception:
        return "Error: backend not ready (failed to import processing module)", 500

    file = request.files.get("file")
    if file is None:
        return "Error: no file uploaded", 400

    # Use a temporary directory so uploaded input is not persisted in the backend folder
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.xlsx")
        output_path = os.path.join(tmpdir, "output.xlsx")

        # Guardar archivo temporalmente
        file.save(input_path)

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


    @app.route("/health", methods=["GET"])
    def health():
        """Lightweight health endpoint.

        This endpoint is intentionally minimal: it does not import or start
        Playwright or other heavy dependencies and returns quickly so uptime
        pingers keep the free Render instance awake.
        """
        return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True)