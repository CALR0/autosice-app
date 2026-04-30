"""Worker runner: runs the processing function in a background thread.

This module will host `_process_job_async` equivalent. For now it's a
lightweight placeholder that other modules can call.
"""
import threading
import time
from .manager import job_input_path, job_output_path, job_meta_path, save_job_meta


def start_job_worker(job_id: str, target_fn):
    """Start a daemon thread that runs `target_fn(job_input, job_output, job_meta)`.

    `target_fn` should accept (input_path, output_path, job_meta_path).
    """
    inp = str(job_input_path(job_id))
    out = str(job_output_path(job_id))
    meta = str(job_meta_path(job_id))

    def runner():
        save_job_meta(job_id, {"status": "running", "started_at": time.time()})
        try:
            # target_fn is expected to write per-row meta and may return final counts
            result = None
            try:
                result = target_fn(inp, out, job_meta_path=meta)
            except TypeError:
                # Some implementations may accept positional args only
                result = target_fn(inp, out)

            # If the processor returned counts, persist them as final meta.
            final_meta = None
            if isinstance(result, (list, tuple)) and len(result) >= 2:
                try:
                    processed_count = int(result[0])
                    error_count = int(result[1])
                    final_meta = {
                        "status": "finished",
                        "finished_at": time.time(),
                        "rows_processed": processed_count,
                        "rows_errors": error_count,
                    }
                    save_job_meta(job_id, final_meta)
                except Exception:
                    final_meta = None

            # If processor didn't return final meta, ensure we at least set finished state
            m = load_meta_silent(meta)
            if not m or m.get('status') != 'finished':
                if final_meta is None:
                    save_job_meta(job_id, {"status": "finished", "finished_at": time.time()})
                else:
                    # final_meta already saved
                    pass
        except Exception as e:
            save_job_meta(job_id, {"status": "error", "error": str(e), "finished_at": time.time()})

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    return t


def load_meta_silent(path):
    try:
        import json
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None
