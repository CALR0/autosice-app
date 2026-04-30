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
        inject_selector_map,
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

        # Helper: try to set a select's value using value, then label, then
        # a JS normalized-text match. Returns True on success.
        def try_set_select(selector, val_text):
            try:
                if val_text is None:
                    return False
                sval = str(val_text).strip()
                if sval == "":
                    return False
                # wait briefly for the element to exist
                try:
                    page.wait_for_selector(selector, timeout=1500)
                except Exception:
                    pass

                # 1) try by value
                try:
                    res = page.select_option(selector, value=sval)
                    if res:
                        try:
                            page.evaluate("sel=>{const e=document.querySelector(sel); if(e) e.dispatchEvent(new Event('change',{bubbles:true}));}", selector)
                        except Exception:
                            pass
                        return True
                except Exception:
                    pass

                # 2) try by label (visible text)
                try:
                    res = page.select_option(selector, label=sval)
                    if res:
                        try:
                            page.evaluate("sel=>{const e=document.querySelector(sel); if(e) e.dispatchEvent(new Event('change',{bubbles:true}));}", selector)
                        except Exception:
                            pass
                        return True
                except Exception:
                    pass

                # 3) try JS-side normalized full-text match to find option.value
                try:
                    found = page.evaluate(
                        "(sel, target) => { function norm(s){ try{ return s.toString().toLowerCase().normalize('NFD').replace(/\\p{Diacritic}/gu,'').replace(/[^a-z0-9\\s]/g,'').replace(/\\s+/g,' ').trim(); }catch(e){return s.toString().toLowerCase().trim();} } const el = document.querySelector(sel); if(!el) return null; const t = norm(target||''); for(const o of (el.options||[])){ try{ if(norm(o.innerText||o.text||'')===t) return o.value;}catch(e){continue;} } return null }",
                        selector,
                        sval,
                    )
                    if found:
                        try:
                            page.select_option(selector, value=found)
                        except Exception:
                            try:
                                page.evaluate("(sel,val)=>{const e=document.querySelector(sel); if(e){ e.value=val; e.dispatchEvent(new Event('change',{bubbles:true})); }}", selector, found)
                            except Exception:
                                pass
                        return True
                except Exception:
                    pass

                return False
            except Exception:
                return False

        from collections import OrderedDict
        selector_cache = OrderedDict()

        # Allowed exact values and labels for strict selects. Accepts either
        # the option `value` (preferred) or the visible label (case-insensitive).
        ALLOWED_SELECTS = {
            "#dnn_ctr417_SiceTAC_CONFIGURACION": {
                "values": set([
                    "2","2_7_8","2_8_9","2_9_105","2S2","2S3",
                    "3","3S2","3S3","V2","V3","V4",
                ]),
                "labels": set(),
            },
            "#dnn_ctr417_SiceTAC_CONDICIONCARGA": {
                "values": set(["1","2"]),
                "labels": set(["CARGADO","VACIO"]),
            },
            "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE": {
                "values": set(["1","10","2","60","48","231","1061","4"]),
                "labels": set(["ESTACAS","ESTIBAS","FURGON","FURGON REFRIGERADO","PLATAFORMA","PORTACONTENEDORES","TANQUE","VOLCO"]),
            },
            "#dnn_ctr417_SiceTAC_TIPOCARGA": {
                "values": set(["12","5"]),
                "labels": set(["General","Granel Sólido"]),
            },
        }

        def allowed_for_selector(sel, raw_val):
            try:
                if raw_val is None:
                    return False
                sval = str(raw_val).strip()
                if sval == "":
                    return False
                cfg = ALLOWED_SELECTS.get(sel)
                if not cfg:
                    return True
                if sval in cfg["values"]:
                    return True
                # case-insensitive label match
                up = sval.upper()
                for lab in cfg["labels"]:
                    if up == lab.upper():
                        return True
                return False
            except Exception:
                return False

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
                    # Validate Excel-provided config value is one of allowed options
                    config_sel = "#dnn_ctr417_SiceTAC_CONFIGURACION"
                    if not allowed_for_selector(config_sel, row.get("configuracion")):
                        try:
                            log_debug(f"invalid configuracion value for row {i}: {row.get('configuracion')} allowed={ALLOWED_SELECTS.get(config_sel)}")
                        except Exception:
                            pass
                        df_output.at[i, "resultado"] = f"Valor invalido para configuracion: {row.get('configuracion')}"
                        break

                    # Prefer direct selection by value/label using the Excel value.
                    config_value = str(row["configuracion"]) if pd.notna(row["configuracion"]) else ""
                    found_conf = False
                    try:
                        if try_set_select("#dnn_ctr417_SiceTAC_CONFIGURACION", config_value):
                            found_conf = True
                    except Exception:
                        found_conf = False

                    if not found_conf:
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

                    # The 'condicion' select may be created/updated after selecting
                    # the configuration. Retry a few times and rebuild the selector
                    # map after waiting to avoid false negatives when the element
                    # is not yet present in the DOM.
                    # For 'condicion' prefer direct set by Excel value/label.
                    cond_sel = "#dnn_ctr417_SiceTAC_CONDICIONCARGA"
                    cond_val = row["condicion"]
                    # validate condicion
                    if not allowed_for_selector(cond_sel, cond_val):
                        try:
                            log_debug(f"invalid condicion value for row {i}: {cond_val} allowed={ALLOWED_SELECTS.get(cond_sel)}")
                        except Exception:
                            pass
                        df_output.at[i, "resultado"] = f"Valor invalido para condicion: {cond_val}"
                        break
                    cond_ok = False
                    try:
                        # allow a short wait for dynamic creation
                        try:
                            page.wait_for_selector(cond_sel, timeout=1500)
                        except Exception:
                            pass
                        if try_set_select(cond_sel, cond_val):
                            cond_ok = True
                    except Exception:
                        cond_ok = False

                    if not cond_ok:
                        df_output.at[i, "resultado"] = f"No existe condicion: {row['condicion']}"
                        break

                    try:
                        if not wait_for_significant_response(page, timeout_ms=1000):
                            esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                    except Exception:
                        try:
                            esperar_postback(page, min(WAIT_TIME, 0.5), FAST_PROCESSING)
                        except Exception:
                            pass
                    log_debug(f"row {i}: condicion selected elapsed={time.time()-row_t0:.3f}s")

                    # For 'unidad transporte' (carroceria) set by Excel value/label directly
                    # validate unidad transporte
                    unidad_sel = "#dnn_ctr417_SiceTAC_UNIDADTRANSPORTE"
                    if not allowed_for_selector(unidad_sel, row.get("carroceria")):
                        try:
                            log_debug(f"invalid unidad transporte value for row {i}: {row.get('carroceria')} allowed={ALLOWED_SELECTS.get(unidad_sel)}")
                        except Exception:
                            pass
                        df_output.at[i, "resultado"] = f"Valor invalido para unidad transporte: {row.get('carroceria')}"
                        break

                    try:
                        if not try_set_select(unidad_sel, row["carroceria"]):
                            df_output.at[i, "resultado"] = f"No existe unidad transporte (carroceria): {row['carroceria']}"
                            break
                    except Exception:
                        df_output.at[i, "resultado"] = f"No existe unidad transporte (carroceria): {row['carroceria']}"
                        break

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
                        tipo_sel = "#dnn_ctr417_SiceTAC_TIPOCARGA"
                        # validate tipo carga
                        if not allowed_for_selector(tipo_sel, row.get("tipo_carga")):
                            try:
                                log_debug(f"invalid tipo_carga value for row {i}: {row.get('tipo_carga')} allowed={ALLOWED_SELECTS.get(tipo_sel)}")
                            except Exception:
                                pass
                            df_output.at[i, "resultado"] = f"Valor invalido para tipo_carga: {row.get('tipo_carga')}"
                            break

                        try:
                            if not try_set_select(tipo_sel, row["tipo_carga"]):
                                df_output.at[i, "resultado"] = f"No existe tipo_carga: {row['tipo_carga']}"
                                break
                        except Exception:
                            df_output.at[i, "resultado"] = f"No existe tipo_carga: {row['tipo_carga']}"
                            break

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
