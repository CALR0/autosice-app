"""Request validation helpers for the API.

These functions perform lightweight checks (file extension, size). They are
intended to be used by the route handlers in `api.routes` or moved endpoints.
"""
from typing import Tuple

ALLOWED_EXT = ('.xlsx', '.xls')


def validate_extension(filename: str) -> bool:
    if not filename:
        return False
    return filename.lower().endswith(ALLOWED_EXT)


def validate_size(bytes_len: int, max_bytes: int) -> Tuple[bool, str]:
    if bytes_len is None:
        return False, 'no content-length'
    if bytes_len > max_bytes:
        return False, 'file too large'
    return True, ''
