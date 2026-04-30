# procesador.py

import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time
import os
import unicodedata
import os


def procesar_excel(INPUT_FILE, OUTPUT_FILE, job_meta_path=None):

    # ============================================================
    # CONFIGURACIÓN
    # ============================================================

    URL = "https://plc.mintransporte.gov.co/runtime/empresa/ctl/sicetac/mid/417"
    # If FAST_PROCESSING=1 in the environment, enable optimizations (resource blocking, shorter waits)
    FAST_PROCESSING = os.getenv("FAST_PROCESSING", "0") == "1"
    WAIT_TIME = float(os.getenv("WAIT_TIME", "0.35")) if FAST_PROCESSING else float(os.getenv("WAIT_TIME", "1"))
    # When FAST_PROCESSING is enabled, checkpoint (write Excel to disk) less frequently to avoid heavy I/O.
    # Default checkpoint every 10 rows in fast mode, or every row in normal mode (preserves previous behavior).
    DEFAULT_CHECKPOINT_FAST = 10
    CHECKPOINT_EVERY = int(os.getenv("CHECKPOINT_EVERY", str(DEFAULT_CHECKPOINT_FAST if FAST_PROCESSING else 1)))
    # Optional debug timings: set DEBUG_TIMINGS=1 in the environment to enable
    # lightweight per-row timing logs (prints to stdout). Default off.
    DEBUG_TIMINGS = os.getenv("DEBUG_TIMINGS", "0") == "1"

    def log_debug(*args):
        if DEBUG_TIMINGS:
            try:
                print("[timing]", *args)
            except Exception:
                pass


    # ============================================================
    # FUNCIONES INTERNAS
    # ============================================================

    def normalizar(texto):
        texto = str(texto).lower().strip()
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
        texto = re.sub(r'[^a-z0-9\s]', '', texto)
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()

    def resolver_captcha(texto):
        numeros = list(map(int, re.findall(r'\d+', texto)))
        return sum(numeros)

    def parse_number(value):
        """Try to parse a numeric value from various string formats. Returns float or None."""
        try:
            if value is None:
                return None
            s = str(value).strip()
            if s == "":
                return None
            # Remove currency symbols and spaces
            s_clean = re.sub(r"[^0-9.,-]", "", s)
            # Try common formats
            try:
                # Remove thousand separators like commas
                return float(s_clean.replace(',', ''))
            except Exception:
                try:
                    # Replace comma as decimal separator
                    return float(s_clean.replace('.', '').replace(',', '.'))
                except Exception:
                    return None
        except Exception:
            return None

    def esperar_select(page, selector):
        page.wait_for_function(f"""
        () => {{
            const sel = document.querySelector("{selector}");
            return sel && sel.options.length > 1;
        }}
        """)

    def esperar_postback(page):
        # Prefer a fast networkidle wait; if it times out, fall back to
        # domcontentloaded. Use Playwright's `wait_for_timeout` instead of
        # Python sleep so the event loop stays responsive.
        try:
            if FAST_PROCESSING:
                page.wait_for_load_state("networkidle", timeout=5000)
            else:
                page.wait_for_load_state("networkidle")
        except Exception:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=(2000 if FAST_PROCESSING else 10000))
            except Exception:
                pass

        try:
            # WAIT_TIME is in seconds; Playwright expects ms
            page.wait_for_timeout(int(WAIT_TIME * 1000))
        except Exception:
            # fallback to time.sleep if Playwright wait isn't available
            try:
                time.sleep(WAIT_TIME)
            except Exception:
                pass


    def wait_for_significant_response(page, timeout_ms=8000):
        """Try to wait for a likely significant XHR/Fetch response triggered by
        a recent select or click. Returns True if a response arrived, False
        otherwise. This is a heuristic; it falls back silently.
        """
        try:
            page.wait_for_response(lambda r: (r.request.method in ("POST", "GET")) and (200 <= r.status < 300), timeout=timeout_ms)
            return True
        except Exception:
            return False

    def seleccionar_opcion(page, selector, valor_excel):
        # Wait until the select is populated
        esperar_select(page, selector)

        valor_norm = normalizar(valor_excel)

        # Try to use cached mapping if available
        mapping_entry = selector_cache.get(selector)
        if mapping_entry is None:
            mapping = build_selector_map(selector)
        else:
            mapping = mapping_entry[0]

        value = mapping.get(valor_norm)
        if value:
            page.select_option(selector, value=value)
            # If selecting ORIGEN, invalidate DESTINO cache because it depends on origen
            if selector == "#dnn_ctr417_SiceTAC_ORIGEN":
                selector_cache.pop("#dnn_ctr417_SiceTAC_DESTINO", None)
            return
        # Fallback: fuzzy-match against cached mapping keys (cheap, no DOM calls).
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

        # If no match, raise a clear exception
        raise Exception(f"No se encontró opción para: {valor_excel}")

    def option_exists(page, selector, valor_excel):
        """Return True if the select at `selector` contains an option matching valor_excel (exact normalized match)."""
        try:
            esperar_select(page, selector)
        except Exception:
            return False

        valor_norm = normalizar(valor_excel)

        # Use cache if available
        mapping_entry = selector_cache.get(selector)
        if mapping_entry is None:
            mapping = build_selector_map(selector)
        else:
            mapping = mapping_entry[0]

        return valor_norm in mapping


    # ============================================================
    # CARGA DE ARCHIVOS
    # ============================================================

    df_input = pd.read_excel(INPUT_FILE)

    if os.path.exists(OUTPUT_FILE):
        df_output = pd.read_excel(OUTPUT_FILE)
    else:
        df_output = df_input.copy()
        df_output["ruta"] = ""
        df_output["costo_total"] = ""
        df_output["costo_km"] = ""
        df_output["costo_tonelada"] = ""
        df_output["costo_espera"] = ""
        df_output["resultado"] = ""


    # ============================================================
    # AUTOMATIZACIÓN
    # ============================================================

    with sync_playwright() as p:
        # launch browser; keep headless for production
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]) 
        page = browser.new_page()

        # selector options cache: selector -> (mapping(normalized_text->value), count)
        selector_cache = {}

        def build_selector_map(selector):
            """Build and cache a mapping normalized_text -> option value for a select.

            Use a single `page.evaluate` call to extract option texts/values in the
            browser context (faster than many Python<->page round-trips).
            """
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
                    mapping[normalizar(it.get('t', ''))] = it.get('v', '')
                except Exception:
                    continue
            cnt = len(items)
            selector_cache[selector] = (mapping, cnt)
            log_debug(f"build_selector_map {selector}: options={cnt} time={time.time()-t0:.3f}s")
            return mapping

        # If FAST_PROCESSING enabled, block heavy/irrelevant resources to speed up navigation
        if FAST_PROCESSING:
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

            page.route("**/*", _route_handler)
            # reduce some default timeouts to fail faster on slow calls
            page.set_default_navigation_timeout(30000)
            page.set_default_timeout(30000)
        page.goto(URL)

        # Optional: prebuild selector maps for selectors listed in PREBUILD_SELECTS
        # env var (comma-separated selectors). This is useful when selects are
        # large but stable and avoids building maps per-row.
        prebuild_raw = os.getenv("PREBUILD_SELECTS", "")
        if prebuild_raw:
            try:
                prebuild_list = [s.strip() for s in prebuild_raw.split(",") if s.strip()]
                for sel in prebuild_list:
                    try:
                        build_selector_map(sel)
                        log_debug(f"prebuilt selector: {sel}")
                    except Exception as e:
                        log_debug(f"prebuild failed for {sel}: {e}")
            except Exception:
                pass

        for i, row in df_output.iterrows():

            row_t0 = time.time()
            log_debug(f"start row {i}")

            if str(row.get("resultado", "")).strip() == "Completado con éxito":
                log_debug(f"skip row {i}: already completed")
                continue

            # Validar datos requeridos antes de intentar procesar la fila
            required_fields = ["configuracion", "condicion", "carroceria", "origen", "destino", "hora_cargue", "hora_descargue"]
            missing = [f for f in required_fields if pd.isna(row.get(f, None)) or str(row.get(f, "")).strip() == ""]
            if missing:
                df_output.at[i, "resultado"] = f"Faltan datos: {', '.join(missing)}"
                df_output.to_excel(OUTPUT_FILE, index=False)
                continue

            # Validar horas como enteros razonables
            try:
                hc = int(row["hora_cargue"])
                hd = int(row["hora_descargue"])
                if hc < 0 or hd < 0 or hc > 48 or hd > 48:
                    df_output.at[i, "resultado"] = f"Horas inválidas: hora_cargue={row['hora_cargue']} hora_descargue={row['hora_descargue']}"
                    df_output.to_excel(OUTPUT_FILE, index=False)
                    continue
            except Exception:
                df_output.at[i, "resultado"] = f"Horas inválidas: hora_cargue={row.get('hora_cargue')} hora_descargue={row.get('hora_descargue')}"
                df_output.to_excel(OUTPUT_FILE, index=False)
                continue

            # Reintentos en caso de fallo de página/red (máximo 40 segundos por fila)
            start_time = time.time()
            while True:
                try:
                    # CONFIGURACION: validar existencia por value o por texto normalizado
                    config_value = str(row["configuracion"]) if pd.notna(row["configuracion"]) else ""
                    opciones_conf = page.locator("#dnn_ctr417_SiceTAC_CONFIGURACION option")
                    found_conf = False
                    for j in range(opciones_conf.count()):
                        # check value equality first
                        try:
                            if opciones_conf.nth(j).get_attribute("value") == config_value:
                                page.select_option("#dnn_ctr417_SiceTAC_CONFIGURACION", value=config_value)
                                found_conf = True
                                break
                        except Exception:
                            pass
                    if not found_conf:
                        # try exact-text match
                        if option_exists(page, "#dnn_ctr417_SiceTAC_CONFIGURACION", row["configuracion"]):
                            seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_CONFIGURACION", row["configuracion"])
                            found_conf = True
                        else:
                            df_output.at[i, "resultado"] = f"No existe configuracion: {row['configuracion']}"
                            break

                        # Smart wait: prefer waiting for a meaningful XHR response,
                        # fall back to the generic postback wait.
                        try:
                            if not wait_for_significant_response(page, timeout_ms=8000):
                                esperar_postback(page)
                        except Exception:
                            try:
                                esperar_postback(page)
                            except Exception:
                                pass
                        log_debug(f"row {i}: config selected elapsed={time.time()-row_t0:.3f}s")

                    # Validar/seleccionar condicion (exact match required)
                    if not option_exists(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", row["condicion"]):
                        df_output.at[i, "resultado"] = f"No existe condicion: {row['condicion']}"
                        break
                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", row["condicion"])

                    try:
                        if not wait_for_significant_response(page, timeout_ms=8000):
                            esperar_postback(page)
                    except Exception:
                        try:
                            esperar_postback(page)
                        except Exception:
                            pass
                    log_debug(f"row {i}: condicion selected elapsed={time.time()-row_t0:.3f}s")

                    # carroceria / unidad transporte (exact match required)
                    if not option_exists(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", row["carroceria"]):
                        df_output.at[i, "resultado"] = f"No existe unidad transporte (carroceria): {row['carroceria']}"
                        break
                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", row["carroceria"])

                    try:
                        if not wait_for_significant_response(page, timeout_ms=8000):
                            esperar_postback(page)
                    except Exception:
                        try:
                            esperar_postback(page)
                        except Exception:
                            pass
                    log_debug(f"row {i}: carroceria selected elapsed={time.time()-row_t0:.3f}s")

                    condicion = normalizar(row["condicion"])


                    if condicion != "vacio" and pd.notna(row["tipo_carga"]):
                        if not option_exists(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", row["tipo_carga"]):
                            df_output.at[i, "resultado"] = f"No existe tipo_carga: {row['tipo_carga']}"
                            break
                        seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", row["tipo_carga"])

                    # Origen: must exist exactly
                    if not option_exists(page, "#dnn_ctr417_SiceTAC_ORIGEN", row["origen"]):
                        df_output.at[i, "resultado"] = f"No existe origen: {row['origen']}"
                        break
                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_ORIGEN", row["origen"])

                    esperar_select(page, "#dnn_ctr417_SiceTAC_DESTINO")
                    log_debug(f"row {i}: origen selected elapsed={time.time()-row_t0:.3f}s")

                    # Destino: must exist exactly after origen selection
                    if not option_exists(page, "#dnn_ctr417_SiceTAC_DESTINO", row["destino"]):
                        df_output.at[i, "resultado"] = f"No existe destino: {row['destino']}"
                        break
                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_DESTINO", row["destino"])

                    log_debug(f"row {i}: destino selected elapsed={time.time()-row_t0:.3f}s")

                    page.fill("#dnn_ctr417_SiceTAC_HORASCARGUE", str(row["hora_cargue"]))
                    page.fill("#dnn_ctr417_SiceTAC_HORASDESCARGUE", str(row["hora_descargue"]))

                    captcha_texto = page.inner_text("#dnn_ctr417_SiceTAC_Cat")
                    captcha_resultado = resolver_captcha(captcha_texto)
                    page.fill("#dnn_ctr417_SiceTAC_Resultado", str(captcha_resultado))

                    valor_antes = page.input_value("#dnn_ctr417_SiceTAC_COSTOTOTALVIAJE")

                    page.click("#dnn_ctr417_SiceTAC_btCalcular")

                    page.wait_for_function("""
                    (valor) => {
                        const el = document.querySelector("#dnn_ctr417_SiceTAC_COSTOTOTALVIAJE");
                        return el && el.value !== valor;
                    }
                    """, arg=valor_antes)

                    log_debug(f"row {i}: calculation finished elapsed={time.time()-row_t0:.3f}s")

                    df_output.at[i, "ruta"] = page.locator("#dnn_ctr417_SiceTAC_RUTA option:checked").inner_text()
                    df_output.at[i, "costo_total"] = page.input_value("#dnn_ctr417_SiceTAC_COSTOTOTALVIAJE")
                    df_output.at[i, "costo_km"] = page.input_value("#dnn_ctr417_SiceTAC_COSTOVIAJEKM")
                    df_output.at[i, "costo_tonelada"] = page.input_value("#dnn_ctr417_SiceTAC_COSTOTONELADATOTAL")
                    df_output.at[i, "costo_espera"] = page.input_value("#dnn_ctr417_SiceTAC_COSTOTIEMPOESPERA")

                    # Validar que se hayan calculado costos: si todos son None/0 -> marcar error
                    total_val = parse_number(df_output.at[i, "costo_total"])
                    km_val = parse_number(df_output.at[i, "costo_km"])
                    ton_val = parse_number(df_output.at[i, "costo_tonelada"])
                    espera_val = parse_number(df_output.at[i, "costo_espera"])

                    all_zero_or_missing = True
                    for v in (total_val, km_val, ton_val, espera_val):
                        if v is not None and abs(v) > 1e-9:
                            all_zero_or_missing = False
                            break

                    if all_zero_or_missing:
                        # Do not mark as 'Sin costos calculados' — treat this as a site/response error.
                        df_output.at[i, "resultado"] = "Error: no se obtuvieron costos (posible caída del sitio)"
                    else:
                        df_output.at[i, "resultado"] = "Completado con éxito"
                    log_debug(f"row {i}: finished total_elapsed={time.time()-row_t0:.3f}s resultado={df_output.at[i,'resultado']}")
                    break

                except Exception as e:
                    err_msg = str(e)

                    # Si la excepción parece indicar un dato inválido (no hay opción), no reintentar
                    if "No se encontró opción" in err_msg or "No se encontró opción para" in err_msg:
                        df_output.at[i, "resultado"] = err_msg
                        break

                    # Si hemos excedido el tiempo máximo de reintentos, registrar y pasar a la siguiente fila
                    elapsed = time.time() - start_time
                    if elapsed >= 40:
                        df_output.at[i, "resultado"] = f"Error (timeout de reintentos): {err_msg}"
                        break

                    # Intentar recargar la página y esperar un poco antes de reintentar
                    try:
                        page.reload()
                    except Exception:
                        try:
                            page.goto(URL)
                        except Exception:
                            pass

                    time.sleep(2)

            # Guardar el estado tras procesar (o marcar error) la fila actual
            # To reduce expensive disk I/O, only checkpoint every CHECKPOINT_EVERY rows when FAST_PROCESSING is enabled.
            try:
                if CHECKPOINT_EVERY <= 1:
                    df_output.to_excel(OUTPUT_FILE, index=False)
                else:
                    # i is zero-based; write when we've processed a multiple of CHECKPOINT_EVERY or on the final row
                    if (i + 1) % CHECKPOINT_EVERY == 0:
                        df_output.to_excel(OUTPUT_FILE, index=False)
            except Exception:
                # On any write failure, ignore to avoid crashing processing loop; final save will attempt to persist results.
                pass

            # If a job_meta_path was provided, update progress metadata per-row.
            if job_meta_path:
                try:
                    # Compute processed and error counts so far
                    success_mask = df_output.get("resultado", "") == "Completado con éxito"
                    processed_count_partial = int(df_output[success_mask].shape[0])
                    total_rows_partial = int(df_output.shape[0])
                    error_count_partial = int(total_rows_partial - processed_count_partial)
                    meta = {"status": "running", "rows_processed": processed_count_partial, "rows_errors": error_count_partial, "total_rows": total_rows_partial}
                    # atomic write
                    tmp = job_meta_path + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as mf:
                        import json
                        json.dump(meta, mf)
                    try:
                        os.replace(tmp, job_meta_path)
                    except Exception:
                        try:
                            os.remove(job_meta_path)
                            os.replace(tmp, job_meta_path)
                        except Exception:
                            pass
                except Exception:
                    pass

            time.sleep(WAIT_TIME)

        browser.close()

    # Final checkpoint: ensure output file is written at least once after processing completes
    try:
        df_output.to_excel(OUTPUT_FILE, index=False)
    except Exception:
        pass

    # Calcular cuántas filas fueron procesadas con éxito y cuántas con error
    try:
        success_mask = df_output.get("resultado", "") == "Completado con éxito"
        processed_count = int(df_output[success_mask].shape[0])
        error_count = int(df_output.shape[0] - processed_count)
    except Exception:
        # Si por alguna razón la columna no existe o hay un error, devolver totales conservadores
        try:
            total = int(df_output.shape[0])
        except Exception:
            total = 0
        processed_count = total
        error_count = 0

    return processed_count, error_count