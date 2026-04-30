"""Full implementation of the processing logic moved from top-level
`backend/procesador.py` so modules under `processors/` own the core
business logic. This file is an exact (behavior-preserving) copy of the
original implementation; imports are left as package-level imports so
existing code that runs from the project root continues to work.
"""

import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time
import os
import unicodedata


def procesar_excel(INPUT_FILE, OUTPUT_FILE, job_meta_path=None):

    # ============================================================
    # CONFIGURACIÓN
    # ============================================================

    from config import URL, FAST_PROCESSING, WAIT_TIME, CHECKPOINT_EVERY, PREBUILD_SELECTS
    from utils.timing import log_debug
    from utils.normalization import normalizar, resolver_captcha, parse_number
    from services.playwright_service import (
        setup_resource_blocking,
        esperar_select,
        esperar_postback,
        wait_for_significant_response,
        build_selector_map,
        seleccionar_opcion,
        option_exists,
    )
    from jobs.manager import save_job_meta_path


    # seleccionar_opcion and option_exists are provided by services.playwright_service


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
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page()

        from collections import OrderedDict
        selector_cache = OrderedDict()

        if FAST_PROCESSING:
            setup_resource_blocking(page, FAST_PROCESSING)
        page.goto(URL)

        prebuild_raw = PREBUILD_SELECTS
        if prebuild_raw:
            try:
                prebuild_list = [s.strip() for s in prebuild_raw.split(",") if s.strip()]
                for sel in prebuild_list:
                    try:
                        mapping, cnt = build_selector_map(page, sel, normalizar, log_debug)
                        # insert with simple LRU eviction (max 8)
                        try:
                            if sel in selector_cache:
                                try:
                                    del selector_cache[sel]
                                except Exception:
                                    pass
                            selector_cache[sel] = (mapping, cnt)
                            try:
                                while len(selector_cache) > 8:
                                    selector_cache.popitem(last=False)
                            except Exception:
                                pass
                        except Exception:
                            selector_cache[sel] = (mapping, cnt)
                            log_debug(f"prebuilt selector: {sel}")
                    except Exception as e:
                        log_debug(f"prebuild failed for {sel}: {e}")
            except Exception:
                pass

        # Always prebuild small, frequently-used selectors to avoid rebuilding them per-row.
        try:
            small_selectors = [
                "#dnn_ctr417_SiceTAC_CONFIGURACION",
                "#dnn_ctr417_SiceTAC_CONDICIONCARGA",
                "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE",
                "#dnn_ctr417_SiceTAC_TIPOCARGA",
            ]
            for sel in small_selectors:
                try:
                        if sel not in selector_cache:
                            mapping, cnt = build_selector_map(page, sel, normalizar, log_debug)
                        # insert with LRU eviction
                        try:
                            if sel in selector_cache:
                                del selector_cache[sel]
                        except Exception:
                            pass
                        selector_cache[sel] = (mapping, cnt)
                        try:
                            from services.playwright_service import inject_selector_map
                            inject_selector_map(page, sel, mapping)
                        except Exception:
                            pass
                        try:
                            while len(selector_cache) > 8:
                                selector_cache.popitem(last=False)
                        except Exception:
                            pass
                        log_debug(f"prebuilt selector: {sel}")
                except Exception:
                    pass
        except Exception:
            pass

        for i, row in df_output.iterrows():

            row_t0 = time.time()
            log_debug(f"start row {i}")

            if str(row.get("resultado", "")).strip() == "Completado con éxito":
                log_debug(f"skip row {i}: already completed")
                continue

            required_fields = ["configuracion", "condicion", "carroceria", "origen", "destino", "hora_cargue", "hora_descargue"]
            missing = [f for f in required_fields if pd.isna(row.get(f, None)) or str(row.get(f, "")).strip() == ""]
            if missing:
                df_output.at[i, "resultado"] = f"Faltan datos: {', '.join(missing)}"
                df_output.to_excel(OUTPUT_FILE, index=False)
                continue

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

            start_time = time.time()
            while True:
                try:
                    config_value = str(row["configuracion"]) if pd.notna(row["configuracion"]) else ""
                    opciones_conf = page.locator("#dnn_ctr417_SiceTAC_CONFIGURACION option")
                    found_conf = False
                    for j in range(opciones_conf.count()):
                        try:
                            if opciones_conf.nth(j).get_attribute("value") == config_value:
                                page.select_option("#dnn_ctr417_SiceTAC_CONFIGURACION", value=config_value)
                                found_conf = True
                                break
                        except Exception:
                            pass
                    if not found_conf:
                        if option_exists(page, "#dnn_ctr417_SiceTAC_CONFIGURACION", row["configuracion"], selector_cache, normalizar, log_debug):
                            # try fast JS-side exact normalized match first
                            try:
                                from services.playwright_service import find_option_value_js, select_option_via_page_map
                                val = find_option_value_js(page, "#dnn_ctr417_SiceTAC_CONFIGURACION", row["configuracion"])
                                if val:
                                    ok = select_option_via_page_map(page, "#dnn_ctr417_SiceTAC_CONFIGURACION", val)
                                    if ok:
                                        found_conf = True
                                if not found_conf:
                                    # fallback to Python-side selector helper
                                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_CONFIGURACION", row["configuracion"], selector_cache, normalizar, log_debug)
                                    found_conf = True
                            except Exception:
                                seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_CONFIGURACION", row["configuracion"], selector_cache, normalizar, log_debug)
                                found_conf = True
                        else:
                            df_output.at[i, "resultado"] = f"No existe configuracion: {row['configuracion']}"
                            break

                        try:
                            if not wait_for_significant_response(page, timeout_ms=1000):
                                esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                        except Exception:
                            try:
                                esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                            except Exception:
                                pass
                        log_debug(f"row {i}: config selected elapsed={time.time()-row_t0:.3f}s")
                    # After selecting configuration, the 'condicion' select may be
                    # created/updated by a postback. Wait briefly for it to exist
                    # before checking/using it.
                    try:
                        esperar_select(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", timeout=2.0)
                    except Exception:
                        pass

                    if not option_exists(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", row["condicion"], selector_cache, normalizar, log_debug):
                        df_output.at[i, "resultado"] = f"No existe condicion: {row['condicion']}"
                        break
                    try:
                        from services.playwright_service import find_option_value_js, select_option_via_page_map
                        val = find_option_value_js(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", row["condicion"])
                        if val:
                            if select_option_via_page_map(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", val):
                                pass
                            else:
                                seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", row["condicion"], selector_cache, normalizar, log_debug)
                        else:
                            seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", row["condicion"], selector_cache, normalizar, log_debug)
                    except Exception:
                        seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_CONDICIONCARGA", row["condicion"], selector_cache, normalizar, log_debug)

                    try:
                        if not wait_for_significant_response(page, timeout_ms=1000):
                            esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                    except Exception:
                        try:
                            esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                        except Exception:
                            pass
                    log_debug(f"row {i}: condicion selected elapsed={time.time()-row_t0:.3f}s")

                    if not option_exists(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", row["carroceria"], selector_cache, normalizar, log_debug):
                        df_output.at[i, "resultado"] = f"No existe unidad transporte (carroceria): {row['carroceria']}"
                        break
                    try:
                        from services.playwright_service import find_option_value_js, select_option_via_page_map
                        val = find_option_value_js(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", row["carroceria"])
                        if val:
                            if select_option_via_page_map(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", val):
                                pass
                            else:
                                seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", row["carroceria"], selector_cache, normalizar, log_debug)
                        else:
                            seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", row["carroceria"], selector_cache, normalizar, log_debug)
                    except Exception:
                        seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE", row["carroceria"], selector_cache, normalizar, log_debug)

                    try:
                        if not wait_for_significant_response(page, timeout_ms=1000):
                            esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                    except Exception:
                        try:
                            esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                        except Exception:
                            pass
                    log_debug(f"row {i}: carroceria selected elapsed={time.time()-row_t0:.3f}s")

                    condicion = normalizar(row["condicion"])


                    if condicion != "vacio" and pd.notna(row["tipo_carga"]):
                        if not option_exists(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", row["tipo_carga"], selector_cache, normalizar, log_debug):
                            df_output.at[i, "resultado"] = f"No existe tipo_carga: {row['tipo_carga']}"
                            break
                        try:
                            from services.playwright_service import find_option_value_js, select_option_via_page_map
                            val = find_option_value_js(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", row["tipo_carga"])
                            if val:
                                if select_option_via_page_map(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", val):
                                    pass
                                else:
                                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", row["tipo_carga"], selector_cache, normalizar, log_debug)
                            else:
                                seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", row["tipo_carga"], selector_cache, normalizar, log_debug)
                        except Exception:
                            seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_TIPOCARGA", row["tipo_carga"], selector_cache, normalizar, log_debug)

                    if not option_exists(page, "#dnn_ctr417_SiceTAC_ORIGEN", row["origen"], selector_cache, normalizar, log_debug):
                        df_output.at[i, "resultado"] = f"No existe origen: {row['origen']}"
                        break
                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_ORIGEN", row["origen"], selector_cache, normalizar, log_debug)

                    esperar_select(page, "#dnn_ctr417_SiceTAC_DESTINO")
                    log_debug(f"row {i}: origen selected elapsed={time.time()-row_t0:.3f}s")

                    if not option_exists(page, "#dnn_ctr417_SiceTAC_DESTINO", row["destino"], selector_cache, normalizar, log_debug):
                        df_output.at[i, "resultado"] = f"No existe destino: {row['destino']}"
                        break
                    seleccionar_opcion(page, "#dnn_ctr417_SiceTAC_DESTINO", row["destino"], selector_cache, normalizar, log_debug)

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
                        df_output.at[i, "resultado"] = "Error: no se obtuvieron costos (posible caída del sitio)"
                    else:
                        df_output.at[i, "resultado"] = "Completado con éxito"
                    log_debug(f"row {i}: finished total_elapsed={time.time()-row_t0:.3f}s resultado={df_output.at[i,'resultado']}")
                    break

                except Exception as e:
                    err_msg = str(e)

                    if "No se encontró opción" in err_msg or "No se encontró opción para" in err_msg:
                        df_output.at[i, "resultado"] = err_msg
                        break

                    elapsed = time.time() - start_time
                    if elapsed >= 40:
                        df_output.at[i, "resultado"] = f"Error (timeout de reintentos): {err_msg}"
                        break

                    try:
                        page.reload()
                    except Exception:
                        try:
                            page.goto(URL)
                        except Exception:
                            pass

                    time.sleep(2)

            try:
                if CHECKPOINT_EVERY <= 1:
                    df_output.to_excel(OUTPUT_FILE, index=False)
                else:
                    if (i + 1) % CHECKPOINT_EVERY == 0:
                        df_output.to_excel(OUTPUT_FILE, index=False)
            except Exception:
                pass

            if job_meta_path:
                try:
                    # Only count rows that have been attempted (non-empty `resultado`).
                    total_rows_partial = int(df_output.shape[0])
                    results_col = df_output.get("resultado", "")
                    attempted_mask = (results_col != "")
                    attempted_count = int(df_output[attempted_mask].shape[0])
                    success_mask = (results_col == "Completado con éxito")
                    processed_count_partial = int(df_output[success_mask].shape[0])
                    error_count_partial = int(attempted_count - processed_count_partial)
                    meta = {
                        "status": "running",
                        "rows_processed": processed_count_partial,
                        "rows_errors": error_count_partial,
                        "total_rows": total_rows_partial,
                        "rows_attempted": attempted_count,
                    }
                    try:
                        try:
                            log_debug(f"writing job meta to {job_meta_path}: {meta}")
                        except Exception:
                            pass
                        save_job_meta_path(job_meta_path, meta)
                        try:
                            log_debug(f"wrote job meta to {job_meta_path}")
                        except Exception:
                            pass
                    except Exception:
                        try:
                            log_debug(f"failed writing job meta to {job_meta_path}")
                        except Exception:
                            pass
                except Exception:
                    pass

            # small wait and force garbage collection to reduce memory pressure on constrained instances
            try:
                time.sleep(WAIT_TIME)
            except Exception:
                pass
            try:
                import gc
                gc.collect()
            except Exception:
                pass

        browser.close()

    try:
        df_output.to_excel(OUTPUT_FILE, index=False)
    except Exception:
        pass

    try:
        success_mask = df_output.get("resultado", "") == "Completado con éxito"
        processed_count = int(df_output[success_mask].shape[0])
        error_count = int(df_output.shape[0] - processed_count)
    except Exception:
        try:
            total = int(df_output.shape[0])
        except Exception:
            total = 0
        processed_count = total
        error_count = 0

    return processed_count, error_count
