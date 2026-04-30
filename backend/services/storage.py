"""Storage helpers: atomic file writes and path utilities."""
import os


def atomic_write(path: str, data: bytes):
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    try:
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(path)
            os.replace(tmp, path)
        except Exception:
            pass
