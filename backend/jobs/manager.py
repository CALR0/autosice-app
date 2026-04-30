"""Job manager helpers: create job dirs, save/load meta, enqueue helper.

These are lightweight helpers used by the API to create job folders and
manage metadata. We'll gradually move logic from `app.py` here.
"""
from pathlib import Path
import json
import os
import time


JOBS_DIR = Path(os.getenv('JOBS_DIR', './jobs')).resolve()
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def job_dir(job_id: str) -> Path:
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def job_meta_path(job_id: str) -> Path:
    return job_dir(job_id) / 'meta.json'


def job_input_path(job_id: str) -> Path:
    return job_dir(job_id) / 'input.xlsx'


def job_output_path(job_id: str) -> Path:
    return job_dir(job_id) / 'output.xlsx'


def save_job_meta(job_id: str, meta: dict):
    p = job_meta_path(job_id)
    tmp = str(p) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f)
    try:
        os.replace(tmp, str(p))
    except Exception:
        try:
            os.remove(str(p))
            os.replace(tmp, str(p))
        except Exception:
            pass


def save_job_meta_path(path: str, meta: dict):
    """Save meta to an explicit file path using atomic replace semantics."""
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f)
    try:
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.remove(str(path))
            os.replace(tmp, str(path))
        except Exception:
            pass


def load_job_meta(job_id: str):
    p = job_meta_path(job_id)
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None
