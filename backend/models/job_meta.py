"""Dataclass-like helpers for job meta.json structure."""
from dataclasses import dataclass, asdict
import json
import time
import os


@dataclass
class JobMeta:
    status: str = 'queued'
    created_at: float = None
    total_rows: int = None
    rows_processed: int = 0
    rows_errors: int = 0
    error: str = None
    started_at: float = None
    finished_at: float = None

    def to_dict(self):
        d = asdict(self)
        # remove None values for compactness
        return {k: v for k, v in d.items() if v is not None}


def save_meta(path: str, meta: JobMeta):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta.to_dict(), f)
    try:
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(path)
            os.replace(tmp, path)
        except Exception:
            pass
