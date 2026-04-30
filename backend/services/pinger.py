"""Optional external pinger to keep free-hosted instances warm.

Provides `start_pinger_if_configured()` which reads `PING_URL` and
`PING_INTERVAL_MIN` from the environment and starts a daemon thread.
"""
import os
import threading
import time


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
