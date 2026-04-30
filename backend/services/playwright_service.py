import time


def setup_resource_blocking(page, fast_processing=False):
    """If fast_processing enabled, block heavy resources and set tighter timeouts."""
    if not fast_processing:
        return

    blocked_resource_types = {"image", "media", "font", "stylesheet"}

    def _route_handler(route, request):
        try:
            rt = request.resource_type
            url = request.url
            if rt in blocked_resource_types or "google-analytics" in url or "doubleclick" in url:
                route.abort()
            else:
                route.continue_()
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass

    try:
        page.route("**/*", _route_handler)
    except Exception:
        # If routing fails (older Playwright versions), ignore silently
        pass

    try:
        page.set_default_navigation_timeout(30000)
        page.set_default_timeout(30000)
    except Exception:
        pass


def esperar_select(page, selector):
    page.wait_for_function(f"""
    () => {{
        const sel = document.querySelector("{selector}");
        return sel && sel.options.length > 1;
    }}
    """)


def esperar_postback(page, wait_time, fast_processing=False):
    try:
        if fast_processing:
            page.wait_for_load_state("networkidle", timeout=5000)
        else:
            page.wait_for_load_state("networkidle")
    except Exception:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=(2000 if fast_processing else 10000))
        except Exception:
            pass

    try:
        page.wait_for_timeout(int(wait_time * 1000))
    except Exception:
        try:
            time.sleep(wait_time)
        except Exception:
            pass


def wait_for_significant_response(page, timeout_ms=8000):
    try:
        page.wait_for_response(lambda r: (r.request.method in ("POST", "GET")) and (200 <= r.status < 300), timeout=timeout_ms)
        return True
    except Exception:
        return False


def build_selector_map(page, selector, normalizar, log_debug=None):
    t0 = time.time()
    try:
        items = page.evaluate(
            "(sel) => Array.from(document.querySelectorAll(sel + ' option')).map(o => ({t: o.innerText.trim(), v: o.value}))",
            selector,
        )
    except Exception:
        items = []

    mapping = {}
    for it in items:
        try:
            raw_text = it.get('t', '')
            opt_val = it.get('v', '')
            norm_full = normalizar(raw_text)
            # primary key: full normalized text
            if norm_full and norm_full not in mapping:
                mapping[norm_full] = opt_val

            # also index on first segment before dash/comma/paren to match 'Madrid - Cundinamarca' -> 'Madrid'
            try:
                import re as _re
                first_seg = _re.split(r'[-,/()]+', raw_text)[0]
                norm_first = normalizar(first_seg)
                if norm_first and norm_first not in mapping:
                    mapping[norm_first] = opt_val
            except Exception:
                pass

            # index on individual tokens (words) to match partial inputs like 'bogot' or 'bogota'
            try:
                for tok in norm_full.split():
                    if len(tok) > 2 and tok not in mapping:
                        mapping[tok] = opt_val
            except Exception:
                pass
            # also add variant stripping common abbreviations like 'd c' or 'dc'
            try:
                stripped = _re.sub(r"\b(d\.?\s*c\.?|dc)\b", "", norm_full).strip()
                if stripped and stripped not in mapping:
                    mapping[stripped] = opt_val
            except Exception:
                pass
        except Exception:
            continue
    cnt = len(items)
    if log_debug:
        try:
            log_debug(f"build_selector_map {selector}: options={cnt} time={time.time()-t0:.3f}s")
        except Exception:
            pass
    return mapping, cnt
 

def seleccionar_opcion(page, selector, valor_excel, selector_cache, normalizar, log_debug=None):
    """Select an option by normalized visible text, with caching and fallback matching."""
    esperar_select(page, selector)

    valor_norm = normalizar(valor_excel)

    mapping_entry = selector_cache.get(selector)
    if mapping_entry is None:
        mapping, cnt = build_selector_map(page, selector, normalizar, log_debug)
        selector_cache[selector] = (mapping, cnt)
    else:
        mapping = mapping_entry[0]

    value = mapping.get(valor_norm)
    if value:
        page.select_option(selector, value=value)
        if selector == "#dnn_ctr417_SiceTAC_ORIGEN":
            selector_cache.pop("#dnn_ctr417_SiceTAC_DESTINO", None)
        return

    mejor_val = None
    for texto_norm, val in mapping.items():
        try:
            if texto_norm == valor_norm:
                mejor_val = val
                break
            if valor_norm in texto_norm or texto_norm in valor_norm:
                mejor_val = val
        except Exception:
            continue

    if mejor_val:
        page.select_option(selector, value=mejor_val)
        if selector == "#dnn_ctr417_SiceTAC_ORIGEN":
            selector_cache.pop("#dnn_ctr417_SiceTAC_DESTINO", None)
        return

    raise Exception(f"No se encontró opción para: {valor_excel}")


def option_exists(page, selector, valor_excel, selector_cache, normalizar, log_debug=None):
    try:
        esperar_select(page, selector)
    except Exception:
        return False

    valor_norm = normalizar(valor_excel)

    mapping_entry = selector_cache.get(selector)
    if mapping_entry is None:
        mapping, cnt = build_selector_map(page, selector, normalizar, log_debug)
        selector_cache[selector] = (mapping, cnt)
    else:
        mapping = mapping_entry[0]

    return valor_norm in mapping
"""Playwright helpers: browser/page lifecycle and common waits.

This module will centralize Playwright setup (FAST_PROCESSING options,
route blocking) so `procesador` can be simplified later.
"""
from playwright.sync_api import sync_playwright


def launch_browser(headless=True, fast_processing=False):
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
    return p, browser
