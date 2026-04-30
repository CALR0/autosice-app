"""Configuration helpers for backend (env-based)."""
import os


def get_env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


MAX_UPLOAD_BYTES = get_env_int('MAX_UPLOAD_BYTES', 5 * 1024 * 1024)
JOBS_DIR = os.getenv('JOBS_DIR', './jobs')

# Playwright / processing flags
FAST_PROCESSING = os.getenv('FAST_PROCESSING', '0') == '1'
WAIT_TIME = float(os.getenv('WAIT_TIME', '0.35')) if FAST_PROCESSING else float(os.getenv('WAIT_TIME', '1'))
DEFAULT_CHECKPOINT_FAST = 10
CHECKPOINT_EVERY = get_env_int('CHECKPOINT_EVERY', DEFAULT_CHECKPOINT_FAST if FAST_PROCESSING else 1)
PREBUILD_SELECTS = os.getenv('PREBUILD_SELECTS', '')

# Target URL for processing (kept configurable for tests)
URL = os.getenv('TARGET_URL', 'https://plc.mintransporte.gov.co/runtime/empresa/ctl/sicetac/mid/417')
