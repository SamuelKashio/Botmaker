"""
botmaker_extractor.py
─────────────────────
Extrae TODAS las respuestas posibles de la Botmaker API v2.0.
Fase 1: Endpoints sin IDs dinámicos (listas, catálogos globales).
Fase 2: Endpoints que requieren IDs reales (obtenidos en Fase 1).
Guarda todo en botmaker_responses.json para análisis posterior.
"""

import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import time

BASE_URL = "https://api.botmaker.com/v2.0"

st.set_page_config(page_title="Botmaker — Extractor de Responses", page_icon="🔬", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=IBM+Plex+Sans:wght@300;400;500&display=swap');

body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background: #0a0c10; color: #e2e8f0; }
.stSidebar { background: #111318 !important; border-right: 1px solid #1e2230; }

.log-entry {
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    padding: 5px 10px;
    border-radius: 4px;
    margin: 3px 0;
    border-left: 3px solid;
}
.log-ok    { background: rgba(16,185,129,0.07); border-color: #10b981; color: #6ee7b7; }
.log-err   { background: rgba(239,68,68,0.07);  border-color: #ef4444; color: #fca5a5; }
.log-skip  { background: rgba(107,114,128,0.07); border-color: #6b7280; color: #9ca3af; }
.log-info  { background: rgba(59,130,246,0.07); border-color: #3b82f6; color: #93c5fd; }

.summary-card {
    background: #111318;
    border: 1px solid #1e2230;
    border-radius: 10px;
    padding: 18px 22px;
    text-align: center;
}
.summary-num {
    font-family: 'Space Mono', monospace;
    font-size: 2rem;
    font-weight: 700;
}
.summary-label { font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }

.stButton > button {
    background: #10b981 !important; color: #0a0c10 !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important; border-radius: 8px !important; border: none !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_headers(token):
    return {"access-token": token, "Content-Type": "application/json"}

def call(token, method, path, params=None, body=None, timeout=25):
    """Ejecuta un request y devuelve (status_code, json_or_text, elapsed_ms)"""
    url = f"{BASE_URL}/{path}"
    t0 = time.time()
    try:
        r = requests.request(
            method, url,
            headers=get_headers(token),
            params=params,
            json=body,
            timeout=timeout,
        )
        elapsed = int((time.time() - t0) * 1000)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return r.status_code, data, elapsed
    except requests.exceptions.Timeout:
        return -1, "TIMEOUT", int((time.time() - t0) * 1000)
    except Exception as e:
        return -1, str(e), int((time.time() - t0) * 1000)

def safe_items(response_data):
    """Extrae lista de items de un response, sea lista o dict con 'items'."""
    if isinstance(response_data, list):
        return response_data
    if isinstance(response_data, dict):
        return response_data.get("items", [])
    return []

def first_id(response_data, *keys):
    """Busca el primer valor de una de las keys en el primer item."""
    items = safe_items(response_data)
    if not items:
        return None
    first = items[0]
    for k in keys:
        if k in first and first[k]:
            return first[k]
    return None

def today_range(days_back=7):
    now = datetime.utcnow()
    return {
        "from": (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z"),
        "to": now.strftime("%Y-%m-%dT23:59:59Z"),
    }

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.markdown("# 🔬 Botmaker — Extractor de Responses")
st.markdown(
    "Este programa llama a **todos los endpoints GET** de la Botmaker API v2.0, "
    "captura cada response completo y lo guarda en un archivo JSON. "
    "Usá ese archivo para compartirlo y que el dashboard sea construido con campos reales."
)
st.markdown("---")

col_cfg, col_run = st.columns([2, 1])

with col_cfg:
    token = st.text_input("🔑 Access Token", type="password", placeholder="Tu token de Botmaker...")

    st.markdown("**Opciones de extracción**")
    col1, col2 = st.columns(2)
    with col1:
        days_messages = st.number_input("Últimos N días para mensajes", min_value=1, max_value=30, value=7)
        days_sessions = st.number_input("Últimos N días para sesiones", min_value=1, max_value=30, value=7)
    with col2:
        days_billing  = st.number_input("Últimos N días para billing",  min_value=1, max_value=90, value=30)
        days_audit    = st.number_input("Últimos N días para auditoría", min_value=1, max_value=90, value=30)

    include_openapi = st.checkbox("Incluir OpenAPI spec (puede ser grande)", value=False)

with col_run:
    st.markdown("**Estado**")
    status_box = st.empty()
    status_box.info("Esperando token...")

    run_btn = st.button("🚀 Iniciar extracción", disabled=not bool(token))

st.markdown("---")

if run_btn and token:
    results = {}      # endpoint_key -> {status, data, elapsed_ms, url, params}
    log_lines = []
    ok_count = 0
    err_count = 0
    skip_count = 0

    log_container = st.empty()
    progress_bar  = st.progress(0)
    status_box.warning("⏳ Extrayendo...")

    def log(msg, kind="info"):
        log_lines.append((msg, kind))
        html = ""
        for m, k in log_lines[-40:]:   # últimas 40 líneas
            html += f'<div class="log-entry log-{k}">{m}</div>'
        log_container.markdown(
            f'<div style="max-height:380px;overflow-y:auto;background:#0d1017;'
            f'border:1px solid #1e2230;border-radius:8px;padding:8px;">{html}</div>',
            unsafe_allow_html=True
        )

    def record(key, label, status, data, elapsed, url, params=None):
        nonlocal ok_count, err_count
        results[key] = {
            "label": label,
            "url": url,
            "params": params or {},
            "status_code": status,
            "elapsed_ms": elapsed,
            "data": data,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
        }
        if status == 200:
            ok_count += 1
            n = len(safe_items(data)) if isinstance(data, (dict, list)) else "—"
            log(f"✅ {status} {label} [{elapsed}ms] — {n} items", "ok")
        elif status == -1:
            err_count += 1
            log(f"❌ ERR {label} — {str(data)[:60]}", "err")
        else:
            err_count += 1
            log(f"⚠️ {status} {label} [{elapsed}ms]", "err")

    # ── Fase 1: Endpoints directos (sin IDs dinámicos) ──────────────────────
    log("━━━ FASE 1: Endpoints directos ━━━", "info")

    PHASE1 = [
        # (key, label, path, params)
        ("agents_all",       "Agents — lista completa",         "agents",    None),
        ("agents_online",    "Agents — online",                 "agents",    {"online": "true"}),
        ("channels",         "Channels — lista",                "channels",  None),
        ("channels_active",  "Channels — activos",              "channels",  {"active": "true"}),
        ("roles",            "Roles — lista",                   "roles",     None),
        ("intents",          "Intents — lista",                 "intents",   None),
        ("webhooks",         "Webhooks — lista",                "webhooks",  None),
        ("wa_templates",     "WA Templates — lista",            "whatsapp/templates", None),
        ("wa_accounts",      "WA Accounts — lista",             "whatsapp/accounts",  None),
        ("commerce_catalogs","Commerce Catalogs — lista",       "commerce/catalogs",  None),
        ("messages_recent",  "Messages — últimos 7 días",       "messages",
            {**today_range(days_messages)}),
        ("messages_wa",      "Messages — WhatsApp",             "messages",
            {**today_range(days_messages), "chat-platform": "whatsapp"}),
        ("sessions",         "Sessions — recientes",            "sessions",
            {**today_range(days_sessions), "include-events": "true"}),
        ("chats_list",       "Chats — lista reciente",          "chats",
            {**today_range(days_messages)}),
        ("billing_wa",       "Billing — WA conversations",      "billing/whatsapp/conversations",
            {**today_range(days_billing)}),
        ("audit_agent",      "Audit — agentes",                 "audits/agent",
            {"from": (datetime.utcnow()-timedelta(days=days_audit)).strftime("%Y-%m-%d"),
             "to": datetime.utcnow().strftime("%Y-%m-%d")}),
        ("audit_intent",     "Audit — intents",                 "audits/intent",
            {"from": (datetime.utcnow()-timedelta(days=days_audit)).strftime("%Y-%m-%d"),
             "to": datetime.utcnow().strftime("%Y-%m-%d")}),
        ("calls",            "Calls — lista",                   "calls",
            {"from": (datetime.utcnow()-timedelta(days=30)).strftime("%Y-%m-%d")}),
    ]

    if include_openapi:
        PHASE1.append(("openapi", "OpenAPI spec", "openapi.json", None))

    total_steps = len(PHASE1) + 15  # phase2 estimate
    done = 0

    for key, label, path, params in PHASE1:
        status, data, elapsed = call(token, "GET", path, params=params)
        record(key, label, status, data, elapsed, f"{BASE_URL}/{path}", params)
        done += 1
        progress_bar.progress(done / total_steps)
        time.sleep(0.15)  # pequeño delay para no saturar la API

    # ── Fase 2: Endpoints que necesitan IDs de la Fase 1 ────────────────────
    log("━━━ FASE 2: Endpoints con IDs dinámicos ━━━", "info")

    # -- Chat por ID --
    chat_id = first_id(results.get("chats_list", {}).get("data"), "id")
    if chat_id:
        status, data, elapsed = call(token, "GET", f"chats/{chat_id}")
        record("chat_detail", f"Chat detail — {chat_id[:12]}…", status, data, elapsed,
               f"{BASE_URL}/chats/{chat_id}")
    else:
        log("⏭ Chat detail — sin chat_id disponible", "skip")
        skip_count += 1
    done += 1; progress_bar.progress(min(done/total_steps, 1.0))

    # -- Agent detail (PATCH no lo llamamos, solo usamos la lista) --
    # Ya tenemos agents_all

    # -- Roles detail --
    role_id = first_id(results.get("roles", {}).get("data"), "id", "roleId")
    if role_id:
        status, data, elapsed = call(token, "GET", f"roles/{role_id}")
        record("role_detail", f"Role detail — {role_id[:16]}…", status, data, elapsed,
               f"{BASE_URL}/roles/{role_id}")
    else:
        log("⏭ Role detail — sin role_id", "skip")
        skip_count += 1
    done += 1; progress_bar.progress(min(done/total_steps, 1.0))

    # -- Intent detail --
    intent_id = first_id(results.get("intents", {}).get("data"), "id", "name")
    if intent_id:
        status, data, elapsed = call(token, "GET", f"intents/{intent_id}")
        record("intent_detail", f"Intent detail — {intent_id[:16]}…", status, data, elapsed,
               f"{BASE_URL}/intents/{intent_id}")
    else:
        log("⏭ Intent detail — sin intent_id", "skip")
        skip_count += 1
    done += 1; progress_bar.progress(min(done/total_steps, 1.0))

    # -- Webhook detail --
    wh_id = first_id(results.get("webhooks", {}).get("data"), "id")
    if wh_id:
        status, data, elapsed = call(token, "GET", f"webhooks/{wh_id}")
        record("webhook_detail", f"Webhook detail — {wh_id[:12]}…", status, data, elapsed,
               f"{BASE_URL}/webhooks/{wh_id}")
    else:
        log("⏭ Webhook detail — sin webhook_id", "skip")
        skip_count += 1
    done += 1; progress_bar.progress(min(done/total_steps, 1.0))

    # -- WA Template detail --
    tpl_name = first_id(results.get("wa_templates", {}).get("data"), "name")
    if tpl_name:
        status, data, elapsed = call(token, "GET", f"whatsapp/templates/{tpl_name}")
        record("wa_template_detail", f"WA Template — {tpl_name[:20]}…", status, data, elapsed,
               f"{BASE_URL}/whatsapp/templates/{tpl_name}")
    else:
        log("⏭ WA Template detail — sin nombre", "skip")
        skip_count += 1
    done += 1; progress_bar.progress(min(done/total_steps, 1.0))

    # -- WA Account detail + health --
    wa_phone = first_id(results.get("wa_accounts", {}).get("data"), "phoneNumber", "phone", "id")
    if wa_phone:
        status, data, elapsed = call(token, "GET", f"whatsapp/accounts/{wa_phone}")
        record("wa_account_detail", f"WA Account — {wa_phone}", status, data, elapsed,
               f"{BASE_URL}/whatsapp/accounts/{wa_phone}")
        status2, data2, elapsed2 = call(token, "GET", f"whatsapp/accounts/{wa_phone}/health")
        record("wa_account_health", f"WA Account health — {wa_phone}", status2, data2, elapsed2,
               f"{BASE_URL}/whatsapp/accounts/{wa_phone}/health")
    else:
        log("⏭ WA Account detail/health — sin phone", "skip")
        skip_count += 2
    done += 2; progress_bar.progress(min(done/total_steps, 1.0))

    # -- Commerce: catalog detail, categories, products --
    catalog_id = first_id(results.get("commerce_catalogs", {}).get("data"), "id", "catalogId")
    if catalog_id:
        for ep_key, ep_label, ep_path in [
            ("catalog_categories", f"Catalog categories — {catalog_id[:10]}…",
             f"commerce/catalogs/{catalog_id}/categories"),
            ("catalog_products",   f"Catalog products — {catalog_id[:10]}…",
             f"commerce/catalogs/{catalog_id}/products"),
        ]:
            status, data, elapsed = call(token, "GET", ep_path)
            record(ep_key, ep_label, status, data, elapsed, f"{BASE_URL}/{ep_path}")
            done += 1; progress_bar.progress(min(done/total_steps, 1.0))
            time.sleep(0.1)
    else:
        log("⏭ Catalog detail/categories/products — sin catalog_id", "skip")
        skip_count += 2
        done += 2

    # -- Messages: paginación (siguiente página si existe) --
    next_page = results.get("messages_recent", {}).get("data", {})
    if isinstance(next_page, dict) and "nextPage" in next_page:
        # Solo guardamos la referencia, no la llamamos (podría ser pesada)
        results["messages_pagination_info"] = {
            "label": "Messages — info paginación",
            "nextPage": next_page["nextPage"],
            "note": "nextPage disponible, no se llamó automáticamente para evitar volúmenes grandes",
        }
        log("ℹ️ Messages tiene nextPage — referencia guardada (no se descargó)", "info")

    done = total_steps; progress_bar.progress(1.0)

    # ── Resumen ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ✅ Extracción completada")

    c1, c2, c3, c4 = st.columns(4)
    for col, num, label, color in [
        (c1, len(results), "Endpoints llamados", "#10b981"),
        (c2, ok_count,     "Respuestas OK",      "#10b981"),
        (c3, err_count,    "Errores",            "#ef4444"),
        (c4, skip_count,   "Salteados (sin ID)", "#6b7280"),
    ]:
        with col:
            st.markdown(f"""
            <div class="summary-card">
                <div class="summary-num" style="color:{color}">{num}</div>
                <div class="summary-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Schema discovery ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔬 Campos descubiertos por endpoint")

    schema_summary = {}
    for key, entry in results.items():
        data = entry.get("data")
        items = safe_items(data)
        if items and isinstance(items[0], dict):
            fields = list(items[0].keys())
            schema_summary[key] = {
                "label": entry.get("label", key),
                "item_count": len(items),
                "fields": fields,
                "sample": items[0],
            }
        elif isinstance(data, dict) and data:
            schema_summary[key] = {
                "label": entry.get("label", key),
                "item_count": 1,
                "fields": list(data.keys()),
                "sample": data,
            }

    for key, info in schema_summary.items():
        with st.expander(f"**{info['label']}** — {info['item_count']} item(s) · {len(info['fields'])} campos"):
            col_a, col_b = st.columns([1, 2])
            with col_a:
                st.markdown("**Campos:**")
                for f in info["fields"]:
                    val = info["sample"].get(f)
                    vtype = type(val).__name__
                    st.markdown(f"- `{f}` *({vtype})*")
            with col_b:
                st.markdown("**Muestra (primer item):**")
                st.json(info["sample"])

    # ── Export JSON ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💾 Descargar resultados")
    st.markdown(
        "Descargá el archivo y compartilo para que pueda construir el dashboard "
        "con los **campos y estructuras reales** de tu cuenta Botmaker."
    )

    export_payload = {
        "meta": {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "base_url": BASE_URL,
            "total_endpoints": len(results),
            "ok": ok_count,
            "errors": err_count,
            "skipped": skip_count,
        },
        "endpoints": results,
        "schema_summary": {
            k: {"label": v["label"], "item_count": v["item_count"], "fields": v["fields"]}
            for k, v in schema_summary.items()
        },
    }

    json_str = json.dumps(export_payload, indent=2, ensure_ascii=False, default=str)

    st.download_button(
        label="⬇️ Descargar botmaker_responses.json",
        data=json_str,
        file_name=f"botmaker_responses_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
    )

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Una vez descargado el archivo:**")
        st.markdown("""
        1. Descargá `botmaker_responses.json`
        2. Subilo a esta conversación
        3. Pedime que construya el dashboard con los datos reales
        """)
    with col_r:
        st.markdown("**El JSON incluye:**")
        st.markdown("""
        - Respuesta completa de cada endpoint
        - Schema de campos por endpoint
        - Conteos y metadata
        - Tiempos de respuesta
        """)

    status_box.success("✅ Extracción completada")

elif not token:
    st.markdown("""
    <div style="background:#111318;border:1px solid #1e2230;border-radius:10px;
                padding:32px;text-align:center;color:#6b7280;">
        <div style="font-size:3rem;margin-bottom:12px;">🔑</div>
        <div style="font-family:'Space Mono',monospace;color:#e2e8f0;margin-bottom:8px;">
            Ingresá tu Access Token para comenzar
        </div>
        Encontralo en tu cuenta Botmaker → <strong>Settings → API</strong>
    </div>
    """, unsafe_allow_html=True)

# ── Footer info ──────────────────────────────────────────────────────────────
with st.expander("📋 Lista completa de endpoints que se van a llamar"):
    endpoints_doc = [
        ("GET", "agents",                            "Lista todos los agentes"),
        ("GET", "agents?online=true",                "Agentes en línea"),
        ("GET", "channels",                          "Todos los canales"),
        ("GET", "channels?active=true",              "Canales activos"),
        ("GET", "roles",                             "Roles customizados"),
        ("GET", "intents",                           "Todos los intents"),
        ("GET", "webhooks",                          "Webhooks configurados"),
        ("GET", "whatsapp/templates",                "Templates de WhatsApp"),
        ("GET", "whatsapp/accounts",                 "Cuentas de WhatsApp"),
        ("GET", "commerce/catalogs",                 "Catálogos de comercio"),
        ("GET", "messages",                          "Mensajes recientes"),
        ("GET", "messages?chat-platform=whatsapp",   "Mensajes de WhatsApp"),
        ("GET", "sessions",                          "Sesiones recientes"),
        ("GET", "chats",                             "Lista de chats"),
        ("GET", "billing/whatsapp/conversations",    "Conversaciones facturadas"),
        ("GET", "audits/agent",                      "Auditoría de agentes"),
        ("GET", "audits/intent",                     "Auditoría de intents"),
        ("GET", "calls",                             "Lista de llamadas"),
        ("GET", "chats/{chatId}",                    "Detalle de chat (ID dinámico)"),
        ("GET", "roles/{roleId}",                    "Detalle de rol (ID dinámico)"),
        ("GET", "intents/{intentId}",                "Detalle de intent (ID dinámico)"),
        ("GET", "webhooks/{webhookId}",              "Detalle de webhook (ID dinámico)"),
        ("GET", "whatsapp/templates/{name}",         "Template por nombre (ID dinámico)"),
        ("GET", "whatsapp/accounts/{phone}",         "Cuenta WA por teléfono (ID dinámico)"),
        ("GET", "whatsapp/accounts/{phone}/health",  "Salud de cuenta WA (ID dinámico)"),
        ("GET", "commerce/catalogs/{id}/categories", "Categorías del catálogo (ID dinámico)"),
        ("GET", "commerce/catalogs/{id}/products",   "Productos del catálogo (ID dinámico)"),
    ]

    table_html = """
    <table style="width:100%;border-collapse:collapse;font-size:0.82rem;font-family:'Space Mono',monospace;">
    <tr style="border-bottom:1px solid #1e2230;color:#6b7280;">
        <th style="text-align:left;padding:8px 12px;">Método</th>
        <th style="text-align:left;padding:8px 12px;">Endpoint</th>
        <th style="text-align:left;padding:8px 12px;">Descripción</th>
    </tr>
    """
    for method, path, desc in endpoints_doc:
        color = "#10b981" if method == "GET" else "#f97316"
        table_html += f"""
        <tr style="border-bottom:1px solid #1a1f2a;">
            <td style="padding:6px 12px;color:{color};">{method}</td>
            <td style="padding:6px 12px;color:#93c5fd;">/v2.0/{path}</td>
            <td style="padding:6px 12px;color:#9ca3af;">{desc}</td>
        </tr>
        """
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)
