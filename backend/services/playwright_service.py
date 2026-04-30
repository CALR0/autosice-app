"""Lightweight Playwright helpers used by the processor.

This module provides a small, dependency-light set of helpers that the
processing implementation expects. It intentionally avoids heavy
assumptions about the environment and logs via `log_debug` when available.
"""

import json
import time
import traceback


def _safe_log(log_debug, *args):
    try:
        if log_debug:
            log_debug(*args)
    except Exception:
        try:
            print('[playwright_service]', *args)
        except Exception:
            pass


def setup_resource_blocking(page, fast_processing=False):
    """Block non-critical resources when `fast_processing` is truthy.

    Blocks images, media, fonts and stylesheets to reduce bandwidth and
    speed up navigation. It's a best-effort helper and will silently
    continue if Playwright's route API isn't available.
    """
    if not fast_processing:
        return
    try:
        def handler(route):
            try:
                res_type = route.request.resource_type
                if res_type in ("image", "media", "font", "stylesheet"):
                    route.abort()
                else:
                    route.continue_()
            except Exception:
                try:
                    route.continue_()
                except Exception:
                    pass

        page.route("**/*", lambda route: handler(route))
    except Exception:
        # Not fatal
        pass


def esperar_select(page, selector, timeout=5.0):
    """Wait until a <select> element exists and has at least one <option>.

    Returns True if ready, False on timeout.
    """
    try:
        deadline = time.time() + float(timeout)
        while time.time() < deadline:
            try:
                el = page.query_selector(selector)
                if el:
                    opts = page.query_selector_all(f"{selector} option")
                    if opts and len(opts) > 0:
                        return True
            except Exception:
                pass
            time.sleep(0.1)
    except Exception:
        pass
    return False


def esperar_postback(page, wait_time=0.5, fast_processing=False):
    """Simple wait helper used after selections that cause postbacks.

    This function favors a short sleep and returns; used as a fallback in
    environments where request-watching is difficult.
    """
    try:
        time.sleep(wait_time)
    except Exception:
        pass


def wait_for_significant_response(page, timeout_ms=500):
    """Attempt to detect a significant network response.

    This is a heuristic: it returns True if at least one network
    response completes within the timeout. If Playwright network
    listeners are not available, returns False.
    """
    try:
        # Try a fast, non-invasive approach: poll performance entries.
        # This will work on most pages and is inexpensive.
        script = "() => (window.performance && window.performance.getEntriesByType) ? window.performance.getEntriesByType('resource').length : 0"
        before = page.evaluate(script)
        time.sleep(min(timeout_ms / 1000.0, 0.05))
        after = page.evaluate(script)
        return (after or 0) > (before or 0)
    except Exception:
        return False


def build_selector_map(page, selector, normalizar=None, log_debug_fn=None):
    """Build a mapping of normalized option text -> option.value for a select.

    Returns (mapping_dict, count). Normalization is delegated to the
    provided `normalizar` callable when available; otherwise a simple
    lowercasing/strip is used.
    """
    try:
        opts = page.query_selector_all(f"{selector} option")
        mapping = {}
        count = 0
        for o in opts:
            try:
                text = (o.inner_text() or "").strip()
                val = o.get_attribute("value") or ""
                if normalizar:
                    key = normalizar(text)
                else:
                    key = (text or "").lower().strip()
                if key:
                    mapping[key] = val
                count += 1
            except Exception:
                continue
        try:
            sample_keys = list(mapping.keys())[:10]
            _safe_log(log_debug_fn, f"build_selector_map: selector={selector} keys_sample={sample_keys} count={count}")
        except Exception:
            pass
        return mapping, count
    except Exception as e:
        _safe_log(log_debug_fn, f"build_selector_map failed for {selector}: {e}")
        return {}, 0


def inject_selector_map(page, selector, mapping):
    """Inject a mapping into the page under window.__selector_map for fast JS-side lookups."""
    try:
        # Ensure the global exists
        page.evaluate("() => { window.__selector_map = window.__selector_map || {}; }")
        # Set the mapping as a JSON-serializable object
        page.evaluate("(sel, mapping) => { window.__selector_map[sel] = mapping; }", selector, mapping)
    except Exception:
        pass


def select_option_via_page_map(page, selector, value):
    """Set a select's value using an already-known option value (fast path).

    Returns True on success, False otherwise.
    """
    try:
        # Use JS to set value and dispatch change event
        ok = page.evaluate(
            "(sel, val) => { try { const el = document.querySelector(sel); if(!el) return false; el.value = val; el.dispatchEvent(new Event('change',{bubbles:true})); return el.value === val; } catch(e) { return false } }",
            selector,
            value,
        )
        return bool(ok)
    except Exception:
        return False


def find_option_value_js(page, selector, valor):
    """Find an option value by normalizing option text in the page (JS-side).

    Returns the option.value string or None.
    """
    try:
        return page.evaluate(
            "(sel, target) => {\n                function normalizeText(s){ try{ return s.toString().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,'').replace(/[^a-z0-9\s]/g,'').replace(/\s+/g,' ').trim(); }catch(e){ return s.toString().toLowerCase().trim(); } }\n                try{ const el = document.querySelector(sel); if(!el) return null; const t = normalizeText(target||''); const opts = Array.from(el.options||[]); for(const o of opts){ const n = normalizeText(o.innerText||o.text||''); if(n===t) return o.value; } return null;}catch(e){ return null;}\n            }",
            selector,
            valor,
        )
    except Exception:
        try:
            return page.evaluate(
                "(sel, target) => { const el = document.querySelector(sel); if(!el) return null; const t = (target||'').toString().toLowerCase().trim(); for(const o of (el.options||[])){ if(((o.innerText||'').toString().toLowerCase().trim())===t) return o.value; } return null }",
                selector,
                valor,
            )
        except Exception:
            return None


def option_exists(page, selector, valor, selector_cache=None, normalizar=None, log_debug_fn=None):
    """Return True if an option likely exists for the provided text.

    This tries multiple strategies: cached map, JS-side exact normalized
    match, and finally a Python-side normalized lookup.
    """
    try:
        # 1) JS-side exact normalized search (fast and robust)
        try:
            v = find_option_value_js(page, selector, valor)
            if v is not None:
                return True
        except Exception:
            pass

        # 1.b) JS-side direct value match (some inputs are the option.value)
        try:
            js_val_match = page.evaluate(
                "(sel, target) => { const el = document.querySelector(sel); if(!el) return false; const t = (target||'').toString().toLowerCase().trim(); for(const o of (el.options||[])){ if((o.value||'').toString().toLowerCase().trim()===t) return true; } return false; }",
                selector,
                valor,
            )
            if js_val_match:
                return True
        except Exception:
            pass

        # 2) cached mapping
        if selector_cache and selector in selector_cache:
            try:
                mapping = selector_cache.get(selector, ({}, 0))[0]
                key = normalizar(valor) if normalizar else (valor or '').lower().strip()
                if key in mapping:
                    return True
            except Exception:
                pass

        # 3) Try matching option.value directly (some sheets provide the option value)
        try:
            opts = page.query_selector_all(f"{selector} option")
            vnorm = (valor or '').strip()
            if vnorm:
                for o in opts:
                    try:
                        ov = (o.get_attribute('value') or '').strip()
                        if ov and ov.lower() == vnorm.lower():
                            return True
                    except Exception:
                        continue
        except Exception:
            pass

        # 4) Python-side brute force: inspect DOM options by visible text
        try:
            opts = page.query_selector_all(f"{selector} option")
            k = normalizar(valor) if normalizar else (valor or '').lower().strip()
            for o in opts:
                try:
                    txt = (o.inner_text() or '').strip()
                    kn = normalizar(txt) if normalizar else txt.lower().strip()
                    if kn == k:
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        try:
            # collect diagnostics for debugging
            sample_keys = None
            try:
                if selector_cache and selector in selector_cache:
                    sample_keys = list(selector_cache.get(selector, ({}, 0))[0].keys())[:10]
            except Exception:
                sample_keys = None
            sample_values = None
            try:
                opts = page.query_selector_all(f"{selector} option")
                sample_values = []
                for o in opts[:10]:
                    try:
                        sample_values.append((o.get_attribute('value') or '', (o.inner_text() or '').strip()))
                    except Exception:
                        continue
            except Exception:
                sample_values = None

            # Also capture a JS-side snapshot: existence and first options
            try:
                snap = page.evaluate(
                    "(sel) => { const el = document.querySelector(sel); if(!el) return {exists: false}; const opts = Array.from(el.options||[]).map(o=>({v: o.value, t: (o.innerText||o.text||'').toString().trim()})); return {exists:true, count: opts.length, sample: opts.slice(0,10)} }",
                    selector,
                )
            except Exception:
                snap = None

            _safe_log(log_debug_fn, f"option_exists: selector={selector} value={valor} sample_keys={sample_keys} sample_values={sample_values} dom_snapshot={snap}")
        except Exception:
            pass
        return False
    except Exception:
        return False


def seleccionar_opcion(page, selector, valor_text, selector_cache=None, normalizar=None, log_debug_fn=None):
    """Select an option by visible text (tolerant).

    Tries JS-side exact normalized match first, then cached map, then
    falls back to brute-force matching by iterating options.
    """
    try:
        # JS-side exact match
        try:
            val = find_option_value_js(page, selector, valor_text)
            if val:
                return select_option_via_page_map(page, selector, val)
        except Exception:
            pass

        # cached mapping
        if selector_cache and selector in selector_cache:
            try:
                mapping = selector_cache.get(selector, ({}, 0))[0]
                key = normalizar(valor_text) if normalizar else (valor_text or '').lower().strip()
                val = mapping.get(key)
                if val:
                    if select_option_via_page_map(page, selector, val):
                        return True
            except Exception:
                pass

        # 3) Attempt to match by option.value directly (some sheets give values)
        try:
            opts = page.query_selector_all(f"{selector} option")
            vnorm = (valor_text or '').strip()
            if vnorm:
                for o in opts:
                    try:
                        ov = (o.get_attribute('value') or '').strip()
                        if ov and ov.lower() == vnorm.lower():
                            return select_option_via_page_map(page, selector, ov)
                    except Exception:
                        continue
        except Exception:
            pass

        # brute force
        try:
            opts = page.query_selector_all(f"{selector} option")
            k = normalizar(valor_text) if normalizar else (valor_text or '').lower().strip()
            for o in opts:
                try:
                    txt = (o.inner_text() or '').strip()
                    kn = normalizar(txt) if normalizar else txt.lower().strip()
                    if kn == k:
                        # get option value and select
                        v = o.get_attribute('value') or ''
                        return select_option_via_page_map(page, selector, v)
                except Exception:
                    continue
        except Exception:
            pass

        # last resort: try Playwright select by label
        try:
            page.select_option(selector, label=valor_text)
            return True
        except Exception:
            return False
    except Exception:
        return False
