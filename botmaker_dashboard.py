"""
╔══════════════════════════════════════════════════════════════════════╗
║  KASHIO · SUPPORT OPERATIONS DASHBOARD  ·  Botmaker API v2.0        ║
║                                                                      ║
║  Arquitectura analítica:                                             ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │ Tab 1 · Tiempo Real     – Cola viva, agentes, pendientes    │    ║
║  │ Tab 2 · SLA & Tiempos   – FRT, AHT, resolución, SLA %      │    ║
║  │ Tab 3 · Equipo          – Productividad, ranking, carga     │    ║
║  │ Tab 4 · Turnos          – Cobertura, sesiones por turno     │    ║
║  │ Tab 5 · Alertas         – Sistema de alertas inteligente    │    ║
║  │ Tab 6 · Tendencias      – Comparativas, semanas, patrones   │    ║
║  └─────────────────────────────────────────────────────────────┘    ║
║                                                                      ║
║  KPIs implementados:                                                 ║
║  • FRT   – First Response Time (desde sesión hasta primer reply)    ║
║  • AHT   – Average Handle Time (desde asignación hasta cierre)      ║
║  • WAIT  – Tiempo actual de espera (chats pendientes en cola)       ║
║  • RES   – Tasa de resolución / cierre de sesiones                  ║
║  • ASGN  – Tasa de asignación (sesiones atendidas por agente)       ║
║  • SLA%  – % sesiones dentro del umbral de FRT configurado          ║
║  • LOAD  – Carga real vs capacidad (chats / slots por agente)       ║
║  • TRANS – Transferencias entre queues detectadas                   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
from typing import Optional

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

BASE_URL    = "https://api.botmaker.com/v2.0"
LIMA_OFFSET = timedelta(hours=-5)

# ── Clasificación de queues de soporte ───────────────────
# Editar según la configuración real de Botmaker
SUPPORT_QUEUES  = {"Soporte N1", "Soporte N2", "_default_"}
COMERCIAL_QUEUES = {"Comercial", "Ventas"}

# ── SLA thresholds (en minutos) ──────────────────────────
SLA_FRT_OK   = 15    # ≤15min  → cumple SLA
SLA_FRT_WARN = 60    # ≤60min  → en riesgo
# >60min → incumplimiento SLA

SLA_WAIT_OK   = 30   # ≤30min  → aceptable
SLA_WAIT_WARN = 120  # ≤120min → atención requerida
# >120min → crítico

SLA_AHT_OK   = 120   # ≤2h    → buena gestión
SLA_AHT_WARN = 480   # ≤8h    → en riesgo

ALERT_UNASSIGNED_MAX = 5  # chats sin asignar → alerta

# ── Configuración de turnos (hora Lima) ─────────────────
SHIFTS = [
    ("Alonso Loyola",      [0,1,2,3,4],  6, 14, "Soporte Mañana"),
    ("José Luis Cahuana",  [0,1,2,3,4], 14, 22, "Soporte Tarde"),
    ("Deivy Chavez Trejo", [0,1,2,3,4], 22,  6, "Soporte Noche"),
    ("Daniel Huayta",      [5,6],        6, 14, "Fin Semana Mañana"),
    ("Luz Goicochea",      [5,6],       14, 22, "Fin Semana Tarde"),
    ("Joe Villanueva",     [5,6],       22,  6, "Fin Semana Noche"),
    ("Victor Macedo",      [0,1,2,3,4],  9, 18, "Comercial"),
    ("José Luis Cahuana",  [0,1,2,3,4],  9, 18, "Soporte Día"),
]
SHIFT_ORDER = ["Alonso Loyola","José Luis Cahuana","Deivy Chavez Trejo",
               "Daniel Huayta","Luz Goicochea","Joe Villanueva","Victor Macedo"]

def get_shift_label(dt_utc: datetime) -> str:
    lima = dt_utc + LIMA_OFFSET
    wd, h = lima.weekday(), lima.hour
    if wd in [0,1,2,3,4]:
        if  6 <= h < 14: return "Alonso Loyola"
        if 14 <= h < 22: return "José Luis Cahuana"
        return "Deivy Chavez Trejo"
    if  6 <= h < 14: return "Daniel Huayta"
    if 14 <= h < 22: return "Luz Goicochea"
    return "Joe Villanueva"

# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="Kashio · Soporte", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

if "dark_mode" not in st.session_state: st.session_state.dark_mode = True
if "live_on"   not in st.session_state: st.session_state.live_on   = False

dark = st.session_state.dark_mode

# ═══════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════
if dark:
    BG, S1, S2, S3       = "#07080c","#0e1018","#141720","#1a1f2c"
    BORDER, BORDER2       = "#1e2333","#252c40"
    TEXT, TEXT2, MUTED    = "#e6e8f0","#c4c9db","#555e7a"
    GRID                  = "#1a1f2e"
    CHART_BG              = "rgba(0,0,0,0)"
    FONT_COL              = "#8892aa"
    SB_BG                 = "#0e1018"
    SHADOW, SHADOW_MD     = "none","none"
    C_BLUE   = "#4f6ef7"; C_GREEN  = "#22d47b"; C_ORANGE = "#f5a524"
    C_RED    = "#f25c5c"; C_PURPLE = "#a78bfa"; C_SKY    = "#38bdf8"
    C_CORAL  = "#fb923c"; C_PINK   = "#e879f9"
else:
    BG, S1, S2, S3       = "#edf0f9","#ffffff","#f3f5fc","#e8ecf7"
    BORDER, BORDER2       = "#d4daf0","#c2cbec"
    TEXT, TEXT2, MUTED    = "#0d1229","#2e3657","#5a6890"
    GRID                  = "#dce2f4"
    CHART_BG              = "#ffffff"
    FONT_COL              = "#4a5578"
    SB_BG                 = "#f8faff"
    SHADOW     = "0 1px 4px rgba(20,28,80,.06), 0 4px 16px rgba(20,28,80,.06)"
    SHADOW_MD  = "0 2px 8px rgba(20,28,80,.10), 0 8px 24px rgba(20,28,80,.08)"
    C_BLUE   = "#3d5ce8"; C_GREEN  = "#0ea85e"; C_ORANGE = "#d97706"
    C_RED    = "#dc3545"; C_PURPLE = "#7c5cbf"; C_SKY    = "#0891b2"
    C_CORAL  = "#ea580c"; C_PINK   = "#c026d3"

COLORWAY = [C_BLUE, C_GREEN, C_ORANGE, C_RED, C_PURPLE, C_SKY, C_CORAL, C_PINK]
SHIFT_PAL = {"Alonso Loyola":C_BLUE,"José Luis Cahuana":C_ORANGE,
             "Deivy Chavez Trejo":C_PURPLE,"Daniel Huayta":C_GREEN,
             "Luz Goicochea":C_SKY,"Joe Villanueva":C_RED,"Victor Macedo":C_CORAL}

# ─────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500;600&display=swap');

html,body,[class*="css"]{{font-family:'Inter',sans-serif;color:{TEXT};}}
.stApp{{background:{BG}!important;}}
section[data-testid="stSidebar"]{{background:{SB_BG}!important;border-right:1px solid {BORDER}!important;{f'box-shadow:2px 0 20px rgba(20,28,80,.08);' if not dark else ''}}}
section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] div{{color:{TEXT}!important;}}

/* ── KPI ── */
.kpi{{background:{S1};border:1px solid {BORDER};border-radius:14px;padding:16px 18px;
  position:relative;overflow:hidden;box-shadow:{SHADOW};transition:all .2s;}}
.kpi:hover{{box-shadow:{SHADOW_MD};transform:translateY(-1px);}}
.kpi::after{{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:14px 14px 0 0;}}
.kpi-blue::after{{background:{C_BLUE};}} .kpi-green::after{{background:{C_GREEN};}}
.kpi-orange::after{{background:{C_ORANGE};}} .kpi-red::after{{background:{C_RED};}}
.kpi-purple::after{{background:{C_PURPLE};}} .kpi-sky::after{{background:{C_SKY};}}
.kpi-coral::after{{background:{C_CORAL};}}
.kpi-label{{font-size:.67rem;letter-spacing:.1em;text-transform:uppercase;color:{MUTED};font-weight:700;margin-bottom:4px;}}
.kpi-value{{font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;line-height:1;}}
.kpi-sub{{font-size:.72rem;color:{MUTED};margin-top:4px;}}
.kpi-delta-good{{font-size:.75rem;color:{C_GREEN};font-weight:600;margin-top:2px;}}
.kpi-delta-bad{{font-size:.75rem;color:{C_RED};font-weight:600;margin-top:2px;}}

/* ── Agent card ── */
.ac{{background:{S1};border:1px solid {BORDER};border-radius:12px;padding:12px 14px;
  display:flex;align-items:center;gap:12px;box-shadow:{SHADOW};transition:all .2s;}}
.ac:hover{{box-shadow:{SHADOW_MD};border-color:{BORDER2};}}
.av{{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-family:'Syne',sans-serif;font-weight:800;font-size:.88rem;flex-shrink:0;}}
.an{{font-size:.84rem;font-weight:600;color:{TEXT};}}
.am{{font-size:.69rem;color:{MUTED};margin-top:2px;}}
.ab{{padding:3px 8px;border-radius:20px;font-size:.65rem;font-weight:700;
  font-family:'Syne',sans-serif;white-space:nowrap;}}
.od{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px;vertical-align:middle;}}

/* ── Alert cards ── */
.alert-crit{{background:rgba(220,53,69,.07);border:1px solid rgba(220,53,69,.3);
  border-left:4px solid {C_RED};border-radius:0 10px 10px 0;padding:12px 16px;margin:5px 0;}}
.alert-warn{{background:rgba(217,119,6,.07);border:1px solid rgba(217,119,6,.3);
  border-left:4px solid {C_ORANGE};border-radius:0 10px 10px 0;padding:12px 16px;margin:5px 0;}}
.alert-info{{background:rgba(8,145,178,.07);border:1px solid rgba(8,145,178,.3);
  border-left:4px solid {C_SKY};border-radius:0 10px 10px 0;padding:12px 16px;margin:5px 0;}}
.alert-ok{{background:rgba(14,168,94,.07);border:1px solid rgba(14,168,94,.3);
  border-left:4px solid {C_GREEN};border-radius:0 10px 10px 0;padding:12px 16px;margin:5px 0;}}
.alert-title{{font-family:'Syne',sans-serif;font-size:.82rem;font-weight:700;color:{TEXT};}}
.alert-body{{font-size:.76rem;color:{MUTED};margin-top:3px;}}

/* ── Section header ── */
.sh{{font-family:'Syne',sans-serif;font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;
  color:{MUTED};font-weight:700;padding-bottom:6px;border-bottom:2px solid {BORDER};
  margin:20px 0 12px;display:flex;align-items:center;justify-content:space-between;}}

/* ── SLA badge ── */
.sla-ok{{background:rgba(14,168,94,.12);color:{C_GREEN};border:1px solid rgba(14,168,94,.3);
  padding:2px 8px;border-radius:20px;font-size:.68rem;font-weight:700;}}
.sla-warn{{background:rgba(217,119,6,.12);color:{C_ORANGE};border:1px solid rgba(217,119,6,.3);
  padding:2px 8px;border-radius:20px;font-size:.68rem;font-weight:700;}}
.sla-fail{{background:rgba(220,53,69,.12);color:{C_RED};border:1px solid rgba(220,53,69,.3);
  padding:2px 8px;border-radius:20px;font-size:.68rem;font-weight:700;}}

/* ── Sidebar ── */
.sb-section{{background:{S2};border:1px solid {BORDER};border-radius:10px;
  padding:12px 14px;margin-bottom:10px;}}
.sb-label{{font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;
  color:{MUTED};font-weight:700;margin-bottom:8px;font-family:'Syne',sans-serif;}}
.sb-stat{{background:{S1};border:1px solid {BORDER};border-radius:8px;
  padding:8px 12px;margin:4px 0;display:flex;justify-content:space-between;align-items:center;}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{{background:{S1};border-radius:12px;padding:4px;
  border:1px solid {BORDER};gap:2px;box-shadow:{SHADOW};}}
.stTabs [data-baseweb="tab"]{{color:{MUTED}!important;font-family:'Syne',sans-serif!important;
  font-size:.77rem!important;font-weight:600!important;border-radius:8px!important;
  padding:8px 14px!important;transition:all .15s!important;}}
.stTabs [data-baseweb="tab"]:hover{{background:{S2}!important;color:{TEXT}!important;}}
.stTabs [aria-selected="true"]{{background:{C_BLUE}!important;color:#fff!important;}}

/* ── Inputs & controls ── */
.stButton>button{{background:{C_BLUE}!important;color:#fff!important;
  font-family:'Syne',sans-serif!important;font-weight:700!important;font-size:.79rem!important;
  border:none!important;border-radius:8px!important;padding:8px 18px!important;
  box-shadow:{SHADOW}!important;transition:all .2s!important;}}
.stButton>button:hover{{opacity:.88!important;box-shadow:{SHADOW_MD}!important;}}
.stSelectbox>div>div,.stNumberInput>div>div>input,.stDateInput>div>div>input{{
  background:{S2}!important;border:1.5px solid {BORDER}!important;
  color:{TEXT}!important;border-radius:8px!important;font-size:.83rem!important;}}
div[data-testid="stDateInput"] label,div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label,div[data-testid="stSlider"] label{{
  color:{MUTED}!important;font-size:.72rem!important;font-weight:700!important;
  letter-spacing:.05em!important;text-transform:uppercase!important;}}
.stDataFrame{{border-radius:10px;overflow:hidden;box-shadow:{SHADOW};}}
.stDataFrame thead th{{background:{S3}!important;color:{TEXT2}!important;
  font-size:.73rem!important;font-weight:700!important;text-transform:uppercase!important;letter-spacing:.04em!important;}}
.stDataFrame tbody td{{background:{S1}!important;color:{TEXT}!important;font-size:.81rem!important;}}
.stDataFrame tbody tr:hover td{{background:{S2}!important;}}
div[data-testid="stToggle"]>label{{font-size:.81rem!important;color:{TEXT}!important;font-weight:500!important;}}
hr{{border-color:{BORDER};margin:6px 0;}}
[data-testid="stMarkdownContainer"] p{{color:{TEXT}!important;}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.ld{{display:inline-block;width:8px;height:8px;border-radius:50%;
  background:{C_RED};animation:pulse 1.2s infinite;margin-right:5px;vertical-align:middle;}}
</style>""", unsafe_allow_html=True)

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
_LBG = "rgba(14,16,24,.9)" if dark else "rgba(255,255,255,.95)"
_BL = dict(
    paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
    font=dict(family="Inter", color=FONT_COL, size=12),
    xaxis=dict(gridcolor=GRID, linecolor=GRID, zerolinecolor=GRID,
               tickfont=dict(color=FONT_COL)),
    yaxis=dict(gridcolor=GRID, linecolor=GRID, zerolinecolor=GRID,
               tickfont=dict(color=FONT_COL)),
    legend=dict(bgcolor=_LBG, bordercolor=BORDER, font=dict(color=TEXT, size=11)),
    colorway=COLORWAY,
)
def L(**kw):
    r = dict(_BL)
    r.setdefault("margin", dict(l=10,r=10,t=36,b=10))
    r.update(kw)
    return r
def pf(f, height=None):
    kw = {"use_container_width": True, "config": {"displayModeBar": False}}
    if height: kw["height"] = height
    st.plotly_chart(f, **kw)

# ─────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────
def hdrs(): return {"access-token": TOKEN, "Content-Type": "application/json"}
@st.cache_data(ttl=30)
def api_get_cached(path, params_key=""):
    """Cached version for heavy endpoints."""
    try:
        params = dict(p.split("=",1) for p in params_key.split("&") if "=" in p) if params_key else None
        r = requests.get(f"{BASE_URL}/{path}", headers=hdrs(), params=params, timeout=25)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return -1, str(e)

def api_get(path, params=None):
    try:
        r = requests.get(f"{BASE_URL}/{path}", headers=hdrs(), params=params, timeout=25)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return -1, str(e)

def its(resp):
    if isinstance(resp, dict): return resp.get("items", [])
    if isinstance(resp, list): return resp
    return []

# ─────────────────────────────────────────────────────────
# KPI CALCULATIONS  (funciones puras, testeables)
# ─────────────────────────────────────────────────────────
def parse_dt(s: str) -> Optional[datetime]:
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z","+00:00"))
    except: return None

def to_lima_str(dt: datetime) -> str:
    return (dt + LIMA_OFFSET).strftime("%d/%m %H:%M")

def fmt_mins(m: float) -> str:
    if m < 0:   return "—"
    if m < 60:  return f"{int(m)}m"
    if m < 1440: return f"{m/60:.1f}h"
    return f"{m/1440:.1f}d"

def sev_cls(m: float, ok: float, warn: float) -> str:
    if m <= ok:   return "sla-ok"
    if m <= warn: return "sla-warn"
    return "sla-fail"

def sev_color(m: float, ok: float = SLA_WAIT_OK, warn: float = SLA_WAIT_WARN) -> str:
    if m <= ok:   return C_GREEN
    if m <= warn: return C_ORANGE
    return C_RED

def compute_session_kpis(sessions: list) -> pd.DataFrame:
    """
    Para cada sesión extrae:
    - frt_min        : First Response Time en minutos
    - assign_delay   : minutos hasta assigned-to-agent
    - aht_min        : Average Handle Time (assign → close)
    - resolved       : bool, tiene conversation-close
    - assigned       : bool, tiene assigned-to-agent
    - agent_name     : nombre del agente principal
    - n_transfers    : número de re-asignaciones (indica transfers)
    - n_actions      : acciones del agente
    """
    rows = []
    for s in sessions:
        t0       = parse_dt(s.get("creationTime",""))
        if not t0: continue

        t_assign   = None
        t_frt      = None   # primer agent-action
        t_close    = None
        agent_name = ""
        n_assigns  = 0
        n_actions  = 0
        assign_agents = []

        for e in s.get("events", []):
            et   = parse_dt(e.get("creationTime",""))
            info = e.get("info",{})
            name = e.get("name","")

            if name == "assigned-to-agent":
                n_assigns += 1
                assign_agents.append(info.get("agentName",""))
                if not t_assign:
                    t_assign   = et
                    agent_name = info.get("agentName","")
            elif name == "agent-action":
                n_actions += 1
                if not t_frt: t_frt = et
            elif name == "conversation-close":
                t_close = et

        frt_min      = (t_frt - t0).total_seconds()/60    if (t_frt and t0) else None
        assign_delay = (t_assign - t0).total_seconds()/60 if (t_assign and t0) else None
        aht_min      = (t_close - t_assign).total_seconds()/60 if (t_close and t_assign) else None

        rows.append({
            "session_id":    s.get("id",""),
            "date":          (t0 + LIMA_OFFSET).date(),
            "hour":          (t0 + LIMA_OFFSET).hour,
            "start_time":    t0,
            "shift":         get_shift_label(t0),
            "cause":         s.get("startingCause",""),
            "agent":         agent_name,
            "n_assigns":     n_assigns,
            "n_actions":     n_actions,
            "assigned":      n_assigns > 0,
            "resolved":      t_close is not None,
            "transferred":   n_assigns > 1,
            "frt_min":       frt_min,
            "assign_delay":  assign_delay,
            "aht_min":       aht_min,
            "frt_sla_ok":    frt_min <= SLA_FRT_OK   if frt_min is not None else None,
            "frt_sla_warn":  frt_min <= SLA_FRT_WARN if frt_min is not None else None,
        })
    return pd.DataFrame(rows)

def compute_live_chat_metrics(chats: list, agents: list, now: datetime) -> dict:
    """
    Métricas en tiempo real desde la lista de chats activos.
    Retorna dict con conteos y listas filtradas.
    """
    ag_map = {a["id"]: a for a in agents}

    # Filtrar soporte vs comercial
    support  = [c for c in chats if c.get("queueId","") in SUPPORT_QUEUES or not c.get("queueId")]
    # Comercial separado
    comercial = [c for c in chats if c.get("queueId","") in COMERCIAL_QUEUES]

    unassigned  = [c for c in chats if not c.get("agentId")]
    pending     = [c for c in chats if c.get("isBotMuted") and c.get("agentId")]

    # Calcular tiempo de espera real para cada chat pendiente
    pending_with_wait = []
    for c in pending:
        lu = c.get("lastUserMessageDatetime","")
        dt = parse_dt(lu)
        if dt:
            wait_min = (now - dt).total_seconds() / 60
        else:
            wait_min = 0
        aid = c.get("agentId","")
        ag  = ag_map.get(aid, {})
        pending_with_wait.append({
            **c,
            "wait_min":   wait_min,
            "wait_fmt":   fmt_mins(wait_min),
            "sev_cls":    sev_cls(wait_min, SLA_WAIT_OK, SLA_WAIT_WARN),
            "agent_name": ag.get("name","—"),
        })
    pending_with_wait.sort(key=lambda x: x["wait_min"], reverse=True)

    # Carga por agente
    chats_per_agent = Counter(c.get("agentId","") for c in chats if c.get("agentId"))
    wait_per_agent  = defaultdict(list)
    for p in pending_with_wait:
        wait_per_agent[p.get("agentId","")].append(p["wait_min"])

    # WA windows próximas a vencer (< 2h)
    wa_expiring = []
    for c in chats:
        wd = c.get("whatsAppWindowCloseDatetime","")
        dt = parse_dt(wd)
        if dt:
            diff_h = (dt - now).total_seconds() / 3600
            if -1 < diff_h < 2:   # vence en menos de 2h o venció hace < 1h
                wa_expiring.append({**c, "exp_h": diff_h})

    return {
        "all":              chats,
        "support":          support,
        "comercial":        comercial,
        "unassigned":       unassigned,
        "pending":          pending_with_wait,
        "chats_per_agent":  chats_per_agent,
        "wait_per_agent":   wait_per_agent,
        "wa_expiring":      wa_expiring,
        "queues":           Counter(c.get("queueId") or "Sin queue" for c in chats),
        "countries":        Counter(c.get("country","?") for c in chats),
    }

def compute_agent_productivity(df_kpis: pd.DataFrame, chats_per_agent: Counter,
                               agents: list) -> pd.DataFrame:
    """
    Combina métricas de sesiones con datos de agentes en tiempo real.
    """
    ag_map = {a["name"]: a for a in agents}
    ag_id_map = {a["id"]: a for a in agents}

    rows = []
    if df_kpis.empty: return pd.DataFrame()

    for agent, grp in df_kpis.groupby("agent"):
        if not agent: continue
        ag_info     = ag_map.get(agent, {})
        total       = len(grp)
        assigned    = int(grp["assigned"].sum())
        resolved    = int(grp["resolved"].sum())
        transferred = int(grp["transferred"].sum())
        frt_vals    = grp["frt_min"].dropna()
        aht_vals    = grp["aht_min"].dropna()
        sla_ok      = int(grp["frt_sla_ok"].dropna().sum())
        sla_total   = int(grp["frt_sla_ok"].dropna().count())

        # Carga actual
        ag_id = ag_info.get("id","")
        chats_now = chats_per_agent.get(ag_id, 0)
        slots     = ag_info.get("slots", 0) or 1
        load_pct  = round(chats_now / slots * 100) if slots else 0

        rows.append({
            "Agente":         agent,
            "isOnline":       ag_info.get("isOnline", False),
            "Status":         ag_info.get("status","—"),
            "Sesiones":       total,
            "Asignaciones":   assigned,
            "Resueltas":      resolved,
            "Transferidas":   transferred,
            "% Resolución":   round(resolved/assigned*100, 1) if assigned else 0,
            "% Transferencia":round(transferred/assigned*100,1) if assigned else 0,
            "FRT prom (min)": round(frt_vals.mean(), 1) if len(frt_vals) else None,
            "FRT p80 (min)":  round(np.percentile(frt_vals, 80), 1) if len(frt_vals) else None,
            "AHT prom (min)": round(aht_vals.mean(), 1) if len(aht_vals) else None,
            "SLA FRT %":      round(sla_ok/sla_total*100, 1) if sla_total else None,
            "Chats activos":  chats_now,
            "Slots":          ag_info.get("slots", 0),
            "Carga %":        load_pct,
        })

    df = pd.DataFrame(rows).sort_values("Asignaciones", ascending=False)
    return df

def build_alerts(live: dict, df_kpis: pd.DataFrame,
                 df_agents_prod: pd.DataFrame, agents: list,
                 now: datetime, sla_frt_warn: int) -> list:
    """
    Motor de alertas inteligente.
    Retorna lista de dicts: {level: 'crit|warn|info|ok', title, body, metric}
    """
    alerts = []
    ag_map = {a["id"]: a for a in agents}

    # 1. Chats sin asignar
    n_unassigned = len(live["unassigned"])
    if n_unassigned >= ALERT_UNASSIGNED_MAX:
        alerts.append({"level":"crit",
            "title": f"🚨 {n_unassigned} chats sin asignar",
            "body": "Supera el umbral máximo. Revisar cola y disponibilidad de agentes.",
            "metric": n_unassigned})
    elif n_unassigned > 0:
        alerts.append({"level":"warn",
            "title": f"⚠️ {n_unassigned} chats sin asignar",
            "body": "Chats en espera de asignación.",
            "metric": n_unassigned})

    # 2. Chats con espera crítica (> SLA_WAIT_WARN minutos)
    critical_waits = [p for p in live["pending"] if p["wait_min"] > SLA_WAIT_WARN]
    if critical_waits:
        longest = critical_waits[0]
        alerts.append({"level":"crit",
            "title": f"🔴 {len(critical_waits)} chat(s) con espera crítica (>{SLA_WAIT_WARN//60}h)",
            "body": f"Más crítico: {longest.get('firstName','?')} esperando {longest['wait_fmt']} — Agente: {longest['agent_name']}",
            "metric": len(critical_waits)})

    # 3. Agentes sobrecargados (chats > slots)
    for ag in agents:
        aid      = ag.get("id","")
        chats_n  = live["chats_per_agent"].get(aid, 0)
        slots    = ag.get("slots", 0) or 1
        if ag.get("isOnline") and chats_n > slots:
            alerts.append({"level":"warn",
                "title": f"⚠️ {ag.get('name','?')} sobrecargado",
                "body":  f"{chats_n} chats activos vs {slots} slots disponibles ({round(chats_n/slots*100)}% carga)",
                "metric": chats_n})

    # 4. Agentes online sin chats asignados (posible inactividad)
    for ag in agents:
        if not ag.get("isOnline"): continue
        aid    = ag.get("id","")
        chats_n = live["chats_per_agent"].get(aid, 0)
        # Solo alertar si hay chats sin asignar Y el agente no tiene nada
        if chats_n == 0 and n_unassigned > 0:
            alerts.append({"level":"info",
                "title": f"ℹ️ {ag.get('name','?')} en línea sin chats asignados",
                "body":  f"Hay {n_unassigned} chats esperando. Verificar si el agente está activo.",
                "metric": 0})

    # 5. SLA FRT comprometido
    if not df_kpis.empty:
        frt_valid = df_kpis["frt_min"].dropna()
        if len(frt_valid) >= 5:
            breach_pct = round((frt_valid > sla_frt_warn).mean() * 100, 1)
            if breach_pct > 40:
                alerts.append({"level":"crit",
                    "title": f"🚨 SLA FRT en rojo: {breach_pct}% de sesiones superan {sla_frt_warn}min",
                    "body":  f"FRT promedio: {fmt_mins(frt_valid.mean())}. Revisar proceso de asignación.",
                    "metric": breach_pct})
            elif breach_pct > 20:
                alerts.append({"level":"warn",
                    "title": f"⚠️ SLA FRT en riesgo: {breach_pct}% sobre umbral",
                    "body":  f"FRT promedio: {fmt_mins(frt_valid.mean())}.",
                    "metric": breach_pct})

    # 6. WA windows por vencer
    n_expiring = len(live["wa_expiring"])
    if n_expiring:
        alerts.append({"level":"warn",
            "title": f"⚠️ {n_expiring} ventanas de WhatsApp próximas a cerrar",
            "body":  "Conversaciones que perderán acceso de respuesta en < 2h.",
            "metric": n_expiring})

    # 7. Sin agentes online
    online_agents = [a for a in agents if a.get("isOnline")]
    if not online_agents:
        alerts.append({"level":"crit",
            "title": "🚨 No hay agentes en línea",
            "body":  "Ningún agente disponible para atender chats entrantes.",
            "metric": 0})

    # 8. Tasa de transferencia alta
    if not df_agents_prod.empty and "% Transferencia" in df_agents_prod.columns:
        high_transfer = df_agents_prod[df_agents_prod["% Transferencia"] > 30]
        for _, row in high_transfer.iterrows():
            alerts.append({"level":"info",
                "title": f"ℹ️ Alta tasa de transferencia: {row['Agente']}",
                "body":  f"{row['% Transferencia']}% de conversaciones re-asignadas. Puede indicar falta de capacitación.",
                "metric": row["% Transferencia"]})

    if not alerts:
        alerts.append({"level":"ok",
            "title": "✅ Sin alertas activas",
            "body": "Todas las métricas dentro de parámetros normales.",
            "metric": 0})

    return alerts

# ─────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────
_KPI_C = {"blue":None,"green":None,"orange":None,"red":None,"purple":None,"sky":None,"coral":None}
def _kc(cls):
    return {"blue":C_BLUE,"green":C_GREEN,"orange":C_ORANGE,
            "red":C_RED,"purple":C_PURPLE,"sky":C_SKY,"coral":C_CORAL}.get(cls,C_BLUE)

def kpi(label, value, sub="", cls="blue", delta=None, delta_good=True):
    delta_html = ""
    if delta is not None:
        dc = "kpi-delta-good" if delta_good else "kpi-delta-bad"
        delta_html = f'<div class="{dc}">{delta}</div>'
    vc = _kc(cls)
    st.markdown(f'<div class="kpi kpi-{cls}"><div class="kpi-label">{label}</div>'
                f'<div class="kpi-value" style="color:{vc}">{value}</div>'
                f'<div class="kpi-sub">{sub}</div>{delta_html}</div>',
                unsafe_allow_html=True)

def sh(txt, right=""):
    st.markdown(f'<div class="sh"><span>{txt}</span>'
                f'<span style="font-size:.67rem;color:{MUTED}">{right}</span></div>',
                unsafe_allow_html=True)

AV_COLS = [C_BLUE,C_GREEN,C_ORANGE,C_PURPLE,C_SKY,C_RED,C_CORAL,C_PINK]

def agent_card(ag, chats_n, max_wait_min):
    is_online = ag.get("isOnline", False)
    status    = ag.get("status","—")
    name      = ag.get("name","Agente")
    initials  = "".join(w[0].upper() for w in name.split()[:2])
    av_col    = AV_COLS[abs(hash(ag.get("id",""))) % len(AV_COLS)]
    dot_col   = C_GREEN if is_online else MUTED
    if is_online:
        bs="background:rgba(14,168,94,.12);color:{C_GREEN};border:1px solid rgba(14,168,94,.3)".format(C_GREEN=C_GREEN); bt="EN LÍNEA"
    elif status=="busy":
        bs="background:rgba(217,119,6,.12);color:{C_ORANGE};border:1px solid rgba(217,119,6,.3)".format(C_ORANGE=C_ORANGE); bt="OCUPADO"
    else:
        bs=f"background:{S2};color:{MUTED};border:1px solid {BORDER}"; bt="OFFLINE"

    slots = ag.get("slots",0) or 1
    load  = round(chats_n/slots*100)
    lc    = C_RED if load>100 else (C_ORANGE if load>70 else C_GREEN)
    wc    = sev_color(max_wait_min)
    wait_html = (f'<span style="color:{wc};font-size:.69rem;font-weight:700"> · ⏱{fmt_mins(max_wait_min)}</span>'
                 if max_wait_min > 0 else "")
    queues = ", ".join(ag.get("queues",[])) or "—"

    st.markdown(f"""<div class="ac">
      <div class="av" style="background:{av_col}20;color:{av_col};border:1.5px solid {av_col}40">{initials}</div>
      <div style="flex:1;min-width:0">
        <div class="an"><span class="od" style="background:{dot_col}"></span>{name}{wait_html}</div>
        <div class="am">Queues: {queues} · Slots: {ag.get('slots',0)}
          · Chats: <b style="color:{TEXT}">{chats_n}</b>
          · Carga: <b style="color:{lc}">{load}%</b></div>
      </div>
      <span class="ab" style="{bs}">{bt}</span>
    </div>""", unsafe_allow_html=True)

def render_alert(a):
    cls_map = {"crit":"alert-crit","warn":"alert-warn","info":"alert-info","ok":"alert-ok"}
    cls = cls_map.get(a["level"],"alert-info")
    st.markdown(f"""<div class="{cls}">
      <div class="alert-title">{a['title']}</div>
      <div class="alert-body">{a['body']}</div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""<div style="padding:10px 0 14px">
      <div style="font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:800;color:{TEXT}">⚡ Kashio</div>
      <div style="font-size:.63rem;color:{MUTED};letter-spacing:.1em">SOPORTE · OPERACIONES</div>
    </div>""", unsafe_allow_html=True)

    # ── Tema ─────────────────────────────────────────────
    c1, c2, c3 = st.columns([1.2, 2, 1.2])
    with c1: st.markdown(f'<div style="text-align:right;padding-top:5px">☀️</div>', unsafe_allow_html=True)
    with c2:
        new_dark = st.toggle("", value=dark, key="theme_tog")
        if new_dark != dark:
            st.session_state.dark_mode = new_dark; st.rerun()
    with c3: st.markdown('<div style="padding-top:5px">🌙</div>', unsafe_allow_html=True)
    st.markdown('<hr>', unsafe_allow_html=True)

    # ── LIVE ─────────────────────────────────────────────
    st.markdown(f'<div class="sb-label">Monitor en vivo</div>', unsafe_allow_html=True)
    live_on = st.toggle("🔴 Activar LIVE", value=st.session_state.live_on, key="live_tog")
    if live_on != st.session_state.live_on:
        st.session_state.live_on = live_on
    if live_on:
        rmap = {"30 seg":30,"1 min":60,"2 min":120,"5 min":300}
        rlabel = st.selectbox("Intervalo", list(rmap.keys()), index=1, label_visibility="collapsed", key="rinterval")
        rsecs  = rmap[rlabel]
        if HAS_AUTOREFRESH: st_autorefresh(interval=rsecs*1000, limit=None, key="live_ar")
        now_s = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        st.markdown(f'<div style="font-size:.71rem;color:{C_RED};margin-top:3px"><span class="ld"></span>Cada {rlabel} · {now_s}</div>', unsafe_allow_html=True)
    else:
        if st.button("🔄 Refrescar"): st.rerun()
    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Período ──────────────────────────────────────────
    st.markdown(f'<div class="sb-label">Período de análisis</div>', unsafe_allow_html=True)
    now_utc = datetime.now(timezone.utc)
    preset  = st.selectbox("Período", ["Hoy","Últimas 24h","Últimos 7d","Últimos 14d","Últimos 30d","Personalizado"],
                            index=2, label_visibility="collapsed", key="preset")
    offsets = {"Hoy":0,"Últimas 24h":1,"Últimos 7d":7,"Últimos 14d":14,"Últimos 30d":30}
    if preset != "Personalizado":
        d_to   = now_utc.date()
        d_from = (now_utc - timedelta(days=offsets.get(preset,7))).date()
        st.markdown(f'<div style="font-size:.74rem;color:{MUTED}">📅 {d_from} → {d_to}</div>', unsafe_allow_html=True)
    else:
        d_from = st.date_input("Desde", value=now_utc.date()-timedelta(days=7), key="d_from")
        d_to   = st.date_input("Hasta", value=now_utc.date(), key="d_to")

    FROM_STR = f"{d_from}T00:00:00Z"
    TO_STR   = f"{d_to}T23:59:59Z"
    FROM_24H = (now_utc - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    st.markdown('<hr>', unsafe_allow_html=True)

    # ── SLA Config ───────────────────────────────────────
    st.markdown(f'<div class="sb-label">Umbrales SLA</div>', unsafe_allow_html=True)
    sla_frt_ok   = st.number_input("FRT OK (min)",   min_value=1,  max_value=120, value=SLA_FRT_OK,   key="sla_frt_ok")
    sla_frt_warn = st.number_input("FRT Warn (min)",  min_value=1,  max_value=480, value=SLA_FRT_WARN, key="sla_frt_warn")
    sla_wait_warn = st.number_input("Espera crítica (min)", min_value=10, max_value=1440, value=SLA_WAIT_WARN, key="sla_wait")
    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Filtros ──────────────────────────────────────────
    st.markdown(f'<div class="sb-label">Filtros</div>', unsafe_allow_html=True)
    filter_queue = st.selectbox("Queue", ["Todas","Soporte N1","Comercial","_default_"],
                                 label_visibility="collapsed", key="fq")
    st.markdown(f'<div style="font-size:.67rem;color:{MUTED};margin-top:6px">Última carga: {now_utc.strftime("%H:%M UTC")}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# CARGA DE DATOS (una sola vez por render)
# ══════════════════════════════════════════════════════════
with st.spinner("Cargando datos…"):
    sc_ag,  d_ag  = api_get("agents")
    sc_ag2, d_ag2 = api_get("agents", {"online":"true"})
    sc_ch,  d_ch  = api_get("chats",  {"from": FROM_24H})
    params_ses = f"from={FROM_STR}&to={TO_STR}&include-events=true"
    sc_ses, d_ses = api_get_cached("sessions", params_ses)

ag_list  = its(d_ag)  if sc_ag  == 200 else []
ag_on    = its(d_ag2) if sc_ag2 == 200 else []
cht_raw  = its(d_ch)  if sc_ch  == 200 else []
ses_list = its(d_ses) if sc_ses == 200 else []

# Filtro de queue en sidebar
if filter_queue != "Todas":
    cht_raw = [c for c in cht_raw if c.get("queueId","") == filter_queue]

live     = compute_live_chat_metrics(cht_raw, ag_list, now_utc)
df_kpis  = compute_session_kpis(ses_list)
ag_prod  = compute_agent_productivity(df_kpis, live["chats_per_agent"], ag_list)
alerts   = build_alerts(live, df_kpis, ag_prod, ag_list, now_utc, sla_frt_warn)
n_crit   = sum(1 for a in alerts if a["level"]=="crit")

# ── Header con badge de alertas ──────────────────────────
alert_badge = f' <span style="background:{C_RED};color:#fff;font-size:.7rem;padding:2px 7px;border-radius:20px;font-weight:700">{n_crit} ⚠</span>' if n_crit else ""
st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
  <div style="font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:{TEXT}">
    {"<span class='ld'></span>" if live_on else ""}Dashboard Soporte{alert_badge}
  </div>
  <div style="font-size:.74rem;color:{MUTED}">{'🔴 EN VIVO' if live_on else f'{d_from} → {d_to}'}</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════
tab_rt, tab_sla, tab_team, tab_shifts, tab_alerts, tab_trends = st.tabs([
    "🔴 Tiempo Real",
    "⚡ SLA & Tiempos",
    "👥 Equipo",
    "📋 Turnos",
    f"🚨 Alertas {'🔴' if n_crit else '✅'}",
    "📊 Tendencias",
])


# ══════════════════════════════════════════════════════════
# TAB 1 — TIEMPO REAL
# ══════════════════════════════════════════════════════════
with tab_rt:
    # KPI row — métricas de cola en tiempo real
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    n_unassigned = len(live["unassigned"])
    n_pending    = len(live["pending"])
    n_online     = len(ag_on)
    max_wait     = live["pending"][0]["wait_min"] if live["pending"] else 0

    with k1: kpi("Sin asignar",    n_unassigned,  "chats esperando agente", "red",
                 delta=f"⚠️ Umbral: {ALERT_UNASSIGNED_MAX}" if n_unassigned >= ALERT_UNASSIGNED_MAX else "✅ OK",
                 delta_good=(n_unassigned < ALERT_UNASSIGNED_MAX))
    with k2: kpi("Soporte N1",     len(live["support"]), "en cola soporte", "orange")
    with k3: kpi("Comercial",      len(live["comercial"]), "en cola comercial", "blue")
    with k4: kpi("Pend. respuesta",n_pending, "bot muted + agente", "purple")
    with k5: kpi("Máx. espera",    fmt_mins(max_wait),
                 "chat más antiguo sin resp.",
                 "red" if max_wait > sla_wait_warn else ("orange" if max_wait > SLA_WAIT_OK else "green"))
    with k6: kpi("Agentes online", n_online, f"de {len(ag_list)} total", "green")

    st.markdown("")

    # ── Grid agentes ─────────────────────────────────────
    sh("Estado del equipo en tiempo real", f"{n_online} en línea · {len(ag_list)} total")
    ag_sorted = sorted(ag_list,
        key=lambda a: (0 if a.get("isOnline") else (1 if a.get("status")=="busy" else 2)))

    # Max wait per agent
    ag_max_wait = {aid: max(ws) for aid, ws in live["wait_per_agent"].items()}

    cols = st.columns(3)
    for i, ag in enumerate(ag_sorted):
        with cols[i%3]:
            agent_card(ag, live["chats_per_agent"].get(ag.get("id",""),0),
                       ag_max_wait.get(ag.get("id",""), 0))
            st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)

    st.markdown("")
    col_l, col_r = st.columns([3,2])

    with col_l:
        # Tabla de pendientes con tiempo de espera
        sh(f"Chats pendientes de respuesta — {n_pending}", "bot silenciado + agente asignado")
        if live["pending"]:
            rows = []
            for c in live["pending"]:
                sc_ = c["sev_cls"]
                sla_badge = (f'<span class="{sc_}">{c["wait_fmt"]}</span>')
                rows.append({
                    "⏱ Espera":    c["wait_fmt"],
                    "Sev":         "🔴" if c["wait_min"]>sla_wait_warn else ("🟠" if c["wait_min"]>SLA_WAIT_OK else "🟢"),
                    "Agente":      c["agent_name"],
                    "Cliente":     c.get("firstName","—"),
                    "País":        c.get("country","—"),
                    "Queue":       c.get("queueId","—"),
                    "Último msg":  c.get("lastUserMessageDatetime","")[:16].replace("T"," "),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38, 380))
        else:
            st.success("✅ Sin chats pendientes de respuesta.")

        sh(f"Sin asignar — {n_unassigned}", "chats sin agentId · últimas 24h")
        if live["unassigned"]:
            rows = [{"Nombre":c.get("firstName","—"),"País":c.get("country","—"),
                     "Queue":c.get("queueId","—"),
                     "🪟 WA":"✅" if c.get("whatsAppWindowCloseDatetime","")>now_utc.isoformat()[:19] else "❌",
                     "Último msg":c.get("lastUserMessageDatetime","")[:16].replace("T"," ")}
                    for c in live["unassigned"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(38*len(rows)+38, 300))
        else:
            st.success("✅ Sin chats sin asignar.")

    with col_r:
        sh("Por queue")
        if cht_raw:
            qc = live["queues"]
            f1 = px.pie(pd.DataFrame({"Q":list(qc.keys()),"n":list(qc.values())}),
                        names="Q", values="n", hole=0.6,
                        color_discrete_map={"_default_":C_BLUE,"Soporte N1":C_ORANGE,
                                            "Comercial":C_GREEN,"Sin queue":MUTED})
            f1.update_layout(**L(margin=dict(l=0,r=0,t=10,b=0)))
            pf(f1, 200)

        sh("Espera por agente (min)")
        if live["pending"]:
            ag_wait_avg = {ag: sum(ws)/len(ws) for ag, ws in live["wait_per_agent"].items()}
            ag_id_name  = {a["id"]: a["name"] for a in ag_list}
            wdf = pd.DataFrame([{"Agente": ag_id_name.get(aid, aid[:10]), "min": round(v,1)}
                                  for aid, v in sorted(ag_wait_avg.items(), key=lambda x: -x[1])])
            f2 = px.bar(wdf, x="min", y="Agente", orientation="h",
                        color="min", color_continuous_scale=[C_GREEN, C_ORANGE, C_RED],
                        text=wdf["min"].apply(fmt_mins))
            f2.update_layout(**L(coloraxis_showscale=False, margin=dict(l=130,r=50,t=10,b=10)))
            f2.update_traces(marker_cornerradius=4, textposition="outside")
            pf(f2, 220)

        sh("Por país")
        if live["countries"]:
            cc = live["countries"]
            f3 = px.bar(pd.DataFrame({"País":list(cc.keys()),"n":list(cc.values())}).sort_values("n"),
                        x="n", y="País", orientation="h", color_discrete_sequence=[C_PURPLE])
            f3.update_layout(**L(margin=dict(l=60,r=30,t=10,b=10)))
            f3.update_traces(marker_cornerradius=4)
            pf(f3, 180)

# ══════════════════════════════════════════════════════════
# TAB 2 — SLA & TIEMPOS
# ══════════════════════════════════════════════════════════
with tab_sla:
    if df_kpis.empty:
        st.info("Sin datos de sesiones para el período seleccionado.")
    else:
        frt_valid = df_kpis["frt_min"].dropna()
        aht_valid = df_kpis["aht_min"].dropna()

        # ── KPIs de tiempo ────────────────────────────────
        frt_avg  = frt_valid.mean()  if len(frt_valid) else 0
        frt_p50  = frt_valid.median() if len(frt_valid) else 0
        frt_p80  = np.percentile(frt_valid, 80) if len(frt_valid) > 2 else 0
        aht_avg  = aht_valid.mean()  if len(aht_valid) else 0
        sla_pct  = round(frt_valid.le(sla_frt_warn).mean()*100, 1) if len(frt_valid) else 0
        res_pct  = round(df_kpis["resolved"].mean()*100, 1)
        asgn_pct = round(df_kpis["assigned"].mean()*100, 1)

        k1,k2,k3,k4,k5,k6 = st.columns(6)
        with k1: kpi("FRT Promedio",   fmt_mins(frt_avg),  f"p50: {fmt_mins(frt_p50)}",
                     "red" if frt_avg > sla_frt_warn else ("orange" if frt_avg > sla_frt_ok else "green"),
                     delta=f"p80: {fmt_mins(frt_p80)}", delta_good=frt_p80<=sla_frt_warn)
        with k2: kpi("SLA FRT",       f"{sla_pct}%",  f"≤{sla_frt_warn}min",
                     "green" if sla_pct >= 80 else ("orange" if sla_pct >= 60 else "red"),
                     delta="✅ Cumple" if sla_pct >= 80 else "⚠️ Por mejorar", delta_good=sla_pct>=80)
        with k3: kpi("AHT Promedio",   fmt_mins(aht_avg), "assign → cierre",
                     "green" if aht_avg <= SLA_AHT_OK else ("orange" if aht_avg <= SLA_AHT_WARN else "red"))
        with k4: kpi("Tasa resolución",f"{res_pct}%", f"{int(df_kpis['resolved'].sum())} resueltas","blue")
        with k5: kpi("Tasa asignación",f"{asgn_pct}%",f"{int(df_kpis['assigned'].sum())} asignadas","purple")
        with k6: kpi("Transferencias", int(df_kpis["transferred"].sum()),
                     f"{round(df_kpis['transferred'].mean()*100,1)}% del total","coral")

        st.markdown("")
        col_l, col_m, col_r = st.columns(3)

        with col_l:
            sh("Distribución FRT")
            f1 = px.histogram(df_kpis[df_kpis["frt_min"].notna()], x="frt_min", nbins=20,
                               color_discrete_sequence=[C_BLUE],
                               labels={"frt_min":"FRT (minutos)"})
            f1.add_vline(x=sla_frt_ok,   line_dash="dash", line_color=C_GREEN,  annotation_text=f"OK ({sla_frt_ok}m)")
            f1.add_vline(x=sla_frt_warn, line_dash="dash", line_color=C_ORANGE, annotation_text=f"Warn ({sla_frt_warn}m)")
            f1.update_layout(**L(xaxis_title="minutos", yaxis_title="sesiones"))
            f1.update_traces(marker_cornerradius=3)
            pf(f1)

        with col_m:
            sh("FRT por turno (mediana)")
            if "shift" in df_kpis.columns:
                shift_frt = df_kpis.groupby("shift")["frt_min"].median().reset_index()
                shift_frt.columns = ["Turno","FRT_med"]
                shift_frt = shift_frt.sort_values("FRT_med")
                f2 = px.bar(shift_frt, x="FRT_med", y="Turno", orientation="h",
                             color="FRT_med", color_continuous_scale=[C_GREEN, C_ORANGE, C_RED],
                             text=shift_frt["FRT_med"].apply(lambda x: fmt_mins(x) if pd.notna(x) else "—"))
                f2.add_vline(x=sla_frt_warn, line_dash="dash", line_color=C_RED)
                f2.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=60,t=10,b=10)))
                f2.update_traces(marker_cornerradius=4, textposition="outside")
                pf(f2)

        with col_r:
            sh("SLA compliance por turno")
            if "shift" in df_kpis.columns:
                sla_by_shift = (df_kpis[df_kpis["frt_sla_warn"].notna()]
                                .groupby("shift")["frt_sla_warn"]
                                .agg(["mean","count"])
                                .reset_index())
                sla_by_shift.columns = ["Turno","sla_pct","n"]
                sla_by_shift["sla_pct"] = (sla_by_shift["sla_pct"]*100).round(1)
                f3 = px.bar(sla_by_shift.sort_values("sla_pct"),
                             x="sla_pct", y="Turno", orientation="h",
                             color="sla_pct", color_continuous_scale=[C_RED, C_ORANGE, C_GREEN],
                             text=sla_by_shift.sort_values("sla_pct")["sla_pct"].apply(lambda x: f"{x:.0f}%"))
                f3.add_vline(x=80, line_dash="dash", line_color=C_GREEN, annotation_text="Meta 80%")
                f3.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=60,t=10,b=10), xaxis_range=[0,105]))
                f3.update_traces(marker_cornerradius=4, textposition="outside")
                pf(f3)

        # ── FRT por hora del día ──────────────────────────
        sh("FRT mediano por hora del día (Lima)")
        hourly = df_kpis[df_kpis["frt_min"].notna()].groupby("hour")["frt_min"].median().reset_index()
        hourly.columns = ["Hora","FRT_med"]
        all_hours = pd.DataFrame({"Hora": range(24)})
        hourly = all_hours.merge(hourly, on="Hora", how="left")
        f4 = go.Figure()
        f4.add_trace(go.Bar(x=hourly["Hora"], y=hourly["FRT_med"],
                            marker_color=[C_RED if v>sla_frt_warn else (C_ORANGE if v>sla_frt_ok else C_GREEN)
                                          for v in hourly["FRT_med"].fillna(0)],
                            marker_cornerradius=4,
                            text=hourly["FRT_med"].apply(lambda x: fmt_mins(x) if pd.notna(x) else ""),
                            textposition="outside"))
        f4.add_hline(y=sla_frt_warn, line_dash="dash", line_color=C_RED,
                     annotation_text=f"SLA ({sla_frt_warn}m)", annotation_position="right")
        f4.update_layout(**L(xaxis_title="Hora (Lima)", yaxis_title="FRT mediano (min)",
                              xaxis=dict(tickvals=list(range(24)), **_BL["xaxis"])))
        pf(f4)

        # ── Tabla detallada de sesiones ───────────────────
        sh("Sesiones con detalle de tiempos")
        df_show = df_kpis[["date","shift","agent","cause","frt_min","assign_delay",
                             "aht_min","assigned","resolved","transferred"]].copy()
        df_show["frt_min"]      = df_show["frt_min"].apply(lambda x: fmt_mins(x) if pd.notna(x) else "—")
        df_show["assign_delay"] = df_show["assign_delay"].apply(lambda x: fmt_mins(x) if pd.notna(x) else "—")
        df_show["aht_min"]      = df_show["aht_min"].apply(lambda x: fmt_mins(x) if pd.notna(x) else "—")
        df_show["assigned"]     = df_show["assigned"].map({True:"✅",False:"❌"})
        df_show["resolved"]     = df_show["resolved"].map({True:"✅",False:"❌"})
        df_show["transferred"]  = df_show["transferred"].map({True:"↔️",False:""})
        df_show.columns = ["Fecha","Turno","Agente","Origen","FRT","Delay asign.","AHT","Asignado","Resuelto","Transferido"]
        st.dataframe(df_show, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# TAB 3 — EQUIPO / PRODUCTIVIDAD
# ══════════════════════════════════════════════════════════
with tab_team:
    if ag_prod.empty:
        st.info("Sin datos de productividad para el período seleccionado.")
    else:
        # KPIs globales del equipo
        k1,k2,k3,k4 = st.columns(4)
        with k1: kpi("Total asignaciones", int(ag_prod["Asignaciones"].sum()), f"{d_from}–{d_to}","blue")
        with k2: kpi("% Resolución global", f"{round(ag_prod['Resueltas'].sum()/max(ag_prod['Asignaciones'].sum(),1)*100,1)}%","","green")
        with k3: kpi("% Transferencia global", f"{round(ag_prod['Transferidas'].sum()/max(ag_prod['Asignaciones'].sum(),1)*100,1)}%","","orange")
        with k4:
            best = ag_prod.loc[ag_prod["Asignaciones"].idxmax(), "Agente"] if len(ag_prod) else "—"
            kpi("Top agente", best, f"{ag_prod['Asignaciones'].max()} asig.","purple")

        st.markdown("")
        col_l, col_r = st.columns(2)

        with col_l:
            sh("Ranking — asignaciones por agente")
            f1 = px.bar(ag_prod.sort_values("Asignaciones"),
                        x="Asignaciones", y="Agente", orientation="h",
                        color="Asignaciones", color_continuous_scale=[S2, C_BLUE])
            f1.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=10,t=10,b=10)))
            f1.update_traces(marker_cornerradius=4)
            pf(f1)

            sh("Resolución vs Transferencia por agente")
            f2 = go.Figure()
            f2.add_trace(go.Bar(name="% Resolución",   x=ag_prod["Agente"],
                                y=ag_prod["% Resolución"],   marker_color=C_GREEN, marker_cornerradius=4))
            f2.add_trace(go.Bar(name="% Transferencia",x=ag_prod["Agente"],
                                y=ag_prod["% Transferencia"],marker_color=C_ORANGE, marker_cornerradius=4))
            f2.update_layout(**L(barmode="group", margin=dict(l=10,r=10,t=10,b=80)))
            f2.update_xaxes(tickangle=30)
            pf(f2)

        with col_r:
            sh("SLA FRT % por agente")
            df_sla_ag = ag_prod[ag_prod["SLA FRT %"].notna()].sort_values("SLA FRT %")
            if not df_sla_ag.empty:
                f3 = px.bar(df_sla_ag, x="SLA FRT %", y="Agente", orientation="h",
                             color="SLA FRT %",
                             color_continuous_scale=[C_RED, C_ORANGE, C_GREEN])
                f3.add_vline(x=80, line_dash="dash", line_color=C_GREEN,
                             annotation_text="Meta 80%", annotation_position="top right")
                f3.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=70,t=10,b=10), xaxis_range=[0,105]))
                f3.update_traces(marker_cornerradius=4)
                pf(f3)

            sh("FRT p80 por agente")
            df_frt_ag = ag_prod[ag_prod["FRT p80 (min)"].notna()].sort_values("FRT p80 (min)")
            if not df_frt_ag.empty:
                f4 = px.bar(df_frt_ag, x="FRT p80 (min)", y="Agente", orientation="h",
                             color="FRT p80 (min)",
                             color_continuous_scale=[C_GREEN, C_ORANGE, C_RED],
                             text=df_frt_ag["FRT p80 (min)"].apply(fmt_mins))
                f4.add_vline(x=sla_frt_warn, line_dash="dash", line_color=C_RED)
                f4.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=60,t=10,b=10)))
                f4.update_traces(marker_cornerradius=4, textposition="outside")
                pf(f4)

        # ── Heatmap: actividad agente × hora ──────────────
        sh("Actividad por agente y hora del día (asignaciones)")
        if not df_kpis.empty and "agent" in df_kpis.columns:
            heat_data = (df_kpis[df_kpis["assigned"]]
                         .groupby(["agent","hour"])
                         .size().reset_index(name="n"))
            agents_act = sorted(heat_data["agent"].unique())
            df_heat = heat_data.pivot(index="agent", columns="hour", values="n").fillna(0)
            df_heat = df_heat.reindex(columns=range(24), fill_value=0)
            fh = px.imshow(df_heat, aspect="auto",
                           color_continuous_scale=[S1, S3, C_BLUE, C_GREEN],
                           labels={"x":"Hora (Lima)","y":"Agente","color":"Asignaciones"},
                           text_auto=True)
            fh.update_layout(**L(margin=dict(l=150,r=10,t=10,b=40)))
            pf(fh)

        # ── Tabla completa ────────────────────────────────
        sh("Tabla de productividad completa")
        df_disp = ag_prod.copy()
        df_disp["isOnline"] = df_disp["isOnline"].map({True:"🟢",False:"⚫"})
        df_disp["Carga %"]  = df_disp["Carga %"].apply(lambda x: f"{x}%")
        df_disp["FRT prom (min)"] = df_disp["FRT prom (min)"].apply(lambda x: fmt_mins(x) if pd.notna(x) else "—")
        df_disp["AHT prom (min)"] = df_disp["AHT prom (min)"].apply(lambda x: fmt_mins(x) if pd.notna(x) else "—")
        df_disp["SLA FRT %"]      = df_disp["SLA FRT %"].apply(lambda x: f"{x}%" if pd.notna(x) else "—")
        st.dataframe(df_disp, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════
# TAB 4 — TURNOS
# ══════════════════════════════════════════════════════════
with tab_shifts:
    sh("Horarios configurados")
    st.dataframe(pd.DataFrame([{"Agente":s[0],"Días":s[1] if isinstance(s[1],str) else
                                 "Lun–Vie" if s[1]==[0,1,2,3,4] else "Sáb–Dom",
                                 "Horario (Lima)":f"{s[2]:02d}:00–{s[3]:02d}:00","Tipo":s[4]}
                                for s in SHIFTS]),
                use_container_width=True, hide_index=True)

    if df_kpis.empty:
        st.info("Sin datos de sesiones.")
    else:
        shift_stats = defaultdict(lambda:{"total":0,"asig":0,"resp":0,"cierre":0,"no_asig":0,
                                           "frt_list":[], "aht_list":[]})
        daily_shift = defaultdict(lambda: defaultdict(int))

        for s in ses_list:
            ct = s.get("creationTime","")
            if not ct: continue
            try: dt = datetime.fromisoformat(ct.replace("Z","+00:00"))
            except: continue
            shift = get_shift_label(dt)
            day   = (dt + LIMA_OFFSET).strftime("%Y-%m-%d")
            daily_shift[day][shift] += 1
            ev_names = [e["name"] for e in s.get("events",[])]
            shift_stats[shift]["total"] += 1
            if "assigned-to-agent"  in ev_names: shift_stats[shift]["asig"]    += 1
            else:                                shift_stats[shift]["no_asig"]  += 1
            if "agent-action"       in ev_names: shift_stats[shift]["resp"]     += 1
            if "conversation-close" in ev_names: shift_stats[shift]["cierre"]   += 1

        # Merge FRT per shift from df_kpis
        for shift, grp in df_kpis.groupby("shift"):
            shift_stats[shift]["frt_list"] = grp["frt_min"].dropna().tolist()
            shift_stats[shift]["aht_list"] = grp["aht_min"].dropna().tolist()

        active = [s for s in SHIFT_ORDER if s in shift_stats]

        # KPI cards per shift
        sh("Resumen por turno")
        cols = st.columns(len(active) or 1)
        for i, sname in enumerate(active):
            sd  = shift_stats[sname]
            tot = sd["total"]
            pct = int(100*sd["asig"]/tot) if tot else 0
            frt_med = fmt_mins(np.median(sd["frt_list"])) if sd["frt_list"] else "—"
            sc  = SHIFT_PAL.get(sname, C_BLUE)
            with cols[i]:
                st.markdown(f"""<div class="kpi" style="border-top:3px solid {sc}">
                  <div class="kpi-label" style="color:{sc}">{sname.split()[0]}</div>
                  <div class="kpi-value" style="color:{sc};font-size:1.6rem">{tot}</div>
                  <div class="kpi-sub">{pct}% asignadas</div>
                  <div style="font-size:.68rem;color:{MUTED};margin-top:5px">
                    ✅ {sd['asig']} &nbsp;💬 {sd['resp']} &nbsp;🔒 {sd['cierre']}<br>
                    ⏱ FRT med: <b style="color:{TEXT}">{frt_med}</b>
                  </div></div>""", unsafe_allow_html=True)

        st.markdown("")
        col_l, col_r = st.columns(2)

        with col_l:
            sh("Asignaciones vs No asignadas por turno")
            f1 = go.Figure()
            f1.add_trace(go.Bar(name="Asignadas",    x=active, y=[shift_stats[s]["asig"]    for s in active], marker_color=C_GREEN,  marker_cornerradius=3))
            f1.add_trace(go.Bar(name="Respondidas",  x=active, y=[shift_stats[s]["resp"]    for s in active], marker_color=C_BLUE,   marker_cornerradius=3))
            f1.add_trace(go.Bar(name="No asignadas", x=active, y=[shift_stats[s]["no_asig"] for s in active], marker_color=C_RED,    marker_cornerradius=3))
            f1.update_layout(**L(barmode="group", margin=dict(l=10,r=10,t=10,b=80)))
            f1.update_xaxes(tickangle=30)
            pf(f1)

        with col_r:
            sh("FRT mediano por turno")
            frt_shift_df = pd.DataFrame([{"Turno":s,
                "FRT_med": np.median(shift_stats[s]["frt_list"]) if shift_stats[s]["frt_list"] else None}
                for s in active]).dropna()
            if not frt_shift_df.empty:
                frt_shift_df = frt_shift_df.sort_values("FRT_med")
                f2 = px.bar(frt_shift_df, x="FRT_med", y="Turno", orientation="h",
                             color="FRT_med", color_continuous_scale=[C_GREEN, C_ORANGE, C_RED],
                             text=frt_shift_df["FRT_med"].apply(fmt_mins))
                f2.add_vline(x=sla_frt_warn, line_dash="dash", line_color=C_RED)
                f2.update_layout(**L(coloraxis_showscale=False, margin=dict(l=150,r=70,t=10,b=10)))
                f2.update_traces(marker_cornerradius=4, textposition="outside")
                pf(f2)

        sh("Heatmap — sesiones por turno y día")
        all_days = sorted(daily_shift.keys())
        if all_days and active:
            df_heat = pd.DataFrame(
                [[daily_shift[d].get(s,0) for d in all_days] for s in active],
                index=active, columns=all_days)
            fh = px.imshow(df_heat, aspect="auto",
                           color_continuous_scale=[S1, S3, C_BLUE, C_GREEN], text_auto=True)
            fh.update_layout(**L(margin=dict(l=160,r=10,t=10,b=60)))
            fh.update_xaxes(tickangle=30)
            pf(fh)


# ══════════════════════════════════════════════════════════
# TAB 5 — ALERTAS INTELIGENTES
# ══════════════════════════════════════════════════════════
with tab_alerts:
    crit  = [a for a in alerts if a["level"]=="crit"]
    warns = [a for a in alerts if a["level"]=="warn"]
    infos = [a for a in alerts if a["level"]=="info"]
    oks   = [a for a in alerts if a["level"]=="ok"]

    k1,k2,k3,k4 = st.columns(4)
    with k1: kpi("Alertas críticas",  len(crit),  "acción inmediata","red")
    with k2: kpi("Advertencias",      len(warns), "revisar pronto","orange")
    with k3: kpi("Informativas",      len(infos), "seguimiento","sky")
    with k4: kpi("Estado OK",         len(oks),   "métricas normales","green")

    st.markdown("")

    if crit:
        sh("🚨 Alertas críticas — acción inmediata")
        for a in crit: render_alert(a)

    if warns:
        sh("⚠️ Advertencias — revisar pronto")
        for a in warns: render_alert(a)

    if infos:
        sh("ℹ️ Informativas")
        for a in infos: render_alert(a)

    if oks:
        for a in oks: render_alert(a)

    # ── Panel de diagnóstico de cola en tiempo real ───────
    sh("Diagnóstico de cola en tiempo real")
    col_l, col_r = st.columns(2)

    with col_l:
        # Gauge de carga de cola
        total_slots = sum(a.get("slots",1) or 1 for a in ag_list if a.get("isOnline"))
        total_chats = len(cht_raw)
        load_pct    = round(total_chats / max(total_slots, 1) * 100)
        lc = C_RED if load_pct>90 else (C_ORANGE if load_pct>65 else C_GREEN)

        fg = go.Figure(go.Indicator(
            mode="gauge+number",
            value=load_pct,
            number={"suffix":"%","font":{"size":44,"color":lc,"family":"Syne"}},
            gauge={"axis":{"range":[0,150],"tickcolor":MUTED},
                   "bar":{"color":lc},
                   "bgcolor":S1,"bordercolor":BORDER,"borderwidth":1,
                   "steps":[{"range":[0,65], "color":f"rgba(14,168,94,.1)"},
                             {"range":[65,90],"color":f"rgba(217,119,6,.1)"},
                             {"range":[90,150],"color":f"rgba(220,53,69,.1)"}],
                   "threshold":{"line":{"color":C_RED,"width":3},"thickness":.8,"value":90}},
            title={"text":"Carga de cola (chats / slots online)","font":{"size":12,"color":MUTED}},
        ))
        fg.update_layout(**L(height=280, margin=dict(l=20,r=20,t=50,b=10)))
        pf(fg)

    with col_r:
        # Mini resumen de estado por agente
        sh("Capacidad por agente")
        rows_cap = []
        for ag in ag_list:
            if not ag.get("isOnline"): continue
            aid       = ag.get("id","")
            chats_n   = live["chats_per_agent"].get(aid, 0)
            slots     = ag.get("slots",1) or 1
            load      = round(chats_n/slots*100)
            max_w     = max(live["wait_per_agent"].get(aid, [0]))
            rows_cap.append({
                "Agente":    ag.get("name",""),
                "Chats":     chats_n,
                "Slots":     slots,
                "Carga":     f"{load}%",
                "Máx. esp.": fmt_mins(max_w),
                "Estado":    "🔴 Sobrecargado" if load>100 else ("🟠 Alto" if load>70 else "🟢 Normal"),
            })
        if rows_cap:
            st.dataframe(pd.DataFrame(rows_cap), use_container_width=True, hide_index=True)
        else:
            st.info("No hay agentes en línea en este momento.")

    # ── Historial de espera de chats pendientes ───────────
    if live["pending"]:
        sh("Distribución de tiempos de espera actuales")
        wait_vals = [p["wait_min"] for p in live["pending"]]
        fw = px.histogram(pd.DataFrame({"Espera (min)": wait_vals}),
                           x="Espera (min)", nbins=15, color_discrete_sequence=[C_BLUE])
        fw.add_vline(x=SLA_WAIT_OK,   line_dash="dash", line_color=C_GREEN,  annotation_text=f"OK ({SLA_WAIT_OK}m)")
        fw.add_vline(x=sla_wait_warn, line_dash="dash", line_color=C_RED,    annotation_text=f"Crítico")
        fw.update_layout(**L(yaxis_title="chats"))
        fw.update_traces(marker_cornerradius=3)
        pf(fw)

# ══════════════════════════════════════════════════════════
# TAB 6 — TENDENCIAS
# ══════════════════════════════════════════════════════════
with tab_trends:
    if df_kpis.empty:
        st.info("Sin datos de sesiones para el período seleccionado.")
    else:
        col_l, col_r = st.columns(2)

        with col_l:
            sh("Sesiones por día — origen")
            by_day = df_kpis.groupby(["date","cause"]).size().reset_index(name="n")
            by_day.columns = ["Fecha","Origen","n"]
            f1 = px.bar(by_day, x="Fecha", y="n", color="Origen", barmode="stack",
                        color_discrete_map={"Organic":C_BLUE,"WhatsAppTemplate":C_ORANGE})
            f1.update_layout(**L()); f1.update_traces(marker_cornerradius=3)
            pf(f1)

            sh("FRT promedio diario vs SLA")
            frt_day = df_kpis.groupby("date")["frt_min"].mean().reset_index()
            frt_day.columns = ["Fecha","FRT_avg"]
            f2 = go.Figure()
            f2.add_trace(go.Scatter(x=frt_day["Fecha"], y=frt_day["FRT_avg"],
                                     mode="lines+markers+text",
                                     line=dict(color=C_BLUE, width=2),
                                     marker=dict(color=[C_RED if v>sla_frt_warn else (C_ORANGE if v>sla_frt_ok else C_GREEN)
                                                         for v in frt_day["FRT_avg"].fillna(0)], size=8),
                                     text=frt_day["FRT_avg"].apply(lambda x: fmt_mins(x) if pd.notna(x) else ""),
                                     textposition="top center"))
            f2.add_hline(y=sla_frt_warn, line_dash="dash", line_color=C_RED,
                         annotation_text=f"SLA warn ({sla_frt_warn}m)")
            f2.add_hline(y=sla_frt_ok,   line_dash="dot",  line_color=C_GREEN,
                         annotation_text=f"SLA ok ({sla_frt_ok}m)")
            f2.update_layout(**L(yaxis_title="FRT promedio (min)"))
            pf(f2)

        with col_r:
            sh("Tasa de resolución diaria")
            res_day = df_kpis.groupby("date")["resolved"].mean().reset_index()
            res_day.columns = ["Fecha","Res%"]
            res_day["Res%"] = res_day["Res%"] * 100
            f3 = px.area(res_day, x="Fecha", y="Res%", color_discrete_sequence=[C_GREEN])
            f3.add_hline(y=80, line_dash="dash", line_color=C_ORANGE, annotation_text="Meta 80%")
            f3.update_layout(**L(yaxis_range=[0,105], yaxis_title="% Resueltas"))
            f3.update_traces(fill="tozeroy", fillcolor=f"rgba(14,168,94,.08)" if dark else "rgba(14,168,94,.1)")
            pf(f3)

            sh("Sesiones por día de semana (Lima) — patrón de volumen")
            df_kpis["weekday"] = pd.to_datetime(df_kpis["date"]).dt.weekday
            DAYS = {0:"Lun",1:"Mar",2:"Mié",3:"Jue",4:"Vie",5:"Sáb",6:"Dom"}
            wd_counts = df_kpis.groupby("weekday").size().reset_index(name="n")
            wd_counts["Día"] = wd_counts["weekday"].map(DAYS)
            f4 = px.bar(wd_counts, x="Día", y="n",
                        color="n", color_continuous_scale=[S2, C_BLUE],
                        category_orders={"Día":["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]})
            f4.update_layout(**L(coloraxis_showscale=False))
            f4.update_traces(marker_cornerradius=5)
            pf(f4)

        # ── Comparativa semanal ───────────────────────────
        sh("Comparativa semanal — FRT promedio y volumen")
        df_kpis["week"] = pd.to_datetime(df_kpis["date"]).dt.isocalendar().week.astype(str)
        weeks = df_kpis.groupby("week").agg(
            Sesiones=("session_id","count"),
            FRT_avg=("frt_min","mean"),
            Res_pct=("resolved","mean"),
        ).reset_index()
        weeks["Res_pct"] = (weeks["Res_pct"]*100).round(1)
        weeks["FRT_avg"] = weeks["FRT_avg"].round(1)

        f5 = make_subplots(specs=[[{"secondary_y": True}]])
        f5.add_trace(go.Bar(x=weeks["week"], y=weeks["Sesiones"], name="Sesiones",
                            marker_color=C_BLUE, marker_cornerradius=4), secondary_y=False)
        f5.add_trace(go.Scatter(x=weeks["week"], y=weeks["FRT_avg"], name="FRT prom (min)",
                                mode="lines+markers", line=dict(color=C_ORANGE, width=2),
                                marker=dict(size=7)), secondary_y=True)
        f5.update_layout(**L(legend=dict(x=0.01, y=0.99, **_BL["legend"])))
        f5.update_yaxes(title_text="Sesiones", secondary_y=False,
                        gridcolor=GRID, tickfont=dict(color=FONT_COL))
        f5.update_yaxes(title_text="FRT promedio (min)", secondary_y=True,
                        tickfont=dict(color=FONT_COL))
        f5.update_xaxes(title_text="Semana del año", tickfont=dict(color=FONT_COL))
        f5.update_layout(paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
                         font=dict(family="Inter",color=FONT_COL))
        pf(f5)

        # ── Tabla comparativa semanal ─────────────────────
        sh("Tabla comparativa por semana")
        weeks_disp = weeks.copy()
        weeks_disp["FRT_avg"] = weeks_disp["FRT_avg"].apply(lambda x: fmt_mins(x) if pd.notna(x) else "—")
        weeks_disp["Res_pct"] = weeks_disp["Res_pct"].apply(lambda x: f"{x}%" if pd.notna(x) else "—")
        weeks_disp.columns = ["Semana","Sesiones","FRT promedio","Tasa resolución"]
        st.dataframe(weeks_disp, use_container_width=True, hide_index=True)
