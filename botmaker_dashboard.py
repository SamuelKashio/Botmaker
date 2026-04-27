"""
botmaker_dashboard.py  ·  Kashio — Monitor en Vivo
Token desde st.secrets["BOTMAKER_TOKEN"]
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
import json

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

BASE_URL = "https://api.botmaker.com/v2.0"

# ── Lima = UTC-5 ─────────────────────────────────────────
LIMA_OFFSET = timedelta(hours=-5)

def to_lima(dt_utc: datetime) -> datetime:
    return dt_utc + LIMA_OFFSET

# ── Turnos ───────────────────────────────────────────────
# Formato: (nombre, [dias_semana 0=lun…6=dom], hora_inicio, hora_fin_exclusiva)
# hora_fin puede ser < hora_inicio cuando el turno cruza medianoche
SHIFTS = [
    ("Alonso Loyola",      [0,1,2,3,4],  6, 14),
    ("José Luis Cahuana",  [0,1,2,3,4], 14, 22),
    ("Deivy Chavez Trejo", [0,1,2,3,4], 22,  6),  # 22→06 siguiente día
    ("Daniel Huayta",      [5,6],        6, 14),
    ("Luz Goicochea",      [5,6],       14, 22),
    ("Joe Villanueva",     [5,6],       22,  6),   # 22→06 siguiente día
    ("Victor Macedo",      [0,1,2,3,4],  9, 18),  # Comercial mañana
    ("José Luis Cahuana",  [0,1,2,3,4],  9, 18),  # Comercial tarde (comparten franja)
]

def get_shift_label(dt_utc: datetime) -> str:
    """Retorna el nombre del turno responsable para un datetime UTC."""
    lima = to_lima(dt_utc)
    wd   = lima.weekday()   # 0=lunes
    h    = lima.hour
    is_we = wd in [5, 6]

    if not is_we:          # Lun–Vie
        if  6 <= h < 14:  return "Alonso Loyola"
        if 14 <= h < 22:  return "José Luis Cahuana"
        return "Deivy Chavez Trejo"  # 22–06
    else:                  # Sáb–Dom
        if  6 <= h < 14:  return "Daniel Huayta"
        if 14 <= h < 22:  return "Luz Goicochea"
        return "Joe Villanueva"       # 22–06

SHIFT_SCHEDULE = [
    ("Alonso Loyola",      "Lun–Vie", "06:00–14:00", "Mañana"),
    ("José Luis Cahuana",  "Lun–Vie", "14:00–22:00", "Tarde"),
    ("Deivy Chavez Trejo", "Lun–Vie", "22:00–06:00", "Noche"),
    ("Daniel Huayta",      "Sáb–Dom", "06:00–14:00", "Mañana"),
    ("Luz Goicochea",      "Sáb–Dom", "14:00–22:00", "Tarde"),
    ("Joe Villanueva",     "Sáb–Dom", "22:00–06:00", "Noche"),
    ("Victor Macedo",      "Lun–Vie", "09:00–18:00", "Comercial"),
    ("José Luis Cahuana",  "Lun–Vie", "09:00–18:00", "Comercial"),
]

SHIFT_COLORS = {
    "Alonso Loyola":      "#4f6ef7",
    "José Luis Cahuana":  "#f5a524",
    "Deivy Chavez Trejo": "#a78bfa",
    "Daniel Huayta":      "#22d47b",
    "Luz Goicochea":      "#38bdf8",
    "Joe Villanueva":     "#f25c5c",
    "Victor Macedo":      "#fb923c",
}

# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="Kashio · Monitor", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

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

/* KPI */
.kpi{background:var(--s1);border:1px solid var(--border);border-radius:14px;padding:18px 20px;position:relative;}
.kpi-accent{border-top:2px solid #4f6ef7;} .kpi-green{border-top:2px solid #22d47b;}
.kpi-orange{border-top:2px solid #f5a524;} .kpi-red{border-top:2px solid #f25c5c;}
.kpi-purple{border-top:2px solid #a78bfa;} .kpi-sky{border-top:2px solid #38bdf8;}
.kpi-coral{border-top:2px solid #fb923c;}
.kpi-label{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
.kpi-value{font-family:'Syne',sans-serif;font-size:2.2rem;font-weight:800;line-height:1;margin:7px 0 3px;}
.kpi-sub{font-size:.73rem;color:var(--muted);}

/* Agente card */
.ac{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:13px 15px;display:flex;align-items:center;gap:12px;}
.av{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    font-family:'Syne',sans-serif;font-weight:800;font-size:.95rem;flex-shrink:0;}
.an{font-size:.86rem;font-weight:600;color:var(--text);}
.am{font-size:.7rem;color:var(--muted);margin-top:2px;}
.ab{margin-left:auto;padding:3px 9px;border-radius:20px;font-size:.67rem;font-weight:700;
    font-family:'Syne',sans-serif;white-space:nowrap;}
.od{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;}

/* Sección header */
.sh{font-family:'Syne',sans-serif;font-size:.67rem;letter-spacing:.13em;text-transform:uppercase;
    color:var(--muted);padding-bottom:7px;border-bottom:1px solid var(--border);margin:22px 0 13px;
    display:flex;align-items:center;justify-content:space-between;}

/* Alerta de tiempo */
.alert-row{background:rgba(242,92,92,.06);border:1px solid rgba(242,92,92,.2);
    border-radius:8px;padding:10px 14px;margin:4px 0;display:flex;align-items:center;gap:10px;}
.alert-time{font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:800;min-width:55px;}
.alert-info{font-size:.8rem;color:var(--text);}
.alert-sub{font-size:.7rem;color:var(--muted);margin-top:1px;}

/* Live */
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.ld{display:inline-block;width:8px;height:8px;border-radius:50%;background:#22d47b;
    animation:pulse 2s infinite;margin-right:6px;}

/* Turno badge */
.tb{display:inline-block;padding:2px 8px;border-radius:6px;font-size:.68rem;
    font-weight:700;font-family:'Syne',sans-serif;}

.stButton>button{background:#4f6ef7!important;color:#fff!important;font-family:'Syne',sans-serif!important;
    font-weight:700!important;font-size:.8rem!important;border:none!important;border-radius:8px!important;padding:8px 20px!important;}
.stButton>button:hover{opacity:.82!important;}
.stSelectbox>div>div,.stDateInput>div>div>input{background:var(--s2)!important;
    border:1px solid var(--border)!important;color:var(--text)!important;border-radius:8px!important;}
.stTabs [data-baseweb="tab-list"]{background:var(--s1);border-radius:10px;padding:4px;border:1px solid var(--border);gap:3px;}
.stTabs [data-baseweb="tab"]{color:var(--muted)!important;font-family:'Syne',sans-serif!important;font-size:.76rem!important;border-radius:7px!important;}
.stTabs [aria-selected="true"]{background:#4f6ef7!important;color:#fff!important;}
.stDataFrame{border-radius:10px;overflow:hidden;}
hr{border-color:var(--border);}

/* ── Live toggle ── */
[data-testid="stToggle"] > label {
  background: var(--s2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 20px !important;
  padding: 6px 14px !important;
  font-family: 'Syne', sans-serif !important;
  font-size: .8rem !important;
  font-weight: 700 !important;
  color: var(--muted) !important;
  transition: all .2s !important;
  cursor: pointer !important;
}
[data-testid="stToggle"][aria-checked="true"] > label {
  background: rgba(242,92,92,.12) !important;
  border-color: rgba(242,92,92,.4) !important;
  color: #f25c5c !important;
}
/* pulse the toggle label when on */
@keyframes live-pulse { 0%,100%{box-shadow:0 0 0 0 rgba(242,92,92,.4)} 50%{box-shadow:0 0 0 6px rgba(242,92,92,0)} }
[data-testid="stToggle"][aria-checked="true"] > label {
  animation: live-pulse 2s infinite !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# TOKEN
# ─────────────────────────────────────────────────────────
try:
    TOKEN = st.secrets["BOTMAKER_TOKEN"]
except Exception:
    st.error("⚠️ Falta `BOTMAKER_TOKEN` en Settings → Secrets.")
    st.code('[secrets]\nBOTMAKER_TOKEN = "tu_token_aqui"', language="toml")
    st.stop()

# ─────────────────────────────────────────────────────────
# PLOTLY
# ─────────────────────────────────────────────────────────
_BL = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8892aa", size=12),
    xaxis=dict(gridcolor="#1a1f2e", linecolor="#1a1f2e", zerolinecolor="#1a1f2e"),
    yaxis=dict(gridcolor="#1a1f2e", linecolor="#1a1f2e", zerolinecolor="#1a1f2e"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1a1f2e"),
    colorway=["#4f6ef7","#22d47b","#f5a524","#f25c5c","#a78bfa","#38bdf8","#fb923c"],
)
def L(**kw):
    r = dict(_BL)
    r.setdefault("margin", dict(l=10,r=10,t=36,b=10))
    r.update(kw)
    return r
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
def items(resp):
    if isinstance(resp, dict): return resp.get("items", [])
    if isinstance(resp, list): return resp
    return []

# ─────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────
def kpi(label, value, sub, cls, color):
    st.markdown(f"""<div class="kpi kpi-{cls}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" style="color:{color}">{value}</div>
      <div class="kpi-sub">{sub}</div></div>""", unsafe_allow_html=True)

def sh(txt, right=""):
    st.markdown(f'<div class="sh"><span>{txt}</span>'
                f'<span style="font-size:.67rem;color:#555e7a">{right}</span></div>',
                unsafe_allow_html=True)

AV_COLORS = ["#4f6ef7","#22d47b","#f5a524","#a78bfa","#38bdf8","#f25c5c","#fb923c","#e879f9"]

def fmt_hrs(h: float) -> str:
    if h >= 24: return f"{h/24:.1f}d"
    if h >= 1:  return f"{h:.1f}h"
    return f"{int(h*60)}m"

def sev_color(h: float) -> str:
    if h >= 48: return "#f25c5c"
    if h >= 24: return "#f5a524"
    if h >= 4:  return "#4f6ef7"
    return "#22d47b"

def agent_card(ag, chats_n, max_wait_h):
    is_online = ag.get("isOnline", False)
    status    = ag.get("status", "—")
    name      = ag.get("name", "Agente")
    initials  = "".join(w[0].upper() for w in name.split()[:2])
    idx       = abs(hash(ag.get("id",""))) % len(AV_COLORS)
    av_col    = AV_COLORS[idx]
    dot_col   = "#22d47b" if is_online else "#555e7a"

    if is_online:
        bs = "background:rgba(34,212,123,.12);color:#22d47b;border:1px solid rgba(34,212,123,.3)"
        bt = "EN LÍNEA"
    elif status == "busy":
        bs = "background:rgba(245,165,36,.12);color:#f5a524;border:1px solid rgba(245,165,36,.3)"
        bt = "OCUPADO"
    else:
        bs = "background:rgba(85,94,122,.12);color:#8892aa;border:1px solid rgba(85,94,122,.2)"
        bt = "OFFLINE"

    queues = ", ".join(ag.get("queues", [])) or "—"
    slots  = ag.get("slots", 0)
    prio   = ag.get("priority","—")

    # Métrica de espera
    if max_wait_h > 0:
        wc = sev_color(max_wait_h)
        wait_html = (f'<span style="font-size:.72rem;color:{wc};font-weight:700;'
                     f'margin-left:8px">⏱ {fmt_hrs(max_wait_h)} máx. espera</span>')
    else:
        wait_html = '<span style="font-size:.72rem;color:#555e7a;margin-left:8px">⏱ sin pendientes</span>'

    st.markdown(f"""
    <div class="ac">
      <div class="av" style="background:{av_col}22;color:{av_col};border:1.5px solid {av_col}44">{initials}</div>
      <div style="flex:1;min-width:0">
        <div class="an"><span class="od" style="background:{dot_col}"></span>{name}{wait_html}</div>
        <div class="am">Queues: {queues} · Slots: {slots} · Prioridad: {prio} · Chats activos: <b style="color:#e6e8f0">{chats_n}</b></div>
      </div>
      <span class="ab" style="{bs}">{bt}</span>
    </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="padding:10px 0 18px">
      <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800">⚡ Kashio</div>
      <div style="font-size:.67rem;color:#555e7a;letter-spacing:.1em">BOTMAKER · MONITOR</div>
    </div>""", unsafe_allow_html=True)

    page = st.radio("", [
        "🔴  Monitor en vivo",
        "⏱  Tiempo sin responder",
        "📋  Turnos & cobertura",
        "📈  Productividad agentes",
        "🗂  Sesiones",
        "🎯  Intents & Canales",
        "📋  Templates WA",
    ], label_visibility="collapsed")

    st.markdown('<hr style="margin:10px 0">', unsafe_allow_html=True)
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    st.markdown(f'<div style="font-size:.67rem;color:#555e7a">Última carga: {now_str}</div>',
                unsafe_allow_html=True)
    if page != "🔴  Monitor en vivo":
        st.markdown('<div style="font-size:.67rem;color:#555e7a;margin-top:4px">'
                    '⚡ Live mode disponible en Monitor</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# PAGE: MONITOR EN VIVO
# ══════════════════════════════════════════════════════════
if page == "🔴  Monitor en vivo":

    # ── LIVE toggle bar ──────────────────────────────────
    col_title, col_toggle, col_interval, col_refresh = st.columns([4, 1.2, 1.8, 1])

    with col_title:
        st.markdown("""<h2 style="font-family:'Syne',sans-serif;font-weight:800;margin-bottom:0;padding-top:6px">
          Monitor en vivo</h2>""", unsafe_allow_html=True)

    with col_toggle:
        live_on = st.toggle("🔴 LIVE", value=st.session_state.get("live_on", False), key="live_on")

    with col_interval:
        refresh_opts = {"30 seg": 30, "1 min": 60, "2 min": 120, "5 min": 300}
        if live_on:
            chosen = st.selectbox("Intervalo", list(refresh_opts.keys()),
                                  index=1, label_visibility="collapsed", key="live_interval")
            refresh_secs = refresh_opts[chosen]
        else:
            refresh_secs = 0
            st.markdown("")

    with col_refresh:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        if not live_on:
            if st.button("🔄 Refrescar"):
                st.rerun()

    # ── Ejecutar autorefresh SOLO si live está ON ────────
    if live_on and refresh_secs > 0:
        if HAS_AUTOREFRESH:
            st_autorefresh(interval=refresh_secs * 1000, limit=None, key="live_ar")
            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            st.markdown(
                f'<div style="font-size:.75rem;color:#22d47b;margin-bottom:12px">' +
                f'<span class="ld"></span>Actualizando cada {chosen} · {now_str}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning("Instalá `streamlit-autorefresh` en requirements.txt para usar Live mode.")
    elif live_on:
        st.markdown("")
    else:
        st.markdown(
            '<div style="font-size:.75rem;color:#555e7a;margin-bottom:12px">' +
            'Live mode desactivado · Usá el botón 🔄 para refrescar manualmente</div>',
            unsafe_allow_html=True,
        )

    now_utc  = datetime.now(timezone.utc)
    from_24h = (now_utc - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with st.spinner("Cargando…"):
        sc_ag,  d_ag  = api_get("agents")
        sc_ag2, d_ag2 = api_get("agents", {"online":"true"})
        sc_ch,  d_ch  = api_get("chats",  {"from": from_24h})

    ag_list  = items(d_ag)  if sc_ag  == 200 else []
    ag_on    = items(d_ag2) if sc_ag2 == 200 else []
    cht_list = items(d_ch)  if sc_ch  == 200 else []

    # ── Métricas ──
    sin_asignar = [c for c in cht_list if not c.get("agentId")]
    soporte_n1  = [c for c in cht_list if c.get("queueId") == "Soporte N1"]
    comercial   = [c for c in cht_list if c.get("queueId") == "Comercial"]
    default_q   = [c for c in cht_list if c.get("queueId") == "_default_"]
    pendientes  = [c for c in cht_list if c.get("isBotMuted") and c.get("agentId")]
    now_iso     = now_utc.isoformat()[:19]

    # Max espera por agente
    ag_map      = {a["id"]: a for a in ag_list}
    ag_max_wait = defaultdict(float)  # agentId -> horas
    for c in pendientes:
        lu = c.get("lastUserMessageDatetime","")
        if lu:
            try:
                dt  = datetime.fromisoformat(lu.replace("Z","+00:00"))
                hrs = (now_utc - dt).total_seconds() / 3600
                aid = c.get("agentId","")
                ag_max_wait[aid] = max(ag_max_wait[aid], hrs)
            except: pass

    # KPI row
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: kpi("Sin asignar",     len(sin_asignar), "sin agentId",            "red",    "#f25c5c")
    with k2: kpi("Soporte N1",      len(soporte_n1),  "en cola Soporte",        "orange", "#f5a524")
    with k3: kpi("Comercial",       len(comercial),   "en cola Comercial",      "accent", "#4f6ef7")
    with k4: kpi("Cola _default_",  len(default_q),   "sin cola específica",    "purple", "#a78bfa")
    with k5: kpi("Pend. responder", len(pendientes),  "bot muted + agente",     "sky",    "#38bdf8")
    with k6: kpi("Agentes online",  len(ag_on),       f"de {len(ag_list)} total","green", "#22d47b")

    st.markdown("")

    # ── ESTADO DE AGENTES (con tiempo máx. de espera) ──
    sh("Estado de agentes", f"{len(ag_on)} en línea · {len(ag_list)} total")
    chats_x_agent = Counter(c.get("agentId","") for c in cht_list if c.get("agentId"))
    ag_sorted = sorted(ag_list,
                       key=lambda a: (0 if a.get("isOnline") else (1 if a.get("status")=="busy" else 2)))
    cols = st.columns(3)
    for i, ag in enumerate(ag_sorted):
        aid = ag.get("id","")
        with cols[i % 3]:
            agent_card(ag, chats_x_agent.get(aid, 0), ag_max_wait.get(aid, 0))
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    st.markdown("")

    # ── CHATS SIN ASIGNAR ──
    col_l, col_r = st.columns([3, 2])
    with col_l:
        sh(f"Sin asignar — {len(sin_asignar)}", "sin agentId · últimas 24h")
        if sin_asignar:
            rows = []
            for c in sin_asignar:
                wd   = c.get("whatsAppWindowCloseDatetime","")
                rows.append({
                    "Nombre":     c.get("firstName","—"),
                    "País":       c.get("country","—"),
                    "Queue":      c.get("queueId","—"),
                    "Ventana WA": "✅" if wd > now_iso else "❌",
                    "Bot muted":  "Sí" if c.get("isBotMuted") else "No",
                    "Último msg": c.get("lastUserMessageDatetime","")[:16].replace("T"," "),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38, 400))
        else:
            st.success("✅ Sin chats sin asignar.")

    with col_r:
        sh("Por queue")
        if cht_list:
            qc = Counter(c.get("queueId") or "Sin queue" for c in cht_list)
            f1 = px.pie(pd.DataFrame({"Q":list(qc.keys()),"n":list(qc.values())}),
                        names="Q", values="n", hole=0.58,
                        color_discrete_map={"_default_":"#4f6ef7","Soporte N1":"#f5a524",
                                            "Comercial":"#22d47b","Sin queue":"#555e7a"})
            f1.update_layout(**L(margin=dict(l=0,r=0,t=10,b=0)))
            pf(f1)

        sh("Bot activo vs silenciado")
        mc = Counter("Silenciado" if c.get("isBotMuted") else "Bot activo" for c in cht_list)
        f2 = go.Figure(go.Bar(
            x=list(mc.keys()), y=list(mc.values()),
            marker_color=["#f25c5c" if k=="Silenciado" else "#22d47b" for k in mc.keys()],
            text=list(mc.values()), textposition="outside"))
        f2.update_layout(**L(showlegend=False, margin=dict(l=10,r=10,t=10,b=30)))
        f2.update_traces(marker_cornerradius=6)
        pf(f2)

    # ── PENDIENTES ──
    sh(f"Pendientes de responder — {len(pendientes)}", "bot silenciado + agente asignado")
    if pendientes:
        rows = []
        for c in pendientes:
            lu   = c.get("lastUserMessageDatetime","")
            hrs  = 0.0
            if lu:
                try:
                    dt  = datetime.fromisoformat(lu.replace("Z","+00:00"))
                    hrs = (now_utc - dt).total_seconds() / 3600
                except: pass
            aid  = c.get("agentId","")
            a    = ag_map.get(aid,{})
            rows.append({
                "⏱ Espera": fmt_hrs(hrs),
                "Horas":     round(hrs,1),
                "Agente":    a.get("name", aid[:12]+"…"),
                "Cliente":   c.get("firstName","—"),
                "País":      c.get("country","—"),
                "Queue":     c.get("queueId","—"),
                "Último msg":lu[:16].replace("T"," "),
            })
        rows.sort(key=lambda x: x["Horas"], reverse=True)
        col_t, col_c = st.columns([3,2])
        with col_t:
            df_show = pd.DataFrame(rows).drop(columns=["Horas"])
            st.dataframe(df_show, use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38, 380))
        with col_c:
            by_ag = defaultdict(float)
            for r in rows: by_ag[r["Agente"]] = max(by_ag[r["Agente"]], r["Horas"])
            f3 = go.Figure(go.Bar(
                x=list(by_ag.values()), y=list(by_ag.keys()),
                orientation="h",
                marker_color=[sev_color(v) for v in by_ag.values()],
                text=[fmt_hrs(v) for v in by_ag.values()],
                textposition="outside",
            ))
            f3.update_layout(**L(title="Máx. espera por agente",
                                  margin=dict(l=140,r=50,t=36,b=10), showlegend=False))
            f3.update_traces(marker_cornerradius=4)
            pf(f3)
    else:
        st.success("✅ Sin pendientes.")


# ══════════════════════════════════════════════════════════
# PAGE: TIEMPO SIN RESPONDER
# ══════════════════════════════════════════════════════════
elif page == "⏱  Tiempo sin responder":
    st.markdown("""<h2 style="font-family:'Syne',sans-serif;font-weight:800;margin-bottom:2px">
      ⏱ Tiempo sin responder</h2>
    <div style="color:#555e7a;font-size:.8rem;margin-bottom:18px">
      Conversaciones con bot silenciado y agente asignado que no han recibido respuesta</div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1: days_back = st.number_input("Últimos N días", min_value=1, max_value=30, value=7)
    with c2:
        warn_h  = st.number_input("Alerta desde (horas)", min_value=1, max_value=72, value=4)
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        load = st.button("🔄 Cargar")

    if load:
        now_utc  = datetime.now(timezone.utc)
        from_dt  = (now_utc - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with st.spinner("Cargando chats…"):
            sc_ag, d_ag = api_get("agents")
            sc_ch, d_ch = api_get("chats", {"from": from_dt})

        ag_list  = items(d_ag) if sc_ag == 200 else []
        cht_list = items(d_ch) if sc_ch == 200 else []
        ag_map   = {a["id"]: a for a in ag_list}

        # Solo pendientes (bot muted + agente + lastUserMessageDatetime)
        rows = []
        for c in cht_list:
            if not (c.get("isBotMuted") and c.get("agentId")): continue
            lu = c.get("lastUserMessageDatetime","")
            if not lu: continue
            try:
                dt  = datetime.fromisoformat(lu.replace("Z","+00:00"))
                hrs = (now_utc - dt).total_seconds() / 3600
            except: continue
            if hrs < warn_h: continue

            aid   = c.get("agentId","")
            ag    = ag_map.get(aid, {})
            lima_str = to_lima(dt).strftime("%d/%m %H:%M")
            rows.append({
                "hrs":        hrs,
                "⏱ Espera":   fmt_hrs(hrs),
                "Severidad":  "🔴 Crítico" if hrs >= 48 else ("🟠 Alto" if hrs >= 24 else ("🟡 Medio" if hrs >= 8 else "🔵 Bajo")),
                "Agente":     ag.get("name", aid[:12]+"…"),
                "Cliente":    c.get("firstName","—"),
                "País":       c.get("country","—"),
                "Queue":      c.get("queueId","—"),
                "Último msg (Lima)": lima_str,
                "Chat ID":    c.get("chat",{}).get("chatId","")[:14]+"…",
            })

        rows.sort(key=lambda x: x["hrs"], reverse=True)

        if not rows:
            st.success(f"✅ Ningún chat supera las {warn_h}h sin respuesta.")
        else:
            # KPIs
            k1,k2,k3,k4 = st.columns(4)
            criticos = sum(1 for r in rows if r["hrs"] >= 48)
            altos    = sum(1 for r in rows if 24 <= r["hrs"] < 48)
            medios   = sum(1 for r in rows if 8  <= r["hrs"] < 24)
            max_h    = rows[0]["hrs"]
            with k1: kpi("Conversaciones", len(rows), f"≥{warn_h}h sin respuesta","red","#f25c5c")
            with k2: kpi("Críticos ≥48h",  criticos,  "requieren atención urgente","red","#f25c5c")
            with k3: kpi("Altos 24–48h",   altos,     "","orange","#f5a524")
            with k4: kpi("Máx. espera",     fmt_hrs(max_h), rows[0]["Agente"],"purple","#a78bfa")

            st.markdown("")
            col_l, col_r = st.columns([2,3])

            with col_l:
                # Gauge máx espera
                sh("Conversación más antigua sin respuesta")
                max_row = rows[0]
                gauge_val = min(max_row["hrs"], 120)
                fig_g = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=round(max_row["hrs"],1),
                    number={"suffix":" h", "font":{"size":36,"color":sev_color(max_row["hrs"]),"family":"Syne"}},
                    delta={"reference": 24, "valueformat":".1f"},
                    gauge={
                        "axis":{"range":[0,120],"tickcolor":"#555e7a"},
                        "bar":{"color": sev_color(max_row["hrs"])},
                        "bgcolor":"#0e1018",
                        "borderwidth":0,
                        "steps":[
                            {"range":[0,4],   "color":"rgba(34,212,123,.12)"},
                            {"range":[4,24],  "color":"rgba(79,110,247,.12)"},
                            {"range":[24,48], "color":"rgba(245,165,36,.12)"},
                            {"range":[48,120],"color":"rgba(242,92,92,.12)"},
                        ],
                        "threshold":{"line":{"color":"#f25c5c","width":3},"thickness":0.8,"value":48},
                    },
                    title={"text": f"{max_row['Cliente']} · {max_row['Agente']}",
                           "font":{"size":12,"color":"#8892aa"}},
                ))
                fig_g.update_layout(**L(height=280, margin=dict(l=20,r=20,t=50,b=20)))
                pf(fig_g)

                # Distribución por severidad
                sh("Por severidad")
                sev_counts = Counter(r["Severidad"] for r in rows)
                sev_df = pd.DataFrame({"Severidad":list(sev_counts.keys()),
                                        "n":list(sev_counts.values())})
                f_sev = px.pie(sev_df, names="Severidad", values="n", hole=0.55,
                               color_discrete_map={
                                   "🔴 Crítico":"#f25c5c","🟠 Alto":"#f5a524",
                                   "🟡 Medio":"#4f6ef7","🔵 Bajo":"#22d47b"})
                f_sev.update_layout(**L(margin=dict(l=0,r=0,t=10,b=0)))
                pf(f_sev)

            with col_r:
                # Barras horizontales de espera por conversación (top 20)
                sh(f"Top {min(20,len(rows))} conversaciones — horas sin respuesta")
                df_bars = pd.DataFrame(rows[:20])
                df_bars["Label"] = df_bars["Cliente"] + " / " + df_bars["Agente"]
                f_bars = px.bar(
                    df_bars, x="hrs", y="Label", orientation="h",
                    color="hrs",
                    color_continuous_scale=["#22d47b","#4f6ef7","#f5a524","#f25c5c"],
                    color_continuous_midpoint=24,
                    text=df_bars["⏱ Espera"],
                )
                f_bars.update_layout(**L(coloraxis_showscale=False,
                                          margin=dict(l=180,r=60,t=10,b=10),
                                          height=max(300, len(rows[:20])*28+40)))
                f_bars.update_traces(marker_cornerradius=4, textposition="outside")
                pf(f_bars)

                # Espera por agente (boxplot / scatter)
                sh("Distribución de esperas por agente")
                df_ag = pd.DataFrame(rows)
                f_box = px.box(df_ag, x="Agente", y="hrs",
                               color="Agente",
                               color_discrete_map=SHIFT_COLORS,
                               points="all")
                f_box.update_layout(**L(showlegend=False,
                                         yaxis_title="Horas sin respuesta",
                                         margin=dict(l=10,r=10,t=10,b=60)))
                pf(f_box)

            # ── Tabla completa ──
            sh("Detalle completo de conversaciones sin responder")
            df_full = pd.DataFrame(rows).drop(columns=["hrs"])
            # Color rows by severity
            st.dataframe(df_full, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# PAGE: TURNOS & COBERTURA
# ══════════════════════════════════════════════════════════
elif page == "📋  Turnos & cobertura":
    st.markdown("""<h2 style="font-family:'Syne',sans-serif;font-weight:800;margin-bottom:2px">
      📋 Turnos & cobertura</h2>
    <div style="color:#555e7a;font-size:.8rem;margin-bottom:18px">
      Estadísticas de chats atendidos, asignados y respondidos por turno</div>
    """, unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    with c1: d_from = st.date_input("Desde", value=datetime.now()-timedelta(days=7))
    with c2: d_to   = st.date_input("Hasta", value=datetime.now())
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        load = st.button("🔄 Cargar")

    # ── Tabla de turnos ──
    sh("Horarios configurados")
    sched_rows = []
    for name, days, hours, tipo in SHIFT_SCHEDULE:
        sc = SHIFT_COLORS.get(name, "#555e7a")
        sched_rows.append({
            "Agente": name, "Días": days, "Horario (Lima)": hours, "Tipo": tipo
        })
    st.dataframe(pd.DataFrame(sched_rows), use_container_width=True, hide_index=True)

    if load:
        with st.spinner("Cargando sesiones…"):
            sc_ses, d_ses = api_get("sessions", {
                "from": d_from.strftime("%Y-%m-%dT00:00:00Z"),
                "to":   d_to.strftime("%Y-%m-%dT23:59:59Z"),
                "include-events": "true",
            })
            sc_ag, d_ag = api_get("agents")

        ses_list = items(d_ses) if sc_ses == 200 else []
        ag_list  = items(d_ag)  if sc_ag  == 200 else []

        # ── Calcular stats por turno desde sesiones ──
        shift_stats = defaultdict(lambda: {
            "total":0,"asignadas":0,"respondidas":0,"no_asignadas":0,"cierres":0
        })
        daily_shift = defaultdict(lambda: defaultdict(int))  # date -> shift -> count

        for s in ses_list:
            ct = s.get("creationTime","")
            if not ct: continue
            try:
                dt = datetime.fromisoformat(ct.replace("Z","+00:00"))
            except: continue

            shift     = get_shift_label(dt)
            day_str   = to_lima(dt).strftime("%Y-%m-%d")
            ev_names  = [e["name"] for e in s.get("events",[])]

            shift_stats[shift]["total"] += 1
            daily_shift[day_str][shift] += 1

            if "assigned-to-agent" in ev_names: shift_stats[shift]["asignadas"] += 1
            else:                               shift_stats[shift]["no_asignadas"] += 1
            if "agent-action"       in ev_names: shift_stats[shift]["respondidas"] += 1
            if "conversation-close" in ev_names: shift_stats[shift]["cierres"] += 1

        if not shift_stats:
            st.info("Sin datos para ese período.")
        else:
            # ── KPI por turno ──
            sh("Resumen por turno")
            ordered_shifts = ["Alonso Loyola","José Luis Cahuana","Deivy Chavez Trejo",
                              "Daniel Huayta","Luz Goicochea","Joe Villanueva","Victor Macedo"]
            cols = st.columns(len([s for s in ordered_shifts if s in shift_stats]))
            ci = 0
            for shift_name in ordered_shifts:
                if shift_name not in shift_stats: continue
                st_data = shift_stats[shift_name]
                total = st_data["total"]
                asig  = st_data["asignadas"]
                resp  = st_data["respondidas"]
                pct   = int(100*asig/total) if total else 0
                sc    = SHIFT_COLORS.get(shift_name,"#4f6ef7")
                with cols[ci]:
                    st.markdown(f"""<div class="kpi" style="border-top:2px solid {sc}">
                      <div class="kpi-label" style="color:{sc}">{shift_name.split()[0]}</div>
                      <div class="kpi-value" style="color:{sc};font-size:1.8rem">{total}</div>
                      <div class="kpi-sub">sesiones · {pct}% asignadas</div>
                      <div style="font-size:.7rem;color:#555e7a;margin-top:4px">
                        ✅ {asig} asig &nbsp;💬 {resp} resp &nbsp;🔒 {st_data['cierres']} cierre
                      </div></div>""", unsafe_allow_html=True)
                ci += 1

            st.markdown("")
            col_l, col_r = st.columns(2)

            with col_l:
                sh("Sesiones por turno — total")
                shifts_ordered = [s for s in ordered_shifts if s in shift_stats]
                data_bars = {
                    "Turno":      shifts_ordered,
                    "Total":      [shift_stats[s]["total"] for s in shifts_ordered],
                    "Asignadas":  [shift_stats[s]["asignadas"] for s in shifts_ordered],
                    "Respondidas":[shift_stats[s]["respondidas"] for s in shifts_ordered],
                    "No asignadas":[shift_stats[s]["no_asignadas"] for s in shifts_ordered],
                }
                df_b = pd.DataFrame(data_bars)
                f1 = go.Figure()
                f1.add_trace(go.Bar(name="Asignadas",   x=df_b["Turno"], y=df_b["Asignadas"],
                                    marker_color="#22d47b", marker_cornerradius=3))
                f1.add_trace(go.Bar(name="Respondidas", x=df_b["Turno"], y=df_b["Respondidas"],
                                    marker_color="#4f6ef7", marker_cornerradius=3))
                f1.add_trace(go.Bar(name="No asignadas",x=df_b["Turno"], y=df_b["No asignadas"],
                                    marker_color="#f25c5c", marker_cornerradius=3))
                f1.update_layout(**L(barmode="group", margin=dict(l=10,r=10,t=10,b=80)))
                f1.update_xaxes(tickangle=30)
                pf(f1)

            with col_r:
                sh("% Asignadas por turno")
                pct_data = {
                    "Turno": shifts_ordered,
                    "Asignadas %": [int(100*shift_stats[s]["asignadas"]/shift_stats[s]["total"])
                                    if shift_stats[s]["total"] else 0 for s in shifts_ordered],
                }
                df_pct = pd.DataFrame(pct_data)
                f2 = px.bar(df_pct, x="Turno", y="Asignadas %",
                            color="Asignadas %",
                            color_continuous_scale=["#f25c5c","#f5a524","#22d47b"],
                            text=df_pct["Asignadas %"].astype(str)+"%")
                f2.update_layout(**L(coloraxis_showscale=False, margin=dict(l=10,r=10,t=10,b=80)))
                f2.update_xaxes(tickangle=30)
                f2.update_traces(marker_cornerradius=5, textposition="outside")
                pf(f2)

            # ── Heatmap: sesiones por turno por día ──
            sh("Heatmap — sesiones por turno y día")
            all_days  = sorted(daily_shift.keys())
            df_heat = pd.DataFrame(
                [[daily_shift[d].get(s,0) for d in all_days] for s in shifts_ordered],
                index=shifts_ordered, columns=all_days
            )
            f3 = px.imshow(df_heat, aspect="auto",
                           color_continuous_scale=["#0e1018","#1a2a4a","#4f6ef7","#22d47b"],
                           text_auto=True)
            f3.update_layout(**L(margin=dict(l=140,r=10,t=10,b=60)))
            f3.update_xaxes(tickangle=30)
            pf(f3)

            # ── Tabla detallada ──
            sh("Tabla detallada por turno")
            table_rows = []
            for s in shifts_ordered:
                st_d = shift_stats[s]
                total = st_d["total"]
                table_rows.append({
                    "Agente / Turno": s,
                    "Total sesiones": total,
                    "Asignadas":      st_d["asignadas"],
                    "No asignadas":   st_d["no_asignadas"],
                    "Respondidas":    st_d["respondidas"],
                    "Cierres":        st_d["cierres"],
                    "% Asignadas":    f"{int(100*st_d['asignadas']/total) if total else 0}%",
                    "% Respondidas":  f"{int(100*st_d['respondidas']/total) if total else 0}%",
                })
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# PAGE: PRODUCTIVIDAD
# ══════════════════════════════════════════════════════════
elif page == "📈  Productividad agentes":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Productividad de agentes</h2>',
                unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1: d_from = st.date_input("Desde", value=datetime.now()-timedelta(days=7))
    with c2: d_to   = st.date_input("Hasta", value=datetime.now())
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        load = st.button("🔄 Cargar")

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
        ag_map_f = {a["id"]: a for a in ag_list}

        prod = {}
        tl_rows = []
        for s in ses_list:
            for e in s.get("events",[]):
                info    = e.get("info",{})
                ev_name = e.get("name","")
                ag_name = info.get("agentName","")
                ag_id   = info.get("agentId","")
                ev_date = e.get("creationTime","")[:10]
                if not ag_name: continue
                if ag_name not in prod:
                    prod[ag_name] = {"agentId":ag_id,"asignaciones":0,"acciones":0,"cierres":0}
                if ev_name == "assigned-to-agent":
                    prod[ag_name]["asignaciones"] += 1
                    tl_rows.append({"fecha":ev_date,"agente":ag_name})
                elif ev_name == "agent-action":    prod[ag_name]["acciones"]  += 1
                elif ev_name == "conversation-close": prod[ag_name]["cierres"] += 1

        chats_x = Counter(c.get("agentId","") for c in cht_list if c.get("agentId"))

        prod_rows = []
        for name, m in prod.items():
            ag  = ag_map_f.get(m["agentId"],{})
            eff = round(100*m["cierres"]/m["asignaciones"],1) if m["asignaciones"] else 0
            prod_rows.append({
                "Nombre":        name,
                "isOnline":      ag.get("isOnline",False),
                "Status":        ag.get("status","—"),
                "Queues":        ", ".join(ag.get("queues",[])),
                "Chats activos": chats_x.get(m["agentId"],0),
                "Asignaciones":  m["asignaciones"],
                "Acciones":      m["acciones"],
                "Cierres":       m["cierres"],
                "Eficiencia %":  eff,
            })
        prod_rows.sort(key=lambda x: x["Asignaciones"], reverse=True)

        if prod_rows:
            k1,k2,k3,k4 = st.columns(4)
            with k1: kpi("Asignaciones", sum(r["Asignaciones"] for r in prod_rows), f"{d_from}–{d_to}","accent","#4f6ef7")
            with k2: kpi("Acciones",     sum(r["Acciones"]     for r in prod_rows), "agent-action","green","#22d47b")
            with k3: kpi("Cierres",      sum(r["Cierres"]      for r in prod_rows), "conversation-close","orange","#f5a524")
            with k4: kpi("Top agente",   prod_rows[0]["Nombre"], f"{prod_rows[0]['Asignaciones']} asig.","purple","#a78bfa")

            st.markdown("")
            col_l, col_r = st.columns(2)
            with col_l:
                sh("Asignaciones por agente")
                f1 = px.bar(x=[r["Asignaciones"] for r in prod_rows],
                            y=[r["Nombre"] for r in prod_rows], orientation="h",
                            color=[r["Asignaciones"] for r in prod_rows],
                            color_continuous_scale=["#1a1f2e","#4f6ef7"])
                f1.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=10,t=10,b=10)))
                f1.update_traces(marker_cornerradius=4)
                pf(f1)

                sh("Acciones vs cierres")
                f2 = go.Figure()
                f2.add_trace(go.Bar(name="Acciones", x=[r["Nombre"] for r in prod_rows],
                                    y=[r["Acciones"] for r in prod_rows],
                                    marker_color="#4f6ef7", marker_cornerradius=4))
                f2.add_trace(go.Bar(name="Cierres",  x=[r["Nombre"] for r in prod_rows],
                                    y=[r["Cierres"] for r in prod_rows],
                                    marker_color="#22d47b", marker_cornerradius=4))
                f2.update_layout(**L(barmode="group"))
                pf(f2)

            with col_r:
                sh("Eficiencia de cierre (%)")
                f3 = px.bar(x=[r["Eficiencia %"] for r in prod_rows],
                            y=[r["Nombre"] for r in prod_rows], orientation="h",
                            color=[r["Eficiencia %"] for r in prod_rows],
                            color_continuous_scale=["#f25c5c","#f5a524","#22d47b"])
                f3.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=10,t=10,b=10)))
                f3.update_traces(marker_cornerradius=4)
                pf(f3)

                sh("Distribución de asignaciones")
                f4 = px.pie(names=[r["Nombre"] for r in prod_rows],
                            values=[r["Asignaciones"] for r in prod_rows], hole=0.55)
                f4.update_layout(**L(margin=dict(l=0,r=0,t=10,b=0)))
                pf(f4)

            sh("Tabla de productividad")
            df_d = pd.DataFrame(prod_rows)
            df_d["isOnline"] = df_d["isOnline"].map({True:"🟢 Sí",False:"⚫ No"})
            st.dataframe(df_d, use_container_width=True, hide_index=True)

            sh("Asignaciones por día — timeline")
            if tl_rows:
                df_tl = pd.DataFrame(tl_rows)
                pivot = df_tl.groupby(["fecha","agente"]).size().reset_index(name="n")
                f5 = px.bar(pivot, x="fecha", y="n", color="agente", barmode="stack")
                f5.update_layout(**L())
                f5.update_traces(marker_cornerradius=3)
                pf(f5)
        else:
            st.info("Sin datos para ese período.")


# ══════════════════════════════════════════════════════════
# PAGE: SESIONES
# ══════════════════════════════════════════════════════════
elif page == "🗂  Sesiones":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Sesiones</h2>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1: d_from = st.date_input("Desde", value=datetime.now()-timedelta(days=7))
    with c2: d_to   = st.date_input("Hasta", value=datetime.now())
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        load = st.button("🔄 Cargar")
    if load:
        with st.spinner("Cargando…"):
            sc, d = api_get("sessions", {"from":d_from.strftime("%Y-%m-%dT00:00:00Z"),
                                          "to":d_to.strftime("%Y-%m-%dT23:59:59Z"),
                                          "include-events":"true"})
        if sc == 200:
            ses = items(d)
            all_ev=[e["name"] for s in ses for e in s.get("events",[])]
            k1,k2,k3,k4 = st.columns(4)
            with k1: kpi("Sesiones",len(ses),f"{d_from}–{d_to}","accent","#4f6ef7")
            with k2: kpi("Orgánicas",sum(1 for s in ses if s.get("startingCause")=="Organic"),"","green","#22d47b")
            with k3: kpi("Vía Template",sum(1 for s in ses if s.get("startingCause")=="WhatsAppTemplate"),"","orange","#f5a524")
            with k4: kpi("Eventos",len(all_ev),"","purple","#a78bfa")
            st.markdown("")
            col_l,col_r = st.columns(2)
            with col_l:
                df=pd.DataFrame(ses); df["ts"]=pd.to_datetime(df["creationTime"],errors="coerce")
                by=df.groupby([df["ts"].dt.date,"startingCause"]).size().reset_index(name="n")
                by.columns=["Fecha","Origen","n"]
                f1=px.bar(by,x="Fecha",y="n",color="Origen",barmode="stack",
                          color_discrete_map={"Organic":"#4f6ef7","WhatsAppTemplate":"#f5a524"})
                f1.update_layout(**L()); f1.update_traces(marker_cornerradius=3); pf(f1)
            with col_r:
                ev_df=pd.Series(all_ev).value_counts().reset_index(); ev_df.columns=["Evento","n"]
                f2=px.bar(ev_df,x="n",y="Evento",orientation="h",color="n",
                          color_continuous_scale=["#1a1f2e","#a78bfa"])
                f2.update_layout(**L(coloraxis_showscale=False,margin=dict(l=170,r=10,t=10,b=10)))
                f2.update_traces(marker_cornerradius=3); pf(f2)
            sh("Detalle")
            rows=[{"Fecha":s.get("creationTime","")[:16].replace("T"," "),
                   "Origen":s.get("startingCause",""),
                   "Nombre":s.get("chat",{}).get("firstName",""),
                   "Canal":s.get("chat",{}).get("chat",{}).get("channelId","").split("-")[-1],
                   "Eventos":len(s.get("events",[]))} for s in ses[:300]]
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        else: st.error(f"Error {sc}: {d}")


# ══════════════════════════════════════════════════════════
# PAGE: INTENTS & CANALES
# ══════════════════════════════════════════════════════════
elif page == "🎯  Intents & Canales":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Intents & Canales</h2>', unsafe_allow_html=True)
    if st.button("🔄 Cargar"):
        with st.spinner("Cargando…"):
            sc_in,d_in=api_get("intents"); sc_ch,d_ch=api_get("channels")
        col_l,col_r=st.columns(2)
        with col_l:
            sh("Intents")
            if sc_in==200:
                ilist=items(d_in); active=sum(1 for i in ilist if i.get("active"))
                kpi("Activos",active,f"de {len(ilist)}","green","#22d47b"); st.markdown("")
                all_t=[t for i in ilist for t in i.get("topics",[])]
                tf=pd.Series(all_t).value_counts().head(12).reset_index(); tf.columns=["Topic","n"]
                f1=px.bar(tf,x="n",y="Topic",orientation="h",color="n",color_continuous_scale=["#1a1f2e","#a78bfa"])
                f1.update_layout(**L(coloraxis_showscale=False,margin=dict(l=160,r=10,t=10,b=10)))
                f1.update_traces(marker_cornerradius=3); pf(f1)
        with col_r:
            sh("Canales")
            if sc_ch==200:
                chs=items(d_ch); kpi("Canales",len(chs),f"{sum(1 for c in chs if c.get('active'))} activos","sky","#38bdf8")
                st.markdown("")
                plat=pd.Series([c.get("platform","") for c in chs]).value_counts().reset_index(); plat.columns=["Plataforma","n"]
                f2=px.bar(plat,x="Plataforma",y="n",color="Plataforma")
                f2.update_layout(**L()); f2.update_traces(marker_cornerradius=5); pf(f2)
                st.dataframe(pd.DataFrame([{"Plataforma":c["platform"],"Activo":"✅" if c.get("active") else "❌","Número":c.get("number","")} for c in chs]),use_container_width=True,hide_index=True)


# ══════════════════════════════════════════════════════════
# PAGE: TEMPLATES WA
# ══════════════════════════════════════════════════════════
elif page == "📋  Templates WA":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Templates WhatsApp</h2>', unsafe_allow_html=True)
    if st.button("🔄 Cargar"):
        with st.spinner("Cargando…"):
            sc,d=api_get("whatsapp/templates")
        if sc==200:
            tpls=items(d)
            k1,k2,k3=st.columns(3)
            with k1: kpi("Templates",len(tpls),"","accent","#4f6ef7")
            with k2: kpi("Marketing",sum(1 for t in tpls if t.get("category")=="MARKETING"),"","orange","#f5a524")
            with k3: kpi("Utility",  sum(1 for t in tpls if t.get("category")=="UTILITY"),"","sky","#38bdf8")
            st.markdown("")
            col_l,col_r=st.columns(2)
            with col_l:
                cf=pd.Series([t.get("category","") for t in tpls]).value_counts().reset_index(); cf.columns=["Cat","n"]
                f=px.pie(cf,names="Cat",values="n",hole=0.55,color_discrete_map={"MARKETING":"#f5a524","UTILITY":"#4f6ef7"})
                f.update_layout(**L()); pf(f)
            with col_r:
                st.dataframe(pd.DataFrame([{"Nombre":t.get("name",""),"Estado":t.get("state",""),
                    "Categoría":t.get("category",""),"Idioma":t.get("locale",""),
                    "Botones":len(t.get("buttons",[]) or [])} for t in tpls]),use_container_width=True,hide_index=True)
            sh("Vista previa")
            for t in tpls[:5]:
                bt=t.get("body",{}).get("text","") if isinstance(t.get("body"),dict) else ""
                with st.expander(f"📄 {t.get('name','')} · {t.get('category','')}"):
                    st.write(bt)
                    for b in (t.get("buttons",[]) or []):
                        st.markdown(f"- `{b.get('type','')}` **{b.get('text','')}**"+(f" → {b.get('url','')}" if b.get("url") else ""))
        else: st.error(f"Error {sc}: {d}")
