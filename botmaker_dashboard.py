"""
botmaker_dashboard.py  ·  Kashio
Sidebar: filtros de fecha + switch Live + switch Tema
Contenido: pestañas (Monitor · Tiempos · Turnos · Productividad · Sesiones · Más)
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

BASE_URL    = "https://api.botmaker.com/v2.0"
LIMA_OFFSET = timedelta(hours=-5)

def to_lima(dt): return dt + LIMA_OFFSET

def get_shift_label(dt_utc):
    lima = to_lima(dt_utc)
    wd, h = lima.weekday(), lima.hour
    if wd in [0,1,2,3,4]:
        if  6 <= h < 14: return "Alonso Loyola"
        if 14 <= h < 22: return "José Luis Cahuana"
        return "Deivy Chavez Trejo"
    else:
        if  6 <= h < 14: return "Daniel Huayta"
        if 14 <= h < 22: return "Luz Goicochea"
        return "Joe Villanueva"

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
SHIFT_ORDER  = ["Alonso Loyola","José Luis Cahuana","Deivy Chavez Trejo",
                "Daniel Huayta","Luz Goicochea","Joe Villanueva","Victor Macedo"]
SHIFT_COLORS = {"Alonso Loyola":"#4f6ef7","José Luis Cahuana":"#f5a524",
                "Deivy Chavez Trejo":"#a78bfa","Daniel Huayta":"#22d47b",
                "Luz Goicochea":"#38bdf8","Joe Villanueva":"#f25c5c","Victor Macedo":"#fb923c"}

# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="Kashio · Monitor", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

# ── session state defaults ────────────────────────────────
if "dark_mode" not in st.session_state: st.session_state.dark_mode = True
if "live_on"   not in st.session_state: st.session_state.live_on   = False

dark = st.session_state.dark_mode

# ─────────────────────────────────────────────────────────
# THEME VARIABLES
# ─────────────────────────────────────────────────────────
if dark:
    BG        = "#07080c"
    S1        = "#0e1018"
    S2        = "#141720"
    S3        = "#1a1f2c"
    BORDER    = "#1e2333"
    TEXT      = "#e6e8f0"
    TEXT2     = "#c4c9db"
    MUTED     = "#555e7a"
    GRID      = "#1a1f2e"
    PLOT_BG   = "rgba(0,0,0,0)"
    CHART_BG  = "rgba(0,0,0,0)"
    FONT_COL  = "#8892aa"
    SB_BG     = "#0e1018"
    SHADOW    = "none"
    SHADOW_MD = "none"
    # Colores de gráficos saturados para fondo oscuro
    C_BLUE    = "#4f6ef7"
    C_GREEN   = "#22d47b"
    C_ORANGE  = "#f5a524"
    C_RED     = "#f25c5c"
    C_PURPLE  = "#a78bfa"
    C_SKY     = "#38bdf8"
    C_CORAL   = "#fb923c"
else:
    BG        = "#edf0f9"
    S1        = "#ffffff"
    S2        = "#f3f5fc"
    S3        = "#e8ecf7"
    BORDER    = "#d4daf0"
    TEXT      = "#0d1229"
    TEXT2     = "#2e3657"
    MUTED     = "#5a6890"
    GRID      = "#dce2f4"
    PLOT_BG   = "#ffffff"
    CHART_BG  = "#ffffff"
    FONT_COL  = "#4a5578"
    SB_BG     = "#f8faff"
    SHADOW    = "0 1px 3px rgba(20,28,80,.07), 0 4px 16px rgba(20,28,80,.07)"
    SHADOW_MD = "0 2px 8px rgba(20,28,80,.10), 0 8px 24px rgba(20,28,80,.08)"
    # Colores ligeramente más oscuros/saturados para fondo claro
    C_BLUE    = "#3d5ce8"
    C_GREEN   = "#0ea85e"
    C_ORANGE  = "#d97706"
    C_RED     = "#dc3545"
    C_PURPLE  = "#7c5cbf"
    C_SKY     = "#0891b2"
    C_CORAL   = "#ea580c"

# ─────────────────────────────────────────────────────────
# CSS — dynamic theme
# ─────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

/* ── Reset & base ── */
html,body,[class*="css"]{{font-family:'Inter',sans-serif;color:{TEXT};}}
.stApp{{background:{BG}!important;}}

/* ── Sidebar ── */
section[data-testid="stSidebar"]{{
  background:{SB_BG}!important;
  border-right:1px solid {BORDER}!important;
  {("box-shadow: 2px 0 16px rgba(20,28,80,.08);" if not dark else "")}
}}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div{{color:{TEXT}!important;}}

/* ── KPI card ── */
.kpi{{
  background:{S1};
  border:1px solid {BORDER};
  border-radius:14px;
  padding:18px 20px;
  position:relative;
  overflow:hidden;
  box-shadow:{SHADOW};
  transition:box-shadow .2s;
}}
.kpi:hover{{box-shadow:{SHADOW_MD};}}
.kpi-accent{{border-top:3px solid {C_BLUE};}}
.kpi-green{{border-top:3px solid {C_GREEN};}}
.kpi-orange{{border-top:3px solid {C_ORANGE};}}
.kpi-red{{border-top:3px solid {C_RED};}}
.kpi-purple{{border-top:3px solid {C_PURPLE};}}
.kpi-sky{{border-top:3px solid {C_SKY};}}
.kpi-coral{{border-top:3px solid {C_CORAL};}}
.kpi-label{{font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:{MUTED};font-weight:600;}}
.kpi-value{{font-family:'Syne',sans-serif;font-size:2.1rem;font-weight:800;line-height:1;margin:7px 0 3px;}}
.kpi-sub{{font-size:.72rem;color:{MUTED};}}

/* ── Agent card ── */
.ac{{
  background:{S1};
  border:1px solid {BORDER};
  border-radius:12px;
  padding:13px 15px;
  display:flex;align-items:center;gap:12px;
  box-shadow:{SHADOW};
  transition:box-shadow .2s;
}}
.ac:hover{{box-shadow:{SHADOW_MD};}}
.av{{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-family:'Syne',sans-serif;font-weight:800;font-size:.95rem;flex-shrink:0;}}
.an{{font-size:.86rem;font-weight:600;color:{TEXT};}}
.am{{font-size:.7rem;color:{MUTED};margin-top:2px;}}
.ab{{margin-left:auto;padding:3px 9px;border-radius:20px;font-size:.67rem;
  font-weight:700;font-family:'Syne',sans-serif;white-space:nowrap;}}
.od{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;}}

/* ── Section header ── */
.sh{{
  font-family:'Syne',sans-serif;font-size:.67rem;letter-spacing:.13em;
  text-transform:uppercase;color:{MUTED};font-weight:700;
  padding-bottom:7px;border-bottom:2px solid {BORDER};
  margin:22px 0 13px;
  display:flex;align-items:center;justify-content:space-between;
}}

/* ── Live dot ── */
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.ld{{display:inline-block;width:8px;height:8px;border-radius:50%;
  background:{C_RED};animation:pulse 1.2s infinite;margin-right:6px;vertical-align:middle;}}

/* ── Sidebar label ── */
.sidebar-label{{
  font-size:.67rem;letter-spacing:.1em;text-transform:uppercase;
  color:{MUTED};margin-bottom:8px;font-family:'Syne',sans-serif;font-weight:700;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{{
  background:{S1};
  border-radius:10px;padding:4px;
  border:1px solid {BORDER};gap:3px;
  position:sticky;top:0;z-index:10;
  box-shadow:{SHADOW};
}}
.stTabs [data-baseweb="tab"]{{
  color:{MUTED}!important;font-family:'Syne',sans-serif!important;
  font-size:.78rem!important;font-weight:600!important;border-radius:7px!important;
  padding:8px 16px!important;transition:background .15s!important;
}}
.stTabs [data-baseweb="tab"]:hover{{background:{S2}!important;}}
.stTabs [aria-selected="true"]{{background:{C_BLUE}!important;color:#fff!important;}}

/* ── Buttons ── */
.stButton>button{{
  background:{C_BLUE}!important;color:#fff!important;
  font-family:'Syne',sans-serif!important;font-weight:700!important;
  font-size:.8rem!important;border:none!important;border-radius:8px!important;
  padding:8px 20px!important;box-shadow:{SHADOW}!important;
}}
.stButton>button:hover{{opacity:.88!important;box-shadow:{SHADOW_MD}!important;}}

/* ── Form controls ── */
.stSelectbox>div>div,
.stNumberInput>div>div>input,
.stDateInput>div>div>input,
.stTextInput>div>div>input{{
  background:{S2}!important;border:1.5px solid {BORDER}!important;
  color:{TEXT}!important;border-radius:8px!important;
  font-size:.84rem!important;
}}
.stSelectbox>div>div:focus-within,
.stNumberInput>div>div>input:focus,
.stDateInput>div>div>input:focus{{
  border-color:{C_BLUE}!important;
  box-shadow:0 0 0 3px rgba(79,110,247,.15)!important;
}}
div[data-testid="stDateInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label{{
  color:{MUTED}!important;font-size:.74rem!important;font-weight:600!important;
  letter-spacing:.04em!important;text-transform:uppercase!important;
}}

/* ── DataFrame ── */
.stDataFrame{{border-radius:10px;overflow:hidden;box-shadow:{SHADOW};}}
.stDataFrame thead th{{
  background:{S3}!important;color:{TEXT2}!important;
  font-size:.74rem!important;font-weight:700!important;
  text-transform:uppercase!important;letter-spacing:.05em!important;
}}
.stDataFrame tbody td{{
  background:{S1}!important;color:{TEXT}!important;font-size:.82rem!important;
}}
.stDataFrame tbody tr:hover td{{background:{S2}!important;}}

/* ── Toggle ── */
div[data-testid="stToggle"]>label{{font-size:.82rem!important;color:{TEXT}!important;font-weight:500!important;}}

/* ── Misc ── */
hr{{border-color:{BORDER};margin:8px 0;}}
.stAlert{{border-radius:10px!important;}}
[data-testid="stMarkdownContainer"] p{{color:{TEXT}!important;}}
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
# PLOTLY BASE
# ─────────────────────────────────────────────────────────
# Plotly legend/axis bg adapts to theme
_LEGEND_BG = "rgba(14,16,24,.85)" if dark else "rgba(255,255,255,.9)"
_LEGEND_BD = GRID

_BL = dict(
    paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
    font=dict(family="Inter", color=FONT_COL, size=12),
    xaxis=dict(gridcolor=GRID, linecolor=GRID, zerolinecolor=GRID,
               tickfont=dict(color=FONT_COL), title_font=dict(color=MUTED)),
    yaxis=dict(gridcolor=GRID, linecolor=GRID, zerolinecolor=GRID,
               tickfont=dict(color=FONT_COL), title_font=dict(color=MUTED)),
    legend=dict(bgcolor=_LEGEND_BG, bordercolor=_LEGEND_BD,
                font=dict(color=TEXT, size=11)),
    colorway=[C_BLUE, C_GREEN, C_ORANGE, C_RED, C_PURPLE, C_SKY, C_CORAL],
)

def L(**kw):
    r = dict(_BL)
    r.setdefault("margin", dict(l=10,r=10,t=36,b=10))
    r.update(kw)
    return r

def pf(f): st.plotly_chart(f, use_container_width=True, config={"displayModeBar":False})

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
def its(resp):
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
                f'<span style="font-size:.67rem;color:{MUTED}">{right}</span></div>',
                unsafe_allow_html=True)

AV_COLORS = ["#4f6ef7","#22d47b","#f5a524","#a78bfa","#38bdf8","#f25c5c","#fb923c","#e879f9"]

def fmt_hrs(h):
    if h >= 48: return f"{h/24:.1f}d"
    if h >= 1:  return f"{h:.1f}h"
    return f"{int(h*60)}m"

def sev_color(h):
    if h >= 48: return C_RED
    if h >= 24: return C_ORANGE
    if h >= 4:  return C_BLUE
    return C_GREEN

def agent_card(ag, chats_n, max_wait_h):
    is_online = ag.get("isOnline", False)
    status    = ag.get("status","—")
    name      = ag.get("name","Agente")
    initials  = "".join(w[0].upper() for w in name.split()[:2])
    av_col    = AV_COLORS[abs(hash(ag.get("id",""))) % len(AV_COLORS)]
    dot_col   = C_GREEN if is_online else MUTED
    if is_online:
        bs="background:rgba(34,212,123,.12);color:#22d47b;border:1px solid rgba(34,212,123,.3)";bt="EN LÍNEA"
    elif status=="busy":
        bs="background:rgba(245,165,36,.12);color:#f5a524;border:1px solid rgba(245,165,36,.3)";bt="OCUPADO"
    else:
        bs=f"background:{S2};color:{MUTED};border:1px solid {BORDER}";bt="OFFLINE"
    wc = sev_color(max_wait_h)
    wait = (f'<span style="font-size:.7rem;color:{wc};font-weight:700;margin-left:6px">'
            f'⏱ {fmt_hrs(max_wait_h)}</span>') if max_wait_h > 0 else \
           f'<span style="font-size:.7rem;color:{MUTED};margin-left:6px">⏱ —</span>'
    queues = ", ".join(ag.get("queues",[])) or "—"
    st.markdown(f"""
    <div class="ac">
      <div class="av" style="background:{av_col}22;color:{av_col};border:1.5px solid {av_col}44">{initials}</div>
      <div style="flex:1;min-width:0">
        <div class="an"><span class="od" style="background:{dot_col}"></span>{name}{wait}</div>
        <div class="am">Queues: {queues} · Slots: {ag.get('slots',0)} · Chats: <b style="color:{TEXT}">{chats_n}</b></div>
      </div>
      <span class="ab" style="{bs}">{bt}</span>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════
with st.sidebar:
    # ── Logo ──
    st.markdown(f"""<div style="padding:12px 0 16px">
      <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;color:{TEXT}">⚡ Kashio</div>
      <div style="font-size:.65rem;color:{MUTED};letter-spacing:.1em">BOTMAKER · MONITOR</div>
    </div>""", unsafe_allow_html=True)

    # ── Apariencia ──
    st.markdown(f'<div class="sidebar-label">Apariencia</div>', unsafe_allow_html=True)
    col_sun, col_tog, col_moon = st.columns([1, 2, 1])
    with col_sun:  st.markdown(f'<div style="text-align:right;padding-top:6px;font-size:1rem">☀️</div>', unsafe_allow_html=True)
    with col_tog:
        new_dark = st.toggle("", value=dark, key="theme_toggle",
                             help="Alternar entre modo claro y oscuro")
        if new_dark != dark:
            st.session_state.dark_mode = new_dark
            st.rerun()
    with col_moon: st.markdown('<div style="padding-top:6px;font-size:1rem">🌙</div>', unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Live mode ──
    st.markdown(f'<div class="sidebar-label">Monitor en vivo</div>', unsafe_allow_html=True)

    live_on = st.toggle("🔴  Activar LIVE", value=st.session_state.live_on, key="live_toggle")
    if live_on != st.session_state.live_on:
        st.session_state.live_on = live_on

    if live_on:
        refresh_opts = {"30 seg":30,"1 min":60,"2 min":120,"5 min":300}
        chosen_label = st.selectbox("Intervalo de refresco", list(refresh_opts.keys()),
                                    index=1, key="live_interval")
        refresh_secs = refresh_opts[chosen_label]
        # Solo ejecutar autorefresh aquí si está en live
        if HAS_AUTOREFRESH:
            st_autorefresh(interval=refresh_secs*1000, limit=None, key="live_ar")
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        st.markdown(f'<div style="font-size:.72rem;color:#f25c5c;margin-top:4px">'
                    f'<span class="ld"></span>Actualizando cada {chosen_label}</div>',
                    unsafe_allow_html=True)
    else:
        refresh_secs = 0
        if st.button("🔄 Refrescar ahora"):
            st.rerun()

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Filtros de fecha ──
    st.markdown(f'<div class="sidebar-label">Filtros de fecha</div>', unsafe_allow_html=True)

    preset = st.selectbox("Período rápido", ["Hoy","Últimas 24h","Últimos 7 días",
                                              "Últimos 14 días","Últimos 30 días","Personalizado"],
                          index=2, key="date_preset")
    now_utc = datetime.now(timezone.utc)

    if preset == "Hoy":
        d_from_def = now_utc.date()
        d_to_def   = now_utc.date()
    elif preset == "Últimas 24h":
        d_from_def = (now_utc - timedelta(hours=24)).date()
        d_to_def   = now_utc.date()
    elif preset == "Últimos 7 días":
        d_from_def = (now_utc - timedelta(days=7)).date()
        d_to_def   = now_utc.date()
    elif preset == "Últimos 14 días":
        d_from_def = (now_utc - timedelta(days=14)).date()
        d_to_def   = now_utc.date()
    elif preset == "Últimos 30 días":
        d_from_def = (now_utc - timedelta(days=30)).date()
        d_to_def   = now_utc.date()
    else:
        d_from_def = (now_utc - timedelta(days=7)).date()
        d_to_def   = now_utc.date()

    if preset == "Personalizado":
        d_from = st.date_input("Desde", value=d_from_def, key="d_from")
        d_to   = st.date_input("Hasta", value=d_to_def,   key="d_to")
    else:
        d_from = d_from_def
        d_to   = d_to_def
        st.markdown(f'<div style="font-size:.75rem;color:{MUTED}">📅 {d_from} → {d_to}</div>',
                    unsafe_allow_html=True)

    FROM_STR = f"{d_from}T00:00:00Z"
    TO_STR   = f"{d_to}T23:59:59Z"
    FROM_24H = (now_utc - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Alerta tiempo ──
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-label">Umbral de alerta</div>', unsafe_allow_html=True)
    warn_h = st.number_input("Alertar desde (horas)", min_value=1, max_value=72,
                              value=4, key="warn_h")

    # ── Última carga ──
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:.67rem;color:{MUTED}">'
                f'Última carga: {now_utc.strftime("%H:%M:%S UTC")}</div>',
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# MAIN CONTENT — TABS
# ══════════════════════════════════════════════════════════
st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
  <div style="font-family:'Syne',sans-serif;font-size:1.5rem;font-weight:800;color:{TEXT}">
    {'<span class="ld"></span>' if live_on else ''}Dashboard
  </div>
  {'<div style="font-size:.75rem;color:#f25c5c;font-weight:600">● EN VIVO</div>' if live_on else
   f'<div style="font-size:.75rem;color:{MUTED}">{d_from} → {d_to}</div>'}
</div>
""", unsafe_allow_html=True)

tab_monitor, tab_tiempos, tab_turnos, tab_prod, tab_ses, tab_extra = st.tabs([
    "🔴 Monitor",
    "⏱ Tiempos sin resp.",
    "📋 Turnos & Cobertura",
    "📈 Productividad",
    "🗂 Sesiones",
    "🔧 Canales & Templates",
])


# ══════════════════════════════════════════════════════════
# TAB: MONITOR EN VIVO
# ══════════════════════════════════════════════════════════
with tab_monitor:
    with st.spinner("Cargando datos…"):
        sc_ag,  d_ag  = api_get("agents")
        sc_ag2, d_ag2 = api_get("agents", {"online":"true"})
        sc_ch,  d_ch  = api_get("chats",  {"from": FROM_24H})

    ag_list  = its(d_ag)  if sc_ag  == 200 else []
    ag_on    = its(d_ag2) if sc_ag2 == 200 else []
    cht_list = its(d_ch)  if sc_ch  == 200 else []
    ag_map_f = {a["id"]: a for a in ag_list}

    sin_asig   = [c for c in cht_list if not c.get("agentId")]
    soporte_n1 = [c for c in cht_list if c.get("queueId") == "Soporte N1"]
    comercial  = [c for c in cht_list if c.get("queueId") == "Comercial"]
    default_q  = [c for c in cht_list if c.get("queueId") == "_default_"]
    pendientes = [c for c in cht_list if c.get("isBotMuted") and c.get("agentId")]
    now_iso    = now_utc.isoformat()[:19]

    # Max espera por agente
    ag_max_wait = defaultdict(float)
    for c in pendientes:
        lu = c.get("lastUserMessageDatetime","")
        if lu:
            try:
                h = (now_utc - datetime.fromisoformat(lu.replace("Z","+00:00"))).total_seconds()/3600
                ag_max_wait[c.get("agentId","")] = max(ag_max_wait[c.get("agentId","")], h)
            except: pass

    # KPIs
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: kpi("Sin asignar",      len(sin_asig),   "sin agentId","red",C_RED)
    with k2: kpi("Soporte N1",       len(soporte_n1), "en cola","orange",C_ORANGE)
    with k3: kpi("Comercial",        len(comercial),  "en cola","accent",C_BLUE)
    with k4: kpi("Cola _default_",   len(default_q),  "sin cola específica","purple",C_PURPLE)
    with k5: kpi("Pend. responder",  len(pendientes), "bot muted + agente","sky",C_SKY)
    with k6: kpi("Agentes online",   len(ag_on),      f"de {len(ag_list)} total","green",C_GREEN)

    st.markdown("")

    # ── Grid de agentes ──
    sh("Estado de agentes en tiempo real", f"{len(ag_on)} en línea · {len(ag_list)} total")
    chats_x = Counter(c.get("agentId","") for c in cht_list if c.get("agentId"))
    ag_sorted = sorted(ag_list, key=lambda a: (0 if a.get("isOnline") else (1 if a.get("status")=="busy" else 2)))
    cols = st.columns(3)
    for i, ag in enumerate(ag_sorted):
        with cols[i%3]:
            agent_card(ag, chats_x.get(ag.get("id",""),0), ag_max_wait.get(ag.get("id",""),0))
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    st.markdown("")

    # ── Sin asignar + charts ──
    col_l, col_r = st.columns([3,2])
    with col_l:
        sh(f"Sin asignar — {len(sin_asig)}", "últimas 24h")
        if sin_asig:
            rows = [{"Nombre":c.get("firstName","—"),"País":c.get("country","—"),
                     "Queue":c.get("queueId","—"),
                     "Ventana WA":"✅" if c.get("whatsAppWindowCloseDatetime","")>now_iso else "❌",
                     "Bot muted":"Sí" if c.get("isBotMuted") else "No",
                     "Último msg":c.get("lastUserMessageDatetime","")[:16].replace("T"," ")} for c in sin_asig]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38,380))
        else:
            st.success("✅ Sin chats sin asignar.")

    with col_r:
        sh("Por queue")
        if cht_list:
            qc = Counter(c.get("queueId") or "Sin queue" for c in cht_list)
            f1 = px.pie(pd.DataFrame({"Q":list(qc.keys()),"n":list(qc.values())}),
                        names="Q", values="n", hole=0.58,
                        color_discrete_map={"_default_":C_BLUE,"Soporte N1":C_ORANGE,"Comercial":C_GREEN,"Sin queue":MUTED})
            f1.update_layout(**L(margin=dict(l=0,r=0,t=10,b=0)))
            pf(f1)
        sh("Bot activo vs silenciado")
        mc = Counter("Silenciado" if c.get("isBotMuted") else "Bot activo" for c in cht_list)
        f2 = go.Figure(go.Bar(x=list(mc.keys()), y=list(mc.values()),
            marker_color=[C_RED if k=="Silenciado" else C_GREEN for k in mc.keys()],
            text=list(mc.values()), textposition="outside"))
        f2.update_layout(**L(showlegend=False, margin=dict(l=10,r=10,t=10,b=20)))
        f2.update_traces(marker_cornerradius=6)
        pf(f2)

    # ── Pendientes ──
    sh(f"Pendientes de responder — {len(pendientes)}", "bot muted + agente asignado")
    if pendientes:
        rows = []
        for c in pendientes:
            lu = c.get("lastUserMessageDatetime","")
            hrs = 0.0
            if lu:
                try: hrs = (now_utc - datetime.fromisoformat(lu.replace("Z","+00:00"))).total_seconds()/3600
                except: pass
            aid = c.get("agentId","")
            a   = ag_map_f.get(aid,{})
            rows.append({"hrs":hrs,"⏱ Espera":fmt_hrs(hrs),
                "Sev":"🔴" if hrs>=48 else ("🟠" if hrs>=24 else ("🟡" if hrs>=4 else "🟢")),
                "Agente":a.get("name",aid[:10]+"…"),
                "Cliente":c.get("firstName","—"),"País":c.get("country","—"),
                "Queue":c.get("queueId","—"),
                "Último msg":lu[:16].replace("T"," ")})
        rows.sort(key=lambda x: x["hrs"], reverse=True)
        col_t, col_c = st.columns([3,2])
        with col_t:
            st.dataframe(pd.DataFrame(rows).drop(columns=["hrs"]),
                         use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38,360))
        with col_c:
            by_ag = defaultdict(float)
            for r in rows: by_ag[r["Agente"]] = max(by_ag[r["Agente"]], r["hrs"])
            f3 = go.Figure(go.Bar(
                x=list(by_ag.values()), y=list(by_ag.keys()), orientation="h",
                marker_color=[sev_color(v) for v in by_ag.values()],
                text=[fmt_hrs(v) for v in by_ag.values()], textposition="outside"))
            f3.update_layout(**L(title="Máx. espera por agente",
                                  margin=dict(l=140,r=60,t=36,b=10),showlegend=False))
            f3.update_traces(marker_cornerradius=4)
            pf(f3)
    else:
        st.success("✅ Sin pendientes.")


# ══════════════════════════════════════════════════════════
# TAB: TIEMPOS SIN RESPONDER
# ══════════════════════════════════════════════════════════
with tab_tiempos:
    with st.spinner("Cargando…"):
        sc_ag2, d_ag2 = api_get("agents")
        sc_ch2, d_ch2 = api_get("chats", {"from": FROM_STR})

    ag_l2  = its(d_ag2) if sc_ag2 == 200 else []
    ch_l2  = its(d_ch2) if sc_ch2 == 200 else []
    ag_m2  = {a["id"]: a for a in ag_l2}

    rows = []
    for c in ch_l2:
        if not (c.get("isBotMuted") and c.get("agentId")): continue
        lu = c.get("lastUserMessageDatetime","")
        if not lu: continue
        try:
            hrs = (now_utc - datetime.fromisoformat(lu.replace("Z","+00:00"))).total_seconds()/3600
        except: continue
        if hrs < warn_h: continue
        aid = c.get("agentId","")
        ag  = ag_m2.get(aid,{})
        rows.append({
            "hrs": hrs,
            "⏱ Espera": fmt_hrs(hrs),
            "Severidad": "🔴 Crítico" if hrs>=48 else ("🟠 Alto" if hrs>=24 else ("🟡 Medio" if hrs>=8 else "🔵 Bajo")),
            "Agente":    ag.get("name", aid[:12]+"…"),
            "Cliente":   c.get("firstName","—"),
            "País":      c.get("country","—"),
            "Queue":     c.get("queueId","—"),
            "Último msg (Lima)": to_lima(datetime.fromisoformat(lu.replace("Z","+00:00"))).strftime("%d/%m %H:%M"),
        })
    rows.sort(key=lambda x: x["hrs"], reverse=True)

    if not rows:
        st.success(f"✅ Ningún chat supera las {warn_h}h sin respuesta en el período seleccionado.")
    else:
        criticos = sum(1 for r in rows if r["hrs"]>=48)
        altos    = sum(1 for r in rows if 24<=r["hrs"]<48)
        k1,k2,k3,k4 = st.columns(4)
        with k1: kpi("Sin respuesta", len(rows), f"≥{warn_h}h","red",C_RED)
        with k2: kpi("Críticos ≥48h", criticos, "urgente","red",C_RED)
        with k3: kpi("Altos 24–48h",  altos, "","orange",C_ORANGE)
        with k4: kpi("Máx. espera",   fmt_hrs(rows[0]["hrs"]), rows[0]["Agente"],"purple",C_PURPLE)

        st.markdown("")
        col_l, col_r = st.columns([2,3])

        with col_l:
            sh("Gauge — conversación más antigua")
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(rows[0]["hrs"],1),
                number={"suffix":" h","font":{"size":40,"color":sev_color(rows[0]["hrs"]),"family":"Syne"}},
                gauge={"axis":{"range":[0,120],"tickcolor":MUTED,"tickfont":{"color":MUTED}},
                       "bar":{"color":sev_color(rows[0]["hrs"])},
                       "bgcolor":S1,"bordercolor":BORDER,"borderwidth":1,
                       "steps":[{"range":[0,4],"color":"rgba(34,212,123,.1)"},
                                 {"range":[4,24],"color":"rgba(79,110,247,.1)"},
                                 {"range":[24,48],"color":"rgba(245,165,36,.1)"},
                                 {"range":[48,120],"color":"rgba(242,92,92,.1)"}],
                       "threshold":{"line":{"color":C_RED,"width":3},"thickness":.8,"value":48}},
                title={"text":f"{rows[0]['Cliente']} · {rows[0]['Agente']}","font":{"size":12,"color":MUTED}},
            ))
            fig_g.update_layout(**L(height=260, margin=dict(l=20,r=20,t=50,b=10)))
            pf(fig_g)

            sh("Por severidad")
            sev_c = Counter(r["Severidad"] for r in rows)
            fsev = px.pie(pd.DataFrame({"S":list(sev_c.keys()),"n":list(sev_c.values())}),
                          names="S", values="n", hole=0.55,
                          color_discrete_map={"🔴 Crítico":C_RED,"🟠 Alto":C_ORANGE,"🟡 Medio":C_BLUE,"🔵 Bajo":C_GREEN})
            fsev.update_layout(**L(margin=dict(l=0,r=0,t=10,b=0)))
            pf(fsev)

        with col_r:
            sh(f"Top {min(20,len(rows))} conversaciones sin respuesta")
            df_bars = pd.DataFrame(rows[:20])
            df_bars["Label"] = df_bars["Cliente"] + "  /  " + df_bars["Agente"]
            fb = px.bar(df_bars, x="hrs", y="Label", orientation="h",
                        color="hrs", color_continuous_scale=[C_GREEN, C_BLUE, C_ORANGE, C_RED],
                        color_continuous_midpoint=24, text=df_bars["⏱ Espera"])
            fb.update_layout(**L(coloraxis_showscale=False,
                                  margin=dict(l=200,r=60,t=10,b=10),
                                  height=max(300, len(rows[:20])*30+40)))
            fb.update_traces(marker_cornerradius=4, textposition="outside")
            pf(fb)

            sh("Distribución de esperas por agente")
            df_ag = pd.DataFrame(rows)
            fbox = px.box(df_ag, x="Agente", y="hrs", color="Agente",
                          color_discrete_map=SHIFT_COLORS, points="all")
            fbox.update_layout(**L(showlegend=False, yaxis_title="Horas sin respuesta",
                                    margin=dict(l=10,r=10,t=10,b=60)))
            pf(fbox)

        sh("Detalle completo")
        st.dataframe(pd.DataFrame(rows).drop(columns=["hrs"]),
                     use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# TAB: TURNOS & COBERTURA
# ══════════════════════════════════════════════════════════
with tab_turnos:
    sh("Horarios configurados")
    st.dataframe(pd.DataFrame([{"Agente":n,"Días":d,"Horario (Lima)":h,"Tipo":t}
                                for n,d,h,t in SHIFT_SCHEDULE]),
                 use_container_width=True, hide_index=True)

    with st.spinner("Cargando sesiones…"):
        sc_s, d_s = api_get("sessions", {"from":FROM_STR,"to":TO_STR,"include-events":"true"})

    ses_list = its(d_s) if sc_s == 200 else []

    if not ses_list:
        st.info("Sin sesiones para el período seleccionado.")
    else:
        shift_stats = defaultdict(lambda:{"total":0,"asignadas":0,"respondidas":0,"no_asignadas":0,"cierres":0})
        daily_shift = defaultdict(lambda: defaultdict(int))

        for s in ses_list:
            ct = s.get("creationTime","")
            if not ct: continue
            try: dt = datetime.fromisoformat(ct.replace("Z","+00:00"))
            except: continue
            shift    = get_shift_label(dt)
            day_str  = to_lima(dt).strftime("%Y-%m-%d")
            ev_names = [e["name"] for e in s.get("events",[])]
            shift_stats[shift]["total"] += 1
            daily_shift[day_str][shift] += 1
            if "assigned-to-agent"  in ev_names: shift_stats[shift]["asignadas"]    += 1
            else:                                shift_stats[shift]["no_asignadas"]  += 1
            if "agent-action"       in ev_names: shift_stats[shift]["respondidas"]   += 1
            if "conversation-close" in ev_names: shift_stats[shift]["cierres"]       += 1

        active_shifts = [s for s in SHIFT_ORDER if s in shift_stats]

        sh("Resumen por turno")
        cols = st.columns(len(active_shifts))
        for i, sname in enumerate(active_shifts):
            sd    = shift_stats[sname]
            total = sd["total"]
            pct   = int(100*sd["asignadas"]/total) if total else 0
            sc    = SHIFT_COLORS.get(sname,C_BLUE)
            with cols[i]:
                st.markdown(f"""<div class="kpi" style="border-top:2px solid {sc}">
                  <div class="kpi-label" style="color:{sc}">{sname.split()[0]}</div>
                  <div class="kpi-value" style="color:{sc};font-size:1.7rem">{total}</div>
                  <div class="kpi-sub">{pct}% asignadas</div>
                  <div style="font-size:.68rem;color:{MUTED};margin-top:6px">
                    ✅ {sd['asignadas']} asig &nbsp;💬 {sd['respondidas']} resp &nbsp;🔒 {sd['cierres']} cierre
                  </div></div>""", unsafe_allow_html=True)

        st.markdown("")
        col_l, col_r = st.columns(2)

        with col_l:
            sh("Asignadas vs No asignadas por turno")
            f1 = go.Figure()
            f1.add_trace(go.Bar(name="Asignadas",    x=active_shifts, y=[shift_stats[s]["asignadas"]    for s in active_shifts], marker_color=C_GREEN, marker_cornerradius=3))
            f1.add_trace(go.Bar(name="Respondidas",  x=active_shifts, y=[shift_stats[s]["respondidas"]  for s in active_shifts], marker_color=C_BLUE, marker_cornerradius=3))
            f1.add_trace(go.Bar(name="No asignadas", x=active_shifts, y=[shift_stats[s]["no_asignadas"] for s in active_shifts], marker_color=C_RED, marker_cornerradius=3))
            f1.update_layout(**L(barmode="group", margin=dict(l=10,r=10,t=10,b=80)))
            f1.update_xaxes(tickangle=30)
            pf(f1)

        with col_r:
            sh("% Asignadas por turno")
            pct_list = [int(100*shift_stats[s]["asignadas"]/shift_stats[s]["total"]) if shift_stats[s]["total"] else 0 for s in active_shifts]
            f2 = px.bar(pd.DataFrame({"Turno":active_shifts,"Pct":pct_list}),
                        x="Turno", y="Pct", color="Pct",
                        color_continuous_scale=[C_RED, C_ORANGE, C_GREEN],
                        text=[f"{p}%" for p in pct_list])
            f2.update_layout(**L(coloraxis_showscale=False, margin=dict(l=10,r=10,t=10,b=80), yaxis_title="%"))
            f2.update_xaxes(tickangle=30)
            f2.update_traces(marker_cornerradius=5, textposition="outside")
            pf(f2)

        sh("Heatmap — sesiones por turno y día")
        all_days = sorted(daily_shift.keys())
        df_heat = pd.DataFrame(
            [[daily_shift[d].get(s,0) for d in all_days] for s in active_shifts],
            index=active_shifts, columns=all_days)
        fh = px.imshow(df_heat, aspect="auto",
                       color_continuous_scale=[S2, S3, C_BLUE, C_GREEN],
                       text_auto=True)
        fh.update_layout(**L(margin=dict(l=140,r=10,t=10,b=60)))
        fh.update_xaxes(tickangle=30)
        pf(fh)

        sh("Tabla detallada por turno")
        tbl = [{"Agente/Turno":s,"Total":shift_stats[s]["total"],
                "Asignadas":shift_stats[s]["asignadas"],
                "No asignadas":shift_stats[s]["no_asignadas"],
                "Respondidas":shift_stats[s]["respondidas"],
                "Cierres":shift_stats[s]["cierres"],
                "% Asignadas":f"{int(100*shift_stats[s]['asignadas']/shift_stats[s]['total']) if shift_stats[s]['total'] else 0}%",
                "% Respondidas":f"{int(100*shift_stats[s]['respondidas']/shift_stats[s]['total']) if shift_stats[s]['total'] else 0}%",
               } for s in active_shifts]
        st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# TAB: PRODUCTIVIDAD
# ══════════════════════════════════════════════════════════
with tab_prod:
    with st.spinner("Cargando…"):
        sc_ap, d_ap = api_get("agents")
        sc_sp, d_sp = api_get("sessions", {"from":FROM_STR,"to":TO_STR,"include-events":"true"})
        sc_cp, d_cp = api_get("chats",    {"from":FROM_STR})

    ag_lp  = its(d_ap) if sc_ap == 200 else []
    ses_lp = its(d_sp) if sc_sp == 200 else []
    cht_lp = its(d_cp) if sc_cp == 200 else []
    ag_mp  = {a["id"]: a for a in ag_lp}

    prod, tl = {}, []
    for s in ses_lp:
        for e in s.get("events",[]):
            info    = e.get("info",{})
            ev_name = e.get("name","")
            ag_name = info.get("agentName","")
            ag_id   = info.get("agentId","")
            if not ag_name: continue
            if ag_name not in prod:
                prod[ag_name] = {"id":ag_id,"asig":0,"acc":0,"cierre":0}
            if ev_name=="assigned-to-agent":
                prod[ag_name]["asig"] += 1
                tl.append({"fecha":e.get("creationTime","")[:10],"agente":ag_name})
            elif ev_name=="agent-action":        prod[ag_name]["acc"]    += 1
            elif ev_name=="conversation-close":  prod[ag_name]["cierre"] += 1

    chats_xp = Counter(c.get("agentId","") for c in cht_lp if c.get("agentId"))
    prod_rows = []
    for name, m in prod.items():
        ag  = ag_mp.get(m["id"],{})
        eff = round(100*m["cierre"]/m["asig"],1) if m["asig"] else 0
        prod_rows.append({"Nombre":name,"isOnline":ag.get("isOnline",False),
            "Status":ag.get("status","—"),"Queues":", ".join(ag.get("queues",[])),
            "Chats activos":chats_xp.get(m["id"],0),
            "Asignaciones":m["asig"],"Acciones":m["acc"],"Cierres":m["cierre"],"Eficiencia %":eff})
    prod_rows.sort(key=lambda x: x["Asignaciones"], reverse=True)

    if not prod_rows:
        st.info("Sin datos de productividad para el período seleccionado.")
    else:
        k1,k2,k3,k4 = st.columns(4)
        with k1: kpi("Asignaciones", sum(r["Asignaciones"] for r in prod_rows), f"{d_from}–{d_to}","accent",C_BLUE)
        with k2: kpi("Acciones",     sum(r["Acciones"]     for r in prod_rows), "agent-action","green",C_GREEN)
        with k3: kpi("Cierres",      sum(r["Cierres"]      for r in prod_rows), "conversation-close","orange",C_ORANGE)
        with k4: kpi("Top agente",   prod_rows[0]["Nombre"], f"{prod_rows[0]['Asignaciones']} asig.","purple",C_PURPLE)

        st.markdown("")
        col_l, col_r = st.columns(2)
        with col_l:
            sh("Asignaciones por agente")
            f1 = px.bar(x=[r["Asignaciones"] for r in prod_rows],
                        y=[r["Nombre"]       for r in prod_rows], orientation="h",
                        color=[r["Asignaciones"] for r in prod_rows],
                        color_continuous_scale=[S2, C_BLUE])
            f1.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=10,t=10,b=10)))
            f1.update_traces(marker_cornerradius=4); pf(f1)

            sh("Acciones vs Cierres")
            f2 = go.Figure()
            f2.add_trace(go.Bar(name="Acciones", x=[r["Nombre"] for r in prod_rows],
                                y=[r["Acciones"] for r in prod_rows], marker_color=C_BLUE, marker_cornerradius=4))
            f2.add_trace(go.Bar(name="Cierres",  x=[r["Nombre"] for r in prod_rows],
                                y=[r["Cierres"]  for r in prod_rows], marker_color=C_GREEN, marker_cornerradius=4))
            f2.update_layout(**L(barmode="group")); pf(f2)

        with col_r:
            sh("Eficiencia de cierre (%)")
            f3 = px.bar(x=[r["Eficiencia %"] for r in prod_rows],
                        y=[r["Nombre"]        for r in prod_rows], orientation="h",
                        color=[r["Eficiencia %"] for r in prod_rows],
                        color_continuous_scale=[C_RED, C_ORANGE, C_GREEN])
            f3.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=10,t=10,b=10)))
            f3.update_traces(marker_cornerradius=4); pf(f3)

            sh("Distribución de asignaciones")
            f4 = px.pie(names=[r["Nombre"]        for r in prod_rows],
                        values=[r["Asignaciones"]  for r in prod_rows], hole=0.55)
            f4.update_layout(**L(margin=dict(l=0,r=0,t=10,b=0))); pf(f4)

        sh("Tabla de productividad")
        df_d = pd.DataFrame(prod_rows)
        df_d["isOnline"] = df_d["isOnline"].map({True:"🟢 Sí",False:"⚫ No"})
        st.dataframe(df_d, use_container_width=True, hide_index=True)

        if tl:
            sh("Asignaciones por día")
            pivot = pd.DataFrame(tl).groupby(["fecha","agente"]).size().reset_index(name="n")
            f5 = px.bar(pivot, x="fecha", y="n", color="agente", barmode="stack")
            f5.update_layout(**L()); f5.update_traces(marker_cornerradius=3); pf(f5)


# ══════════════════════════════════════════════════════════
# TAB: SESIONES
# ══════════════════════════════════════════════════════════
with tab_ses:
    with st.spinner("Cargando sesiones…"):
        sc_ses, d_ses = api_get("sessions", {"from":FROM_STR,"to":TO_STR,"include-events":"true"})

    if sc_ses == 200:
        ses = its(d_ses)
        all_ev = [e["name"] for s in ses for e in s.get("events",[])]
        k1,k2,k3,k4 = st.columns(4)
        with k1: kpi("Sesiones", len(ses), f"{d_from}–{d_to}","accent",C_BLUE)
        with k2: kpi("Orgánicas", sum(1 for s in ses if s.get("startingCause")=="Organic"),"","green",C_GREEN)
        with k3: kpi("Vía Template WA", sum(1 for s in ses if s.get("startingCause")=="WhatsAppTemplate"),"","orange",C_ORANGE)
        with k4: kpi("Eventos totales", len(all_ev),"","purple",C_PURPLE)
        st.markdown("")
        col_l, col_r = st.columns(2)
        with col_l:
            df_ses = pd.DataFrame(ses)
            df_ses["ts"] = pd.to_datetime(df_ses["creationTime"], errors="coerce")
            by = df_ses.groupby([df_ses["ts"].dt.date,"startingCause"]).size().reset_index(name="n")
            by.columns = ["Fecha","Origen","n"]
            f1 = px.bar(by, x="Fecha", y="n", color="Origen", barmode="stack",
                        color_discrete_map={"Organic":"#4f6ef7","WhatsAppTemplate":"#f5a524"})
            f1.update_layout(**L()); f1.update_traces(marker_cornerradius=3); pf(f1)
        with col_r:
            ev_df = pd.Series(all_ev).value_counts().reset_index(); ev_df.columns=["Evento","n"]
            f2 = px.bar(ev_df, x="n", y="Evento", orientation="h",
                        color="n", color_continuous_scale=[S2, C_PURPLE])
            f2.update_layout(**L(coloraxis_showscale=False, margin=dict(l=170,r=10,t=10,b=10)))
            f2.update_traces(marker_cornerradius=3); pf(f2)
        sh("Detalle")
        rows = [{"Fecha":s.get("creationTime","")[:16].replace("T"," "),
                 "Origen":s.get("startingCause",""),
                 "Nombre":s.get("chat",{}).get("firstName",""),
                 "Canal":s.get("chat",{}).get("chat",{}).get("channelId","").split("-")[-1],
                 "Eventos":len(s.get("events",[]))} for s in ses[:300]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.error(f"Error {sc_ses}: {d_ses}")


# ══════════════════════════════════════════════════════════
# TAB: CANALES & TEMPLATES
# ══════════════════════════════════════════════════════════
with tab_extra:
    col_l, col_r = st.columns(2)

    with col_l:
        sh("Canales")
        if st.button("Cargar canales"):
            sc_ch, d_ch = api_get("channels")
            if sc_ch == 200:
                chs = its(d_ch)
                kpi("Canales", len(chs), f"{sum(1 for c in chs if c.get('active'))} activos","sky",C_SKY)
                st.markdown("")
                plat = pd.Series([c.get("platform","") for c in chs]).value_counts().reset_index(); plat.columns=["P","n"]
                f = px.bar(plat, x="P", y="n", color="P"); f.update_layout(**L()); f.update_traces(marker_cornerradius=5); pf(f)
                st.dataframe(pd.DataFrame([{"Plataforma":c["platform"],"Activo":"✅" if c.get("active") else "❌","Número":c.get("number","")} for c in chs]),use_container_width=True,hide_index=True)

    with col_r:
        sh("Templates WhatsApp")
        if st.button("Cargar templates"):
            sc_t, d_t = api_get("whatsapp/templates")
            if sc_t == 200:
                tpls = its(d_t)
                kpi("Templates", len(tpls), f"MARKETING: {sum(1 for t in tpls if t.get('category')=='MARKETING')}","accent",C_BLUE)
                st.markdown("")
                cf = pd.Series([t.get("category","") for t in tpls]).value_counts().reset_index(); cf.columns=["Cat","n"]
                ft = px.pie(cf, names="Cat", values="n", hole=0.55,
                            color_discrete_map={"MARKETING":"#f5a524","UTILITY":"#4f6ef7"}); ft.update_layout(**L()); pf(ft)
                st.dataframe(pd.DataFrame([{"Nombre":t.get("name",""),"Estado":t.get("state",""),
                    "Categoría":t.get("category",""),"Idioma":t.get("locale","")} for t in tpls]),
                    use_container_width=True,hide_index=True)
