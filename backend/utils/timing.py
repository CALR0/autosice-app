"""Timing / debug logging helpers."""
import os


def log_debug(*args):
    if os.getenv('DEBUG_TIMINGS', '0') == '1':
        try:
            print('[timing]', *args)
        except Exception:
            pass
