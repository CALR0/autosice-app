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

# Kick off the pinger (no-op if PING_URL not set). Delegated to services.pinger
from services.pinger import start_pinger_if_configured

# Kick off the pinger (no-op if PING_URL not set)
start_pinger_if_configured()

UPLOAD_FOLDER = "."

# Jobs directory for async processing (enqueue -> worker thread)
from jobs.manager import job_dir as _job_dir, job_meta_path as _job_meta_path, job_input_path as _job_input_path, job_output_path as _job_output_path, save_job_meta, load_job_meta

# Background worker execution is delegated to `jobs.worker.start_job_worker`.
# The worker module will import the heavy `procesador` module lazily and
# update job meta while processing.

# Maximum upload size for files (bytes). Default 5 MB.
from config import MAX_UPLOAD_BYTES

# Register API blueprint
from api.routes import bp as api_bp
app.register_blueprint(api_bp)


@app.route("/")
def index():
    # Serve a minimal landing response from the backend. The full frontend is
    # expected to be served separately (Netlify). Returning a simple HTML
    # avoids TemplateNotFound errors when `templates/index.html` is missing.
    return (
        "<html><head><meta charset=\"utf-8\"><title>Autosice API</title></head>"
        "<body><h3>Autosice backend</h3><p>Use the <a href=\"/health\">/health</a> endpoint.</p></body></html>"
    )



if __name__ == "__main__":
    app.run(debug=True)