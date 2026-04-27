"""
botmaker_dashboard.py  ·  Kashio — Monitor en Vivo
Token desde st.secrets["BOTMAKER_TOKEN"]
Auto-refresh configurable + métricas de productividad por agente
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from collections import Counter
import json

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

BASE_URL = "https://api.botmaker.com/v2.0"

st.set_page_config(page_title="Kashio · Monitor", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")

# ─────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');
:root{--bg:#07080c;--s1:#0e1018;--s2:#141720;--border:#1e2333;
  --accent:#4f6ef7;--green:#22d47b;--orange:#f5a524;--red:#f25c5c;
  --purple:#a78bfa;--sky:#38bdf8;--text:#e6e8f0;--muted:#555e7a;}
html,body,[class*="css"]{font-family:'Inter',sans-serif;color:var(--text);}
.stApp{background:var(--bg);}
.stSidebar{background:var(--s1)!important;border-right:1px solid var(--border)!important;}

.kpi{background:var(--s1);border:1px solid var(--border);border-radius:14px;
  padding:20px 22px;position:relative;overflow:hidden;}
.kpi-accent{border-top:2px solid var(--accent);}
.kpi-green{border-top:2px solid var(--green);}
.kpi-orange{border-top:2px solid var(--orange);}
.kpi-red{border-top:2px solid var(--red);}
.kpi-purple{border-top:2px solid var(--purple);}
.kpi-sky{border-top:2px solid var(--sky);}
.kpi-label{font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
.kpi-value{font-family:'Syne',sans-serif;font-size:2.4rem;font-weight:800;line-height:1;margin:8px 0 4px;}
.kpi-sub{font-size:.75rem;color:var(--muted);}

.agent-card{background:var(--s1);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;display:flex;align-items:center;gap:14px;}
.agent-avatar{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-family:'Syne',sans-serif;font-weight:800;font-size:1rem;flex-shrink:0;}
.agent-name{font-size:.88rem;font-weight:600;color:var(--text);}
.agent-meta{font-size:.72rem;color:var(--muted);margin-top:2px;}
.agent-badge{margin-left:auto;padding:3px 10px;border-radius:20px;
  font-size:.68rem;font-weight:700;font-family:'Syne',sans-serif;white-space:nowrap;}
.online-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle;}

.sh{font-family:'Syne',sans-serif;font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;
  color:var(--muted);padding-bottom:8px;border-bottom:1px solid var(--border);margin:24px 0 14px;
  display:flex;align-items:center;justify-content:space-between;}

@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;
  background:#22d47b;animation:pulse 2s infinite;margin-right:6px;}

.stButton>button{background:var(--accent)!important;color:#fff!important;
  font-family:'Syne',sans-serif!important;font-weight:700!important;font-size:.82rem!important;
  border:none!important;border-radius:8px!important;padding:9px 22px!important;}
.stButton>button:hover{opacity:.82!important;}
.stSelectbox>div>div,.stNumberInput>div>div>input,.stDateInput>div>div>input{
  background:var(--s2)!important;border:1px solid var(--border)!important;
  color:var(--text)!important;border-radius:8px!important;}
.stTabs [data-baseweb="tab-list"]{background:var(--s1);border-radius:10px;
  padding:4px;border:1px solid var(--border);gap:3px;}
.stTabs [data-baseweb="tab"]{color:var(--muted)!important;font-family:'Syne',sans-serif!important;
  font-size:.77rem!important;border-radius:7px!important;}
.stTabs [aria-selected="true"]{background:var(--accent)!important;color:#fff!important;}
.stDataFrame{border-radius:10px;overflow:hidden;}
hr{border-color:var(--border);}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# TOKEN desde st.secrets
# ─────────────────────────────────────────────────────────
try:
    TOKEN = st.secrets["BOTMAKER_TOKEN"]
except Exception:
    st.error("⚠️ Token no configurado. Agregá `BOTMAKER_TOKEN` en Settings → Secrets de Streamlit.")
    st.code('[secrets]\nBOTMAKER_TOKEN = "tu_token_aqui"', language="toml")
    st.stop()

# ─────────────────────────────────────────────────────────
# PLOTLY THEME
# ─────────────────────────────────────────────────────────
LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8892aa", size=12),
    margin=dict(l=10, r=10, t=36, b=10),
    xaxis=dict(gridcolor="#1a1f2e", linecolor="#1a1f2e", zerolinecolor="#1a1f2e"),
    yaxis=dict(gridcolor="#1a1f2e", linecolor="#1a1f2e", zerolinecolor="#1a1f2e"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1a1f2e"),
    colorway=["#4f6ef7","#22d47b","#f5a524","#f25c5c","#a78bfa","#38bdf8"],
)
def pf(f): st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})

# ─────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────
def hdrs(): return {"access-token": TOKEN, "Content-Type": "application/json"}
def api_get(path, params=None):
    try:
        r = requests.get(f"{BASE_URL}/{path}", headers=hdrs(), params=params, timeout=20)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return -1, str(e)
def api_patch(path, body):
    try:
        r = requests.patch(f"{BASE_URL}/{path}", headers=hdrs(), json=body, timeout=20)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return -1, str(e)
def items(resp):
    if isinstance(resp, dict): return resp.get("items", [])
    if isinstance(resp, list): return resp
    return []

# ─────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────
def kpi_card(label, value, sub, css_class, color):
    st.markdown(f"""
    <div class="kpi kpi-{css_class}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" style="color:{color}">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def sh(text, right=""):
    st.markdown(f'<div class="sh"><span>{text}</span>'
                f'<span style="color:#555e7a;font-size:.68rem">{right}</span></div>',
                unsafe_allow_html=True)

AVATAR_COLORS = ["#4f6ef7","#22d47b","#f5a524","#a78bfa","#38bdf8","#f25c5c","#fb923c","#e879f9"]

def agent_card(ag, chats_count):
    is_online = ag.get("isOnline", False)
    status    = ag.get("status", "—")
    name      = ag.get("name", "Agente")
    initials  = "".join(w[0].upper() for w in name.split()[:2])
    idx       = abs(hash(ag.get("id", ""))) % len(AVATAR_COLORS)
    av_color  = AVATAR_COLORS[idx]
    dot_color = "#22d47b" if is_online else "#555e7a"

    if is_online:
        badge_s = "background:rgba(34,212,123,.12);color:#22d47b;border:1px solid rgba(34,212,123,.3)"
        badge_t = "EN LÍNEA"
    elif status == "busy":
        badge_s = "background:rgba(245,165,36,.12);color:#f5a524;border:1px solid rgba(245,165,36,.3)"
        badge_t = "OCUPADO"
    else:
        badge_s = "background:rgba(85,94,122,.12);color:#8892aa;border:1px solid rgba(85,94,122,.2)"
        badge_t = "OFFLINE"

    queues = ", ".join(ag.get("queues", [])) or "—"
    slots  = ag.get("slots", 0)
    prio   = ag.get("priority","—")
    st.markdown(f"""
    <div class="agent-card">
      <div class="agent-avatar"
           style="background:{av_color}22;color:{av_color};border:1.5px solid {av_color}44">
        {initials}
      </div>
      <div style="flex:1;min-width:0">
        <div class="agent-name">
          <span class="online-dot" style="background:{dot_color}"></span>{name}
        </div>
        <div class="agent-meta">
          Queues: {queues}&nbsp;·&nbsp;Slots: {slots}&nbsp;·&nbsp;
          Prioridad: {prio}&nbsp;·&nbsp;Chats activos: <strong style="color:#e6e8f0">{chats_count}</strong>
        </div>
      </div>
      <span class="agent-badge" style="{badge_s}">{badge_t}</span>
    </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:10px 0 18px">
      <div style="font-family:'Syne',sans-serif;font-size:1.35rem;font-weight:800">⚡ Kashio</div>
      <div style="font-size:.68rem;color:#555e7a;letter-spacing:.1em">BOTMAKER · MONITOR</div>
    </div>""", unsafe_allow_html=True)

    page = st.radio("", [
        "🔴  Monitor en vivo",
        "📈  Productividad agentes",
        "🗂  Sesiones",
        "🎯  Intents & Canales",
        "📋  Templates WA",
    ], label_visibility="collapsed")

    st.markdown('<hr style="margin:10px 0">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.7rem;color:#555e7a;letter-spacing:.08em;'
                'text-transform:uppercase;margin-bottom:8px">Auto-refresco</div>',
                unsafe_allow_html=True)

    refresh_map   = {"Manual":0, "30 seg":30, "1 min":60, "2 min":120, "5 min":300}
    refresh_label = st.selectbox("", list(refresh_map.keys()), index=1, label_visibility="collapsed")
    refresh_secs  = refresh_map[refresh_label]

    if refresh_secs > 0 and HAS_AUTOREFRESH:
        st_autorefresh(interval=refresh_secs * 1000, limit=None, key="autoref")
        st.markdown(f'<div style="font-size:.72rem;color:#22d47b;margin-top:4px">'
                    f'<span class="live-dot"></span>Actualizando cada {refresh_label}</div>',
                    unsafe_allow_html=True)
    elif refresh_secs > 0 and not HAS_AUTOREFRESH:
        st.caption("Instalá `streamlit-autorefresh` en requirements.txt para esta función.")
    else:
        if st.button("🔄 Refrescar ahora"):
            st.rerun()

    now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    st.markdown(f'<div style="font-size:.68rem;color:#555e7a;margin-top:8px">Última carga: {now_utc}</div>',
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# PAGE: MONITOR EN VIVO
# ══════════════════════════════════════════════════════════
if page == "🔴  Monitor en vivo":
    st.markdown("""
    <h2 style="font-family:'Syne',sans-serif;font-weight:800;margin-bottom:2px">
      <span class="live-dot"></span>Monitor en vivo
    </h2>
    <div style="color:#555e7a;font-size:.82rem;margin-bottom:20px">
      Chats activos · Estado de agentes en tiempo real
    </div>""", unsafe_allow_html=True)

    now_utc  = datetime.now(timezone.utc)
    from_24h = (now_utc - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with st.spinner("Cargando datos en vivo…"):
        sc_ag,  d_ag  = api_get("agents")
        sc_ag2, d_ag2 = api_get("agents", {"online": "true"})
        sc_ch,  d_ch  = api_get("chats",  {"from": from_24h})

    ag_list  = items(d_ag)  if sc_ag  == 200 else []
    ag_on    = items(d_ag2) if sc_ag2 == 200 else []
    cht_list = items(d_ch)  if sc_ch  == 200 else []

    # ── Métricas calculadas con campos reales ─────────────
    sin_asignar = [c for c in cht_list if not c.get("agentId")]
    soporte_n1  = [c for c in cht_list if c.get("queueId") == "Soporte N1"]
    comercial   = [c for c in cht_list if c.get("queueId") == "Comercial"]
    default_q   = [c for c in cht_list if c.get("queueId") == "_default_"]
    # Pendientes: bot silenciado + agente asignado = usuario esperando respuesta del agente
    pendientes  = [c for c in cht_list if c.get("isBotMuted") and c.get("agentId")]
    # Ventana WA activa
    now_iso     = now_utc.isoformat()[:19]
    wa_window   = [c for c in cht_list
                   if c.get("whatsAppWindowCloseDatetime","") > now_iso]

    # ── KPI row ───────────────────────────────────────────
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: kpi_card("Sin asignar",      len(sin_asignar), "sin agentId",             "red",    "#f25c5c")
    with k2: kpi_card("Soporte N1",       len(soporte_n1),  "en cola Soporte",         "orange", "#f5a524")
    with k3: kpi_card("Comercial",        len(comercial),   "en cola Comercial",       "accent", "#4f6ef7")
    with k4: kpi_card("Cola _default_",   len(default_q),   "sin cola específica",     "purple", "#a78bfa")
    with k5: kpi_card("Pend. responder",  len(pendientes),  "bot muted + agente",      "sky",    "#38bdf8")
    with k6: kpi_card("Agentes online",   len(ag_on),       f"de {len(ag_list)} total","green",  "#22d47b")

    st.markdown("")

    # ── ESTADO DE AGENTES ─────────────────────────────────
    sh("Estado de agentes", f"{len(ag_on)} en línea · {len(ag_list)} total")
    chats_x_agent = Counter(c.get("agentId","") for c in cht_list if c.get("agentId"))

    # Ordenar: online → busy → offline
    ag_sorted = sorted(ag_list, key=lambda a: (0 if a.get("isOnline") else (1 if a.get("status")=="busy" else 2)))

    cols = st.columns(3)
    for i, ag in enumerate(ag_sorted):
        with cols[i % 3]:
            agent_card(ag, chats_x_agent.get(ag.get("id",""), 0))
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    st.markdown("")

    # ── CHATS SIN ASIGNAR ─────────────────────────────────
    col_l, col_r = st.columns([3, 2])

    with col_l:
        sh(f"Chats sin asignar — {len(sin_asignar)}", "sin agentId · últimas 24h")
        if sin_asignar:
            ag_map = {a["id"]: a["name"] for a in ag_list}
            rows = []
            for c in sin_asignar:
                ci  = c.get("chat", {})
                wd  = c.get("whatsAppWindowCloseDatetime", "")
                rows.append({
                    "Nombre":     c.get("firstName", "—"),
                    "País":       c.get("country", "—"),
                    "Queue":      c.get("queueId", "—"),
                    "Ventana WA": "✅" if wd > now_iso else "❌",
                    "Bot muted":  "Sí" if c.get("isBotMuted") else "No",
                    "Último msg": c.get("lastUserMessageDatetime","")[:16].replace("T"," "),
                    "Chat ID":    ci.get("chatId","")[:14]+"…",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38, 420))
        else:
            st.success("✅ No hay chats sin asignar en las últimas 24h.")

    with col_r:
        sh("Distribución por queue")
        if cht_list:
            q_counts = Counter(c.get("queueId") or "Sin queue" for c in cht_list)
            q_df = pd.DataFrame({"Queue": list(q_counts.keys()), "n": list(q_counts.values())})
            f1 = px.pie(q_df, names="Queue", values="n", hole=0.58,
                        color_discrete_map={"_default_":"#4f6ef7","Soporte N1":"#f5a524",
                                            "Comercial":"#22d47b","Sin queue":"#555e7a"})
            f1.update_layout(**LAYOUT, margin=dict(l=0,r=0,t=10,b=0))
            pf(f1)

        sh("Bot activo vs silenciado")
        if cht_list:
            m_counts = Counter("Silenciado" if c.get("isBotMuted") else "Bot activo" for c in cht_list)
            f2 = go.Figure(go.Bar(
                x=list(m_counts.keys()), y=list(m_counts.values()),
                marker_color=["#f25c5c" if k=="Silenciado" else "#22d47b" for k in m_counts.keys()],
                text=list(m_counts.values()), textposition="outside",
            ))
            f2.update_layout(**LAYOUT, showlegend=False, margin=dict(l=10,r=10,t=10,b=30))
            f2.update_traces(marker_cornerradius=6)
            pf(f2)

    # ── PENDIENTES DE RESPONDER ───────────────────────────
    sh(f"Pendientes de responder — {len(pendientes)}", "bot silenciado + agente asignado")
    if pendientes:
        ag_map = {a["id"]: a["name"] for a in ag_list}
        rows = []
        for c in pendientes:
            ci   = c.get("chat", {})
            agid = c.get("agentId","")
            rows.append({
                "Agente":     ag_map.get(agid, agid[:12]+"…") if agid else "—",
                "Nombre":     c.get("firstName","—"),
                "País":       c.get("country","—"),
                "Queue":      c.get("queueId","—"),
                "Último msg": c.get("lastUserMessageDatetime","")[:16].replace("T"," "),
                "Chat ID":    ci.get("chatId","")[:14]+"…",
            })
        col_t, col_c = st.columns([3,2])
        with col_t:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38, 380))
        with col_c:
            by_ag = Counter(r["Agente"] for r in rows)
            f3 = px.bar(
                x=list(by_ag.values()), y=list(by_ag.keys()), orientation="h",
                color=list(by_ag.values()),
                color_continuous_scale=["#1a1f2e","#38bdf8"],
                title="Pendientes por agente",
            )
            f3.update_layout(**LAYOUT, coloraxis_showscale=False, margin=dict(l=130,r=10,t=36,b=10))
            f3.update_traces(marker_cornerradius=4)
            pf(f3)
    else:
        st.success("✅ No hay chats pendientes de respuesta.")


# ══════════════════════════════════════════════════════════
# PAGE: PRODUCTIVIDAD AGENTES
# ══════════════════════════════════════════════════════════
elif page == "📈  Productividad agentes":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Productividad de agentes</h2>',
                unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    with c1: d_from = st.date_input("Desde", value=datetime.now()-timedelta(days=7))
    with c2: d_to   = st.date_input("Hasta", value=datetime.now())
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        load = st.button("🔄 Cargar datos")

    if load:
        with st.spinner("Cargando…"):
            sc_ag,  d_ag  = api_get("agents")
            sc_ses, d_ses = api_get("sessions", {
                "from": d_from.strftime("%Y-%m-%dT00:00:00Z"),
                "to":   d_to.strftime("%Y-%m-%dT23:59:59Z"),
                "include-events": "true",
            })
            sc_cht, d_cht = api_get("chats", {"from": d_from.strftime("%Y-%m-%dT00:00:00Z")})

        ag_list  = items(d_ag)  if sc_ag  == 200 else []
        ses_list = items(d_ses) if sc_ses == 200 else []
        cht_list = items(d_cht) if sc_cht == 200 else []

        ag_map = {a["id"]: a for a in ag_list}

        # ── Productividad desde eventos de sesión ─────────
        # Campos reales usados: events[].name, events[].info.agentId, events[].info.agentName
        prod = {}
        timeline_rows = []

        for s in ses_list:
            for e in s.get("events", []):
                info    = e.get("info", {})
                ev_name = e.get("name", "")
                ag_name = info.get("agentName", "")
                ag_id   = info.get("agentId", "")
                ev_date = e.get("creationTime","")[:10]
                if not ag_name:
                    continue
                if ag_name not in prod:
                    prod[ag_name] = {"agentId":ag_id,"asignaciones":0,"acciones":0,"cierres":0}
                if ev_name == "assigned-to-agent":
                    prod[ag_name]["asignaciones"] += 1
                    timeline_rows.append({"fecha":ev_date,"agente":ag_name,"tipo":"asignación"})
                elif ev_name == "agent-action":
                    prod[ag_name]["acciones"] += 1
                elif ev_name == "conversation-close":
                    prod[ag_name]["cierres"] += 1

        chats_x_agent = Counter(c.get("agentId","") for c in cht_list if c.get("agentId"))

        prod_rows = []
        for name, m in prod.items():
            ag_info   = ag_map.get(m["agentId"], {})
            chats_now = chats_x_agent.get(m["agentId"], 0)
            eficiencia = round(100 * m["cierres"] / m["asignaciones"], 1) if m["asignaciones"] > 0 else 0
            prod_rows.append({
                "Nombre":          name,
                "isOnline":        ag_info.get("isOnline", False),
                "Status":          ag_info.get("status", "—"),
                "Queues":          ", ".join(ag_info.get("queues", [])),
                "Chats activos":   chats_now,
                "Asignaciones":    m["asignaciones"],
                "Acciones":        m["acciones"],
                "Cierres conv.":   m["cierres"],
                "Eficiencia %":    eficiencia,
            })
        prod_rows.sort(key=lambda x: x["Asignaciones"], reverse=True)

        if not prod_rows:
            st.info("Sin datos de productividad para ese período.")
        else:
            # KPIs
            total_asig  = sum(r["Asignaciones"]  for r in prod_rows)
            total_acc   = sum(r["Acciones"]       for r in prod_rows)
            total_close = sum(r["Cierres conv."]  for r in prod_rows)
            top_agent   = prod_rows[0]["Nombre"]

            k1,k2,k3,k4 = st.columns(4)
            with k1: kpi_card("Asignaciones totales", total_asig,  f"{d_from}–{d_to}", "accent","#4f6ef7")
            with k2: kpi_card("Acciones totales",     total_acc,   "agent-action events","green","#22d47b")
            with k3: kpi_card("Conversaciones cerradas", total_close, "conversation-close","orange","#f5a524")
            with k4: kpi_card("Agente más activo",    top_agent,   f"{prod_rows[0]['Asignaciones']} asig.","purple","#a78bfa")

            st.markdown("")
            col_l, col_r = st.columns(2)

            with col_l:
                sh("Asignaciones por agente")
                f1 = px.bar(
                    x=[r["Asignaciones"] for r in prod_rows],
                    y=[r["Nombre"]       for r in prod_rows],
                    orientation="h",
                    color=[r["Asignaciones"] for r in prod_rows],
                    color_continuous_scale=["#1a1f2e","#4f6ef7"],
                )
                f1.update_layout(**LAYOUT, coloraxis_showscale=False, margin=dict(l=150,r=10,t=10,b=10))
                f1.update_traces(marker_cornerradius=4)
                pf(f1)

                sh("Acciones vs cierres por agente")
                f2 = go.Figure()
                f2.add_trace(go.Bar(name="Acciones", x=[r["Nombre"] for r in prod_rows],
                                    y=[r["Acciones"] for r in prod_rows],
                                    marker_color="#4f6ef7", marker_cornerradius=4))
                f2.add_trace(go.Bar(name="Cierres",  x=[r["Nombre"] for r in prod_rows],
                                    y=[r["Cierres conv."] for r in prod_rows],
                                    marker_color="#22d47b", marker_cornerradius=4))
                f2.update_layout(**LAYOUT, barmode="group")
                pf(f2)

            with col_r:
                sh("Eficiencia de cierre (%)")
                f3 = px.bar(
                    x=[r["Eficiencia %"] for r in prod_rows],
                    y=[r["Nombre"]       for r in prod_rows],
                    orientation="h",
                    color=[r["Eficiencia %"] for r in prod_rows],
                    color_continuous_scale=["#f25c5c","#f5a524","#22d47b"],
                )
                f3.update_layout(**LAYOUT, coloraxis_showscale=False, margin=dict(l=150,r=10,t=10,b=10))
                f3.update_traces(marker_cornerradius=4)
                pf(f3)

                sh("Distribución de asignaciones")
                f4 = px.pie(
                    names=[r["Nombre"]       for r in prod_rows],
                    values=[r["Asignaciones"] for r in prod_rows],
                    hole=0.55,
                )
                f4.update_layout(**LAYOUT, margin=dict(l=0,r=0,t=10,b=0))
                pf(f4)

            sh("Tabla de productividad por agente")
            df_display = pd.DataFrame(prod_rows).copy()
            df_display["isOnline"] = df_display["isOnline"].map({True:"🟢 Sí", False:"⚫ No"})
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            sh("Asignaciones por día — timeline")
            if timeline_rows:
                df_tl = pd.DataFrame(timeline_rows)
                pivot = df_tl.groupby(["fecha","agente"]).size().reset_index(name="n")
                f5 = px.bar(pivot, x="fecha", y="n", color="agente", barmode="stack")
                f5.update_layout(**LAYOUT)
                f5.update_traces(marker_cornerradius=3)
                pf(f5)


# ══════════════════════════════════════════════════════════
# PAGE: SESIONES
# ══════════════════════════════════════════════════════════
elif page == "🗂  Sesiones":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Sesiones</h2>',
                unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    with c1: d_from = st.date_input("Desde", value=datetime.now()-timedelta(days=7))
    with c2: d_to   = st.date_input("Hasta", value=datetime.now())
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        load = st.button("🔄 Cargar sesiones")

    if load:
        with st.spinner("Cargando…"):
            sc, d = api_get("sessions", {
                "from": d_from.strftime("%Y-%m-%dT00:00:00Z"),
                "to":   d_to.strftime("%Y-%m-%dT23:59:59Z"),
                "include-events": "true",
            })
        if sc == 200:
            ses = items(d)
            all_ev = [e["name"] for s in ses for e in s.get("events",[])]
            organic = sum(1 for s in ses if s.get("startingCause")=="Organic")
            wa_tpl  = sum(1 for s in ses if s.get("startingCause")=="WhatsAppTemplate")

            k1,k2,k3,k4 = st.columns(4)
            with k1: kpi_card("Sesiones totales", len(ses),    f"{d_from}–{d_to}","accent","#4f6ef7")
            with k2: kpi_card("Orgánicas",         organic,    "Organic","green","#22d47b")
            with k3: kpi_card("Vía Template WA",   wa_tpl,     "WhatsAppTemplate","orange","#f5a524")
            with k4: kpi_card("Eventos totales",   len(all_ev),"","purple","#a78bfa")

            st.markdown("")
            col_l, col_r = st.columns(2)
            with col_l:
                sh("Sesiones por día y origen")
                df = pd.DataFrame(ses)
                df["ts"] = pd.to_datetime(df["creationTime"], errors="coerce")
                by_day = df.groupby([df["ts"].dt.date,"startingCause"]).size().reset_index(name="n")
                by_day.columns = ["Fecha","Origen","n"]
                f1 = px.bar(by_day, x="Fecha", y="n", color="Origen", barmode="stack",
                            color_discrete_map={"Organic":"#4f6ef7","WhatsAppTemplate":"#f5a524"})
                f1.update_layout(**LAYOUT); f1.update_traces(marker_cornerradius=3)
                pf(f1)

            with col_r:
                sh("Tipos de evento")
                ev_df = pd.Series(all_ev).value_counts().reset_index()
                ev_df.columns = ["Evento","n"]
                f2 = px.bar(ev_df, x="n", y="Evento", orientation="h",
                            color="n", color_continuous_scale=["#1a1f2e","#a78bfa"])
                f2.update_layout(**LAYOUT, coloraxis_showscale=False,
                                 margin=dict(l=170,r=10,t=10,b=10))
                f2.update_traces(marker_cornerradius=3)
                pf(f2)

            sh("Detalle de sesiones")
            rows = [{"Fecha":s.get("creationTime","")[:16].replace("T"," "),
                     "Origen":s.get("startingCause",""),
                     "Nombre":s.get("chat",{}).get("firstName",""),
                     "Contacto":s.get("chat",{}).get("chat",{}).get("contactId",""),
                     "Canal":s.get("chat",{}).get("chat",{}).get("channelId","").split("-")[-1],
                     "Eventos":len(s.get("events",[]))} for s in ses[:300]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.error(f"Error {sc}: {d}")


# ══════════════════════════════════════════════════════════
# PAGE: INTENTS & CANALES
# ══════════════════════════════════════════════════════════
elif page == "🎯  Intents & Canales":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Intents & Canales</h2>',
                unsafe_allow_html=True)
    if st.button("🔄 Cargar"):
        with st.spinner("Cargando…"):
            sc_in, d_in = api_get("intents")
            sc_ch, d_ch = api_get("channels")
        col_l, col_r = st.columns(2)
        with col_l:
            sh("Intents")
            if sc_in == 200:
                ilist = items(d_in)
                active = sum(1 for i in ilist if i.get("active"))
                kpi_card("Intents activos", active, f"de {len(ilist)} totales","green","#22d47b")
                st.markdown("")
                all_topics = [t for i in ilist for t in i.get("topics",[])]
                top_df = pd.Series(all_topics).value_counts().head(12).reset_index()
                top_df.columns = ["Topic","n"]
                f1 = px.bar(top_df, x="n", y="Topic", orientation="h",
                            color="n", color_continuous_scale=["#1a1f2e","#a78bfa"])
                f1.update_layout(**LAYOUT, coloraxis_showscale=False, margin=dict(l=160,r=10,t=10,b=10))
                f1.update_traces(marker_cornerradius=3)
                pf(f1)
        with col_r:
            sh("Canales")
            if sc_ch == 200:
                chs = items(d_ch)
                kpi_card("Canales", len(chs), f"{sum(1 for c in chs if c.get('active'))} activos","sky","#38bdf8")
                st.markdown("")
                plat = pd.Series([c.get("platform","") for c in chs]).value_counts().reset_index()
                plat.columns = ["Plataforma","n"]
                f2 = px.bar(plat, x="Plataforma", y="n", color="Plataforma",
                            color_discrete_sequence=["#4f6ef7","#22d47b","#f5a524","#f25c5c","#a78bfa","#38bdf8","#fb923c"])
                f2.update_layout(**LAYOUT); f2.update_traces(marker_cornerradius=5)
                pf(f2)
                rows = [{"ID":c["id"],"Plataforma":c["platform"],"Activo":"✅" if c.get("active") else "❌","Número":c.get("number","")} for c in chs]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# PAGE: TEMPLATES WA
# ══════════════════════════════════════════════════════════
elif page == "📋  Templates WA":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Templates WhatsApp</h2>',
                unsafe_allow_html=True)
    if st.button("🔄 Cargar templates"):
        with st.spinner("Cargando…"):
            sc, d = api_get("whatsapp/templates")
        if sc == 200:
            tpls = items(d)
            k1,k2,k3 = st.columns(3)
            with k1: kpi_card("Templates",  len(tpls), "","accent","#4f6ef7")
            with k2: kpi_card("Marketing",  sum(1 for t in tpls if t.get("category")=="MARKETING"),"","orange","#f5a524")
            with k3: kpi_card("Utility",    sum(1 for t in tpls if t.get("category")=="UTILITY"),"","sky","#38bdf8")
            st.markdown("")
            col_l, col_r = st.columns(2)
            with col_l:
                cat_df = pd.Series([t.get("category","") for t in tpls]).value_counts().reset_index()
                cat_df.columns = ["Categoría","n"]
                f = px.pie(cat_df, names="Categoría", values="n", hole=0.55,
                           color_discrete_map={"MARKETING":"#f5a524","UTILITY":"#4f6ef7"})
                f.update_layout(**LAYOUT)
                pf(f)
            with col_r:
                rows = [{"Nombre":t.get("name",""),"Estado":t.get("state",""),
                         "Categoría":t.get("category",""),"Idioma":t.get("locale",""),
                         "Botones":len(t.get("buttons",[]) or [])} for t in tpls]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            sh("Vista previa (primeros 5)")
            for t in tpls[:5]:
                body_txt = t.get("body",{}).get("text","") if isinstance(t.get("body"),dict) else ""
                with st.expander(f"📄 {t.get('name','')} · {t.get('category','')}"):
                    st.write(body_txt)
                    for b in (t.get("buttons",[]) or []):
                        st.markdown(f"- `{b.get('type','')}` **{b.get('text','')}**"
                                    + (f" → {b.get('url','')}" if b.get("url") else ""))
        else:
            st.error(f"Error {sc}: {d}")
