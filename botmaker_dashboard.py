"""
botmaker_dashboard.py  ·  Kashio — Botmaker API v2.0
Dashboard interactivo con campos reales mapeados desde la API.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from collections import Counter

BASE_URL = "https://api.botmaker.com/v2.0"

st.set_page_config(
    page_title="Kashio · Botmaker",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

:root {
  --bg:       #07080c;
  --s1:       #0e1018;
  --s2:       #141720;
  --border:   #1f2333;
  --accent:   #4f6ef7;
  --green:    #22d47b;
  --orange:   #f5a524;
  --red:      #f25c5c;
  --purple:   #a78bfa;
  --sky:      #38bdf8;
  --text:     #e6e8f0;
  --muted:    #555e7a;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text); }
.stApp { background: var(--bg); }
.stSidebar { background: var(--s1) !important; border-right: 1px solid var(--border) !important; }

/* ── KPI cards ── */
.kpi { background: var(--s1); border: 1px solid var(--border); border-radius: 14px;
       padding: 20px 22px; position: relative; overflow: hidden; }
.kpi-glow { position: absolute; top: -40px; right: -40px; width: 110px; height: 110px;
            border-radius: 50%; filter: blur(40px); opacity: .18; }
.kpi-label { font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.kpi-value { font-family: 'Syne', sans-serif; font-size: 2.2rem; font-weight: 800;
             line-height: 1.1; margin: 6px 0 4px; }
.kpi-sub   { font-size: .78rem; color: var(--muted); }

/* ── Section headers ── */
.sh { font-family: 'Syne', sans-serif; font-size: .7rem; letter-spacing: .14em;
      text-transform: uppercase; color: var(--muted); padding-bottom: 8px;
      border-bottom: 1px solid var(--border); margin: 28px 0 16px; }

/* ── Badges ── */
.badge { display:inline-block; padding:2px 9px; border-radius:20px;
         font-size:.7rem; font-weight:600; font-family:'Syne',sans-serif; }
.b-green  { background:rgba(34,212,123,.12); color:#22d47b; border:1px solid rgba(34,212,123,.25); }
.b-orange { background:rgba(245,165,36,.12); color:#f5a524; border:1px solid rgba(245,165,36,.25); }
.b-red    { background:rgba(242,92,92,.12);  color:#f25c5c; border:1px solid rgba(242,92,92,.25); }
.b-blue   { background:rgba(79,110,247,.12); color:#4f6ef7; border:1px solid rgba(79,110,247,.25); }
.b-gray   { background:rgba(85,94,122,.12);  color:#8892aa; border:1px solid rgba(85,94,122,.25); }
.b-purple { background:rgba(167,139,250,.12);color:#a78bfa; border:1px solid rgba(167,139,250,.25); }

/* ── Buttons ── */
.stButton > button {
  background: var(--accent) !important; color: #fff !important;
  font-family: 'Syne', sans-serif !important; font-weight: 700 !important;
  font-size: .82rem !important; border: none !important;
  border-radius: 8px !important; padding: 9px 22px !important;
  transition: opacity .2s !important;
}
.stButton > button:hover { opacity: .82 !important; }

/* ── Inputs ── */
.stTextInput > div > div > input, .stSelectbox > div > div,
.stDateInput > div > div > input, .stTextArea textarea,
.stNumberInput > div > div > input {
  background: var(--s2) !important; border: 1px solid var(--border) !important;
  color: var(--text) !important; border-radius: 8px !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: var(--s1); border-radius: 10px; padding: 4px;
  border: 1px solid var(--border); gap: 3px;
}
.stTabs [data-baseweb="tab"] {
  color: var(--muted) !important; font-family: 'Syne', sans-serif !important;
  font-size: .77rem !important; border-radius: 7px !important;
}
.stTabs [aria-selected="true"] { background: var(--accent) !important; color: #fff !important; }

/* ── DataFrame ── */
.stDataFrame { border-radius: 10px; overflow: hidden; }
[data-testid="stDataFrame"] th { background: var(--s2) !important; }

div[data-testid="stMetric"] { background: var(--s1); border: 1px solid var(--border);
  border-radius: 12px; padding: 14px; }
hr { border-color: var(--border); }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# PLOTLY BASE THEME
# ─────────────────────────────────────────────────────────
LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8892aa", size=12),
    margin=dict(l=10, r=10, t=36, b=10),
    xaxis=dict(gridcolor="#1a1f2e", linecolor="#1a1f2e", zerolinecolor="#1a1f2e"),
    yaxis=dict(gridcolor="#1a1f2e", linecolor="#1a1f2e", zerolinecolor="#1a1f2e"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1a1f2e"),
    colorway=["#4f6ef7","#22d47b","#f5a524","#f25c5c","#a78bfa","#38bdf8","#fb923c","#e879f9"],
)

# ─────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────
def hdrs(token): return {"access-token": token, "Content-Type": "application/json"}

def api_get(token, path, params=None):
    try:
        r = requests.get(f"{BASE_URL}/{path}", headers=hdrs(token), params=params, timeout=20)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return -1, str(e)

def api_patch(token, path, body):
    try:
        r = requests.patch(f"{BASE_URL}/{path}", headers=hdrs(token), json=body, timeout=20)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return -1, str(e)

def api_post(token, path, body):
    try:
        r = requests.post(f"{BASE_URL}/{path}", headers=hdrs(token), json=body, timeout=20)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return -1, str(e)

def items(resp): return resp.get("items", []) if isinstance(resp, dict) else []

# ─────────────────────────────────────────────────────────
# HELPERS UI
# ─────────────────────────────────────────────────────────
def kpi(label, value, sub="", color="var(--accent)"):
    st.markdown(f"""
    <div class="kpi">
      <div class="kpi-glow" style="background:{color}"></div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" style="color:{color}">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def sh(text): st.markdown(f'<div class="sh">{text}</div>', unsafe_allow_html=True)

def badge(text, kind="gray"):
    return f'<span class="badge b-{kind}">{text}</span>'

def fig(f): st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})

# ─────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 0 20px">
      <div style="font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:#e6e8f0">⚡ Kashio</div>
      <div style="font-size:.72rem;color:#555e7a;letter-spacing:.08em">BOTMAKER DASHBOARD</div>
    </div>""", unsafe_allow_html=True)

    token = st.text_input("Access Token", type="password", placeholder="Tu token de Botmaker…")

    if token:
        sc, d = api_get(token, "agents")
        if sc == 200:
            n = len(items(d))
            st.markdown(f'<div style="background:rgba(34,212,123,.07);border:1px solid rgba(34,212,123,.2);'
                        f'border-radius:8px;padding:9px 12px;font-size:.8rem;color:#22d47b;margin:8px 0">'
                        f'✅ Conectado · {n} agentes</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:rgba(242,92,92,.07);border:1px solid rgba(242,92,92,.2);'
                        f'border-radius:8px;padding:9px 12px;font-size:.8rem;color:#f25c5c;margin:8px 0">'
                        f'⚠️ Token inválido</div>', unsafe_allow_html=True)

    st.markdown('<hr style="margin:12px 0">', unsafe_allow_html=True)
    page = st.radio("", [
        "📊  Resumen",
        "👥  Agentes",
        "🗂  Sesiones",
        "💬  Chats",
        "🎯  Intents",
        "📡  Canales",
        "📋  Templates WA",
        "🔍  Auditoría",
    ], label_visibility="collapsed")

    st.markdown('<hr style="margin:12px 0">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.68rem;color:#555e7a;font-family:monospace">API v2.0 · api.botmaker.com</div>',
                unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# GATE
# ─────────────────────────────────────────────────────────
if not token:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:65vh;gap:20px;text-align:center">
      <div style="font-size:5rem">⚡</div>
      <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800">Kashio · Botmaker</div>
      <div style="color:#555e7a;max-width:380px;line-height:1.6">
        Ingresá tu <strong style="color:#4f6ef7">Access Token</strong> en el panel izquierdo.<br>
        Settings → API en tu cuenta Botmaker.
      </div>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════
# PAGE: RESUMEN
# ══════════════════════════════════════════════════════════
if page == "📊  Resumen":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800;margin-bottom:4px">Resumen general</h2>', unsafe_allow_html=True)
    today = datetime.utcnow()
    week_ago = today - timedelta(days=7)

    # ── Cargar datos en paralelo ──
    with st.spinner("Cargando métricas…"):
        sc_ag, d_ag   = api_get(token, "agents")
        sc_ag2, d_ag2 = api_get(token, "agents", {"online": "true"})
        sc_ch, d_ch   = api_get(token, "channels")
        sc_in, d_in   = api_get(token, "intents")
        sc_tpl, d_tpl = api_get(token, "whatsapp/templates")
        sc_ses, d_ses = api_get(token, "sessions", {
            "from": week_ago.strftime("%Y-%m-%dT00:00:00Z"),
            "to":   today.strftime("%Y-%m-%dT23:59:59Z"),
            "include-events": "true",
        })
        sc_cht, d_cht = api_get(token, "chats", {
            "from": week_ago.strftime("%Y-%m-%dT00:00:00Z"),
        })

    # ── KPI row ──
    ag_list  = items(d_ag)   if sc_ag  == 200 else []
    ag_on    = items(d_ag2)  if sc_ag2 == 200 else []
    ch_list  = items(d_ch)   if sc_ch  == 200 else []
    in_list  = items(d_in)   if sc_in  == 200 else []
    tpl_list = items(d_tpl)  if sc_tpl == 200 else []
    ses_list = items(d_ses)  if sc_ses == 200 else []
    cht_list = items(d_cht)  if sc_cht == 200 else []

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi("Agentes totales", len(ag_list), f"🟢 {len(ag_on)} en línea", "var(--accent)")
    with c2: kpi("Sesiones (7d)", len(ses_list), "", "var(--green)")
    with c3: kpi("Chats (7d)", len(cht_list), f"{sum(1 for c in cht_list if c.get('agentId'))} con agente", "var(--orange)")
    with c4: kpi("Intents activos", sum(1 for i in in_list if i.get("active")), f"de {len(in_list)} totales", "var(--purple)")
    with c5: kpi("Canales", len(ch_list), "plataformas activas", "var(--sky)")

    st.markdown("")
    col_l, col_r = st.columns([3, 2])

    # ── Sesiones por día ──
    with col_l:
        sh("Sesiones por día — últimos 7 días")
        if ses_list:
            df = pd.DataFrame(ses_list)
            df["ts"] = pd.to_datetime(df["creationTime"], errors="coerce")
            df["cause"] = df["startingCause"]
            by_day = df.groupby([df["ts"].dt.date, "cause"]).size().reset_index(name="n")
            by_day.columns = ["Fecha", "Origen", "n"]
            f1 = px.bar(by_day, x="Fecha", y="n", color="Origen", barmode="stack",
                        title="Sesiones por día y origen",
                        color_discrete_map={"Organic": "#4f6ef7", "WhatsAppTemplate": "#f5a524"})
            f1.update_layout(**LAYOUT)
            f1.update_traces(marker_cornerradius=4)
            fig(f1)

            sh("Eventos de sesión — distribución")
            event_names = []
            for s in ses_list:
                for e in s.get("events", []):
                    event_names.append(e["name"])
            if event_names:
                ev_df = pd.Series(event_names).value_counts().reset_index()
                ev_df.columns = ["Evento", "n"]
                f2 = px.bar(ev_df, x="n", y="Evento", orientation="h",
                            color="n", color_continuous_scale=["#1f2333", "#4f6ef7"])
                f2.update_layout(**LAYOUT, coloraxis_showscale=False,
                                 margin=dict(l=160, r=10, t=10, b=10))
                f2.update_traces(marker_cornerradius=3)
                fig(f2)

    # ── Agentes + Chats ──
    with col_r:
        sh("Agentes — estado isOnline vs status")
        if ag_list:
            df_a = pd.DataFrame(ag_list)
            online_counts = df_a["isOnline"].value_counts().rename({True: "En línea", False: "Offline"})
            f3 = px.pie(online_counts.reset_index(), names="isOnline", values="count",
                        color_discrete_map={"En línea": "#22d47b", "Offline": "#1f2333"},
                        hole=0.62)
            f3.update_layout(**LAYOUT, margin=dict(l=0, r=0, t=0, b=0),
                             showlegend=True, legend=dict(x=0.7, y=0.5))
            f3.update_traces(textinfo="percent+label")
            fig(f3)

        sh("Chats — distribución por queue")
        if cht_list:
            queues = [c.get("queueId") or "Sin queue" for c in cht_list]
            q_df = pd.Series(queues).value_counts().reset_index()
            q_df.columns = ["Queue", "n"]
            f4 = px.bar(q_df, x="Queue", y="n",
                        color_discrete_sequence=["#a78bfa"])
            f4.update_layout(**LAYOUT, margin=dict(l=10, r=10, t=10, b=40))
            f4.update_traces(marker_cornerradius=5)
            fig(f4)

        sh("Chats — Bot activo vs silenciado")
        if cht_list:
            muted = sum(1 for c in cht_list if c.get("isBotMuted"))
            active = len(cht_list) - muted
            f5 = go.Figure(go.Bar(
                x=["Bot activo", "Bot silenciado"],
                y=[active, muted],
                marker_color=["#22d47b", "#f25c5c"],
                text=[active, muted], textposition="outside"
            ))
            f5.update_layout(**LAYOUT, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            f5.update_traces(marker_cornerradius=5)
            fig(f5)


# ══════════════════════════════════════════════════════════
# PAGE: AGENTES
# ══════════════════════════════════════════════════════════
elif page == "👥  Agentes":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Agentes</h2>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 Lista y métricas", "✏️ Editar agente"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            only_online = st.checkbox("Solo en línea (isOnline = true)")
        with c2:
            email_filter = st.text_input("Filtrar por emails (separados por coma)")

        if st.button("🔄 Cargar agentes"):
            params = {}
            if only_online: params["online"] = "true"
            if email_filter: params["emails"] = email_filter.strip()

            with st.spinner("Cargando…"):
                sc, d = api_get(token, "agents", params or None)

            if sc == 200:
                ag = items(d)
                df = pd.DataFrame(ag)

                # KPIs
                k1, k2, k3, k4 = st.columns(4)
                with k1: kpi("Total agentes", len(df), "", "var(--accent)")
                with k2:
                    on = int(df["isOnline"].sum()) if "isOnline" in df else 0
                    kpi("En línea (isOnline)", on, f"de {len(df)}", "var(--green)")
                with k3:
                    busy = int((df["status"] == "busy").sum()) if "status" in df else 0
                    kpi("Status: busy", busy, "", "var(--orange)")
                with k4:
                    high = int((df["priority"] == "high").sum()) if "priority" in df else 0
                    kpi("Priority: high", high, "", "var(--purple)")

                st.markdown("")
                col_l, col_r = st.columns(2)
                with col_l:
                    sh("Distribución por status")
                    st_df = df["status"].value_counts().reset_index()
                    st_df.columns = ["Status", "n"]
                    f = px.bar(st_df, x="Status", y="n", color="Status",
                               color_discrete_sequence=["#4f6ef7","#22d47b","#f5a524","#f25c5c"])
                    f.update_layout(**LAYOUT); f.update_traces(marker_cornerradius=5)
                    fig(f)

                with col_r:
                    sh("Distribución por priority")
                    pr_df = df["priority"].value_counts().reset_index()
                    pr_df.columns = ["Priority", "n"]
                    f2 = px.pie(pr_df, names="Priority", values="n", hole=0.55,
                                color_discrete_sequence=["#4f6ef7","#a78bfa","#22d47b"])
                    f2.update_layout(**LAYOUT)
                    fig(f2)

                sh("Tabla de agentes")
                # Build display table
                rows = []
                for a in ag:
                    rows.append({
                        "Nombre": a.get("name", ""),
                        "Email": a.get("email", ""),
                        "isOnline": "🟢 Sí" if a.get("isOnline") else "⚫ No",
                        "Status": a.get("status", ""),
                        "Priority": a.get("priority", ""),
                        "Slots": a.get("slots", 0),
                        "Queues": ", ".join(a.get("queues", [])),
                        "Desde": a.get("creationTime", "")[:10],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.error(f"Error {sc}: {d}")

    with tab2:
        agent_id = st.text_input("Agent ID")
        c1, c2 = st.columns(2)
        with c1:
            e_name  = st.text_input("Nombre")
            e_email = st.text_input("Email")
            e_slots = st.number_input("Slots", min_value=0, max_value=50, value=0)
        with c2:
            e_priority = st.selectbox("Priority", ["— sin cambiar —", "high", "normal"])
            e_status   = st.selectbox("Status",   ["— sin cambiar —", "online", "busy"])
            e_queues   = st.text_input("Queues (separados por coma)")

        if st.button("💾 Guardar cambios") and agent_id:
            body = {}
            if e_name:  body["name"]  = e_name
            if e_email: body["email"] = e_email
            if e_slots: body["slots"] = e_slots
            if e_priority != "— sin cambiar —": body["priority"] = e_priority
            if e_status   != "— sin cambiar —": body["status"]   = e_status
            if e_queues: body["queues"] = [q.strip() for q in e_queues.split(",")]
            sc, d = api_patch(token, f"agents/{agent_id}", body)
            if sc == 200: st.success("Agente actualizado."); st.json(d)
            else: st.error(f"Error {sc}: {d}")


# ══════════════════════════════════════════════════════════
# PAGE: SESIONES
# ══════════════════════════════════════════════════════════
elif page == "🗂  Sesiones":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Sesiones</h2>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1: d_from = st.date_input("Desde", value=datetime.utcnow() - timedelta(days=7))
    with c2: d_to   = st.date_input("Hasta", value=datetime.utcnow())
    with c3:
        st.markdown(""); st.markdown("")
        load = st.button("🔄 Cargar sesiones")

    if load:
        params = {
            "from": d_from.strftime("%Y-%m-%dT00:00:00Z"),
            "to":   d_to.strftime("%Y-%m-%dT23:59:59Z"),
            "include-events": "true",
        }
        with st.spinner("Cargando sesiones…"):
            sc, d = api_get(token, "sessions", params)

        if sc == 200:
            ses = items(d)
            df  = pd.DataFrame(ses)

            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            organic = sum(1 for s in ses if s.get("startingCause") == "Organic")
            wa_tpl  = sum(1 for s in ses if s.get("startingCause") == "WhatsAppTemplate")
            all_ev  = [e["name"] for s in ses for e in s.get("events", [])]
            agent_ev = all_ev.count("assigned-to-agent")

            with k1: kpi("Sesiones totales", len(ses), d_from.strftime("%d/%m") + " – " + d_to.strftime("%d/%m"), "var(--accent)")
            with k2: kpi("Orgánicas", organic, "startingCause: Organic", "var(--green)")
            with k3: kpi("Via Template WA", wa_tpl, "startingCause: WhatsAppTemplate", "var(--orange)")
            with k4: kpi("Asignaciones a agente", agent_ev, "evento assigned-to-agent", "var(--purple)")

            st.markdown("")
            col_l, col_r = st.columns(2)

            with col_l:
                sh("Origen de sesiones (startingCause)")
                cause_df = df["startingCause"].value_counts().reset_index()
                cause_df.columns = ["Causa", "n"]
                f1 = px.pie(cause_df, names="Causa", values="n", hole=0.55,
                            color_discrete_map={"Organic": "#4f6ef7", "WhatsAppTemplate": "#f5a524"})
                f1.update_layout(**LAYOUT)
                fig(f1)

                sh("Sesiones por día")
                df["ts"] = pd.to_datetime(df["creationTime"], errors="coerce")
                by_day = df.groupby(df["ts"].dt.date).size().reset_index(name="n")
                by_day.columns = ["Fecha", "n"]
                f2 = px.area(by_day, x="Fecha", y="n", color_discrete_sequence=["#4f6ef7"])
                f2.update_layout(**LAYOUT)
                f2.update_traces(fill="tozeroy", fillcolor="rgba(79,110,247,.08)", line_color="#4f6ef7")
                fig(f2)

            with col_r:
                sh("Eventos en sesiones — top tipos")
                if all_ev:
                    ev_df = pd.Series(all_ev).value_counts().reset_index()
                    ev_df.columns = ["Evento", "n"]
                    f3 = px.bar(ev_df, x="n", y="Evento", orientation="h",
                                color="n", color_continuous_scale=["#1a1f2e","#4f6ef7"])
                    f3.update_layout(**LAYOUT, coloraxis_showscale=False,
                                     margin=dict(l=160, r=10, t=10, b=10))
                    f3.update_traces(marker_cornerradius=3)
                    fig(f3)

                sh("Eventos por sesión — promedio")
                df["n_events"] = df["events"].apply(lambda x: len(x) if isinstance(x, list) else 0)
                f4 = px.histogram(df, x="n_events", nbins=15, color_discrete_sequence=["#22d47b"])
                f4.update_layout(**LAYOUT, xaxis_title="Nº de eventos", yaxis_title="Sesiones")
                f4.update_traces(marker_cornerradius=3)
                fig(f4)

            sh("Detalle de sesiones")
            rows = []
            for s in ses[:200]:
                chat = s.get("chat", {})
                chat_inner = chat.get("chat", {})
                rows.append({
                    "ID Sesión": s.get("id","")[:20] + "…",
                    "Fecha": s.get("creationTime","")[:16].replace("T"," "),
                    "Causa": s.get("startingCause",""),
                    "Contact": chat_inner.get("contactId",""),
                    "Canal": chat_inner.get("channelId","").split("-")[-1] if chat_inner.get("channelId") else "",
                    "Nombre": chat.get("firstName",""),
                    "Eventos": len(s.get("events",[])),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.error(f"Error {sc}: {d}")


# ══════════════════════════════════════════════════════════
# PAGE: CHATS
# ══════════════════════════════════════════════════════════
elif page == "💬  Chats":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Chats</h2>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 Lista & análisis", "🔍 Buscar chat", "✏️ Actualizar chat"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1: d_from = st.date_input("Desde", value=datetime.utcnow() - timedelta(days=7), key="cht_from")
        with c2:
            st.markdown(""); st.markdown("")
            load = st.button("🔄 Cargar chats")

        if load:
            with st.spinner("Cargando chats…"):
                sc, d = api_get(token, "chats", {
                    "from": d_from.strftime("%Y-%m-%dT00:00:00Z"),
                })
            if sc == 200:
                cht = items(d)
                df  = pd.DataFrame(cht)

                k1, k2, k3, k4 = st.columns(4)
                muted  = sum(1 for c in cht if c.get("isBotMuted"))
                ag_ass = sum(1 for c in cht if c.get("agentId"))
                pe_cnt = sum(1 for c in cht if c.get("country") == "PE")
                with k1: kpi("Chats totales",    len(cht),  "", "var(--accent)")
                with k2: kpi("Con agente asignado", ag_ass, f"de {len(cht)}", "var(--green)")
                with k3: kpi("Bot silenciado",   muted,     f"{100*muted//len(cht) if cht else 0}%", "var(--orange)")
                with k4: kpi("País PE",          pe_cnt,    "Perú", "var(--sky)")

                st.markdown("")
                col_l, col_r = st.columns(2)

                with col_l:
                    sh("Por queue (queueId)")
                    queues = [c.get("queueId") or "Sin queue" for c in cht]
                    q_df = pd.Series(queues).value_counts().reset_index()
                    q_df.columns = ["Queue", "n"]
                    f1 = px.bar(q_df, x="Queue", y="n", color="Queue",
                                color_discrete_sequence=["#4f6ef7","#22d47b","#f5a524","#f25c5c","#a78bfa"])
                    f1.update_layout(**LAYOUT); f1.update_traces(marker_cornerradius=5)
                    fig(f1)

                    sh("Por país (country)")
                    ctry = [c.get("country") or "Desconocido" for c in cht]
                    ct_df = pd.Series(ctry).value_counts().reset_index()
                    ct_df.columns = ["País", "n"]
                    f2 = px.pie(ct_df, names="País", values="n", hole=0.55,
                                color_discrete_sequence=["#4f6ef7","#22d47b","#f5a524","#a78bfa"])
                    f2.update_layout(**LAYOUT)
                    fig(f2)

                with col_r:
                    sh("isBotMuted — bot activo vs silenciado")
                    muted_df = pd.Series(
                        ["Silenciado" if c.get("isBotMuted") else "Activo" for c in cht]
                    ).value_counts().reset_index()
                    muted_df.columns = ["Estado", "n"]
                    f3 = px.pie(muted_df, names="Estado", values="n", hole=0.55,
                                color_discrete_map={"Activo":"#22d47b","Silenciado":"#f25c5c"})
                    f3.update_layout(**LAYOUT)
                    fig(f3)

                    sh("Actividad reciente — lastUserMessageDatetime")
                    ts_col = "lastUserMessageDatetime"
                    dates = [c.get(ts_col,"")[:10] for c in cht if c.get(ts_col)]
                    if dates:
                        d_df = pd.Series(dates).value_counts().sort_index().reset_index()
                        d_df.columns = ["Fecha","n"]
                        f4 = px.area(d_df, x="Fecha", y="n", color_discrete_sequence=["#22d47b"])
                        f4.update_layout(**LAYOUT)
                        f4.update_traces(fill="tozeroy", fillcolor="rgba(34,212,123,.07)")
                        fig(f4)

                sh("Detalle de chats")
                rows = []
                for c in cht:
                    ci = c.get("chat", {})
                    rows.append({
                        "Nombre":    c.get("firstName",""),
                        "País":      c.get("country",""),
                        "Queue":     c.get("queueId",""),
                        "Bot muted": "Sí" if c.get("isBotMuted") else "No",
                        "Agente":    c.get("agentId","")[:12] + "…" if c.get("agentId") else "",
                        "Último msg": c.get("lastUserMessageDatetime","")[:16].replace("T"," "),
                        "Tags":      ", ".join(c.get("tags",[])) or "—",
                        "ChatID":    ci.get("chatId","")[:14] + "…",
                        "Canal":     ci.get("channelId","").split("-")[-1],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.error(f"Error {sc}: {d}")

    with tab2:
        kind = st.radio("Buscar por", ["Chat ID", "Nombre"], horizontal=True)
        val  = st.text_input("Valor")
        if st.button("🔍 Buscar") and val:
            if kind == "Chat ID":
                sc, d = api_get(token, f"chats/{val}")
                if sc == 200: st.json(d)
                else: st.error(f"{sc}: {d}")
            else:
                sc, d = api_get(token, "chats", {"name": val})
                if sc == 200: st.dataframe(pd.DataFrame(items(d)), use_container_width=True, hide_index=True)
                else: st.error(f"{sc}: {d}")

    with tab3:
        chat_id = st.text_input("Chat ID a actualizar")
        c1, c2  = st.columns(2)
        with c1:
            u_first = st.text_input("Nombre (firstName)")
            u_email = st.text_input("Email")
            u_queue = st.text_input("Queue ID")
        with c2:
            u_tags  = st.text_input("Tags (coma separados)")
            u_vars  = st.text_area("Variables JSON", placeholder='{"key":"value"}', height=80)

        if st.button("💾 Actualizar chat") and chat_id:
            body = {}
            if u_first: body["firstName"] = u_first
            if u_email: body["email"]     = u_email
            if u_queue: body["queueId"]   = u_queue
            if u_tags:  body["tags"]      = [t.strip() for t in u_tags.split(",")]
            if u_vars:
                try: body["variables"] = json.loads(u_vars)
                except: st.warning("JSON de variables inválido"); st.stop()
            sc, d = api_patch(token, f"chats/{chat_id}", body)
            if sc == 200: st.success("Actualizado."); st.json(d)
            else: st.error(f"{sc}: {d}")


# ══════════════════════════════════════════════════════════
# PAGE: INTENTS
# ══════════════════════════════════════════════════════════
elif page == "🎯  Intents":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Intents</h2>', unsafe_allow_html=True)

    if st.button("🔄 Cargar intents"):
        with st.spinner("Cargando…"):
            sc, d = api_get(token, "intents")

        if sc == 200:
            ilist = items(d)

            k1, k2, k3, k4 = st.columns(4)
            active   = sum(1 for i in ilist if i.get("active"))
            inactive = len(ilist) - active
            all_topics = [t for i in ilist for t in i.get("topics", [])]
            unique_topics = len(set(all_topics))
            bots = list(set(i.get("bot",{}).get("name","") for i in ilist if i.get("bot")))

            with k1: kpi("Intents totales", len(ilist), "", "var(--accent)")
            with k2: kpi("Activos", active,   f"{100*active//len(ilist) if ilist else 0}%", "var(--green)")
            with k3: kpi("Inactivos", inactive, "", "var(--red)")
            with k4: kpi("Topics únicos", unique_topics, f"{len(bots)} bot(s)", "var(--purple)")

            st.markdown("")
            col_l, col_r = st.columns(2)

            with col_l:
                sh("Top 15 topics por frecuencia")
                top_topics = pd.Series(all_topics).value_counts().head(15).reset_index()
                top_topics.columns = ["Topic", "n"]
                f1 = px.bar(top_topics, x="n", y="Topic", orientation="h",
                            color="n", color_continuous_scale=["#1a1f2e","#a78bfa"])
                f1.update_layout(**LAYOUT, coloraxis_showscale=False,
                                 margin=dict(l=160, r=10, t=10, b=10))
                f1.update_traces(marker_cornerradius=3)
                fig(f1)

            with col_r:
                sh("Activos vs inactivos")
                f2 = px.pie(
                    pd.DataFrame({"Estado":["Activo","Inactivo"],"n":[active,inactive]}),
                    names="Estado", values="n", hole=0.6,
                    color_discrete_map={"Activo":"#22d47b","Inactivo":"#f25c5c"},
                )
                f2.update_layout(**LAYOUT)
                fig(f2)

                sh("Intents por bot")
                bot_names = [i.get("bot",{}).get("name","Sin bot") for i in ilist]
                bot_df = pd.Series(bot_names).value_counts().reset_index()
                bot_df.columns = ["Bot","n"]
                f3 = px.bar(bot_df, x="Bot", y="n", color_discrete_sequence=["#38bdf8"])
                f3.update_layout(**LAYOUT); f3.update_traces(marker_cornerradius=5)
                fig(f3)

            sh("Tabla de intents")
            rows = [{"Nombre": i.get("name",""), "Bot": i.get("bot",{}).get("name",""),
                     "Activo": "✅" if i.get("active") else "❌",
                     "Topics": ", ".join(i.get("topics",[])),
                     "Triggers": len(i.get("triggers",[])),
                     "ID": i.get("id","")} for i in ilist]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.error(f"Error {sc}: {d}")


# ══════════════════════════════════════════════════════════
# PAGE: CANALES
# ══════════════════════════════════════════════════════════
elif page == "📡  Canales":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Canales</h2>', unsafe_allow_html=True)

    if st.button("🔄 Cargar canales"):
        with st.spinner("Cargando…"):
            sc, d  = api_get(token, "channels")
            sc2,d2 = api_get(token, "whatsapp/accounts")

        if sc == 200:
            chs = items(d)
            df  = pd.DataFrame(chs)

            k1, k2, k3 = st.columns(3)
            with k1: kpi("Canales totales", len(chs), "", "var(--accent)")
            with k2:
                active = sum(1 for c in chs if c.get("active"))
                kpi("Activos", active, "", "var(--green)")
            with k3:
                wa = sum(1 for c in chs if c.get("platform") == "whatsapp")
                kpi("WhatsApp", wa, "", "var(--sky)")

            st.markdown("")
            col_l, col_r = st.columns(2)

            with col_l:
                sh("Distribución por plataforma")
                plat = df["platform"].value_counts().reset_index()
                plat.columns = ["Plataforma","n"]
                f1 = px.bar(plat, x="Plataforma", y="n", color="Plataforma",
                            color_discrete_sequence=["#4f6ef7","#22d47b","#f5a524",
                                                     "#f25c5c","#a78bfa","#38bdf8","#fb923c"])
                f1.update_layout(**LAYOUT); f1.update_traces(marker_cornerradius=5)
                fig(f1)

            with col_r:
                sh("Activo vs inactivo por plataforma")
                df["Estado"] = df["active"].map({True:"Activo",False:"Inactivo"})
                cross = df.groupby(["platform","Estado"]).size().reset_index(name="n")
                f2 = px.bar(cross, x="platform", y="n", color="Estado", barmode="stack",
                            color_discrete_map={"Activo":"#22d47b","Inactivo":"#f25c5c"})
                f2.update_layout(**LAYOUT); f2.update_traces(marker_cornerradius=3)
                fig(f2)

            sh("Tabla de canales")
            rows = [{"ID": c.get("id",""), "Plataforma": c.get("platform",""),
                     "Activo": "✅" if c.get("active") else "❌",
                     "Número": c.get("number",""),
                     "WABA ID": c.get("wabaId",""),
                     "Trial": "Sí" if c.get("trial") else "No"} for c in chs]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if sc2 == 200:
                sh("Cuentas WhatsApp")
                wa_list = items(d2)
                if wa_list:
                    wa_rows = [{"Número": w.get("number",""), "Alias": w.get("alias",""),
                                "WABA ID": w.get("wabaId",""),
                                "Template NS": w.get("templateNamespace","")} for w in wa_list]
                    st.dataframe(pd.DataFrame(wa_rows), use_container_width=True, hide_index=True)
        else:
            st.error(f"Error {sc}: {d}")


# ══════════════════════════════════════════════════════════
# PAGE: TEMPLATES WA
# ══════════════════════════════════════════════════════════
elif page == "📋  Templates WA":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Templates WhatsApp</h2>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Ver templates", "➕ Crear template"])

    with tab1:
        if st.button("🔄 Cargar templates"):
            with st.spinner("Cargando…"):
                sc, d = api_get(token, "whatsapp/templates")

            if sc == 200:
                tpls = items(d)

                k1, k2, k3, k4 = st.columns(4)
                approved  = sum(1 for t in tpls if t.get("state") == "APPROVED")
                marketing = sum(1 for t in tpls if t.get("category") == "MARKETING")
                utility   = sum(1 for t in tpls if t.get("category") == "UTILITY")
                with_btns = sum(1 for t in tpls if t.get("buttons"))

                with k1: kpi("Templates totales", len(tpls), "", "var(--accent)")
                with k2: kpi("Aprobados", approved, "state: APPROVED", "var(--green)")
                with k3: kpi("Marketing", marketing, "category: MARKETING", "var(--orange)")
                with k4: kpi("Con botones", with_btns, "", "var(--purple)")

                st.markdown("")
                col_l, col_r = st.columns(2)

                with col_l:
                    sh("Por categoría")
                    cat_df = pd.Series([t.get("category","") for t in tpls]).value_counts().reset_index()
                    cat_df.columns = ["Categoría","n"]
                    f1 = px.pie(cat_df, names="Categoría", values="n", hole=0.55,
                                color_discrete_map={"MARKETING":"#f5a524","UTILITY":"#4f6ef7","OTP":"#22d47b"})
                    f1.update_layout(**LAYOUT)
                    fig(f1)

                with col_r:
                    sh("Por idioma (locale)")
                    loc_df = pd.Series([t.get("locale","") for t in tpls]).value_counts().reset_index()
                    loc_df.columns = ["Idioma","n"]
                    f2 = px.bar(loc_df, x="Idioma", y="n", color_discrete_sequence=["#a78bfa"])
                    f2.update_layout(**LAYOUT); f2.update_traces(marker_cornerradius=5)
                    fig(f2)

                sh("Tabla de templates")
                rows = []
                for t in tpls:
                    body_text = t.get("body",{}).get("text","") if isinstance(t.get("body"),dict) else ""
                    btns = t.get("buttons",[]) or []
                    rows.append({
                        "Nombre": t.get("name",""),
                        "Estado": t.get("state",""),
                        "Categoría": t.get("category",""),
                        "Idioma": t.get("locale",""),
                        "Botones": len(btns),
                        "Solicitante": t.get("requesterEmail",""),
                        "Preview": body_text[:60] + ("…" if len(body_text)>60 else ""),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                sh("Vista previa de templates")
                for t in tpls[:6]:
                    with st.expander(f"📄 {t.get('name','')}  ·  {t.get('category','')}  ·  {t.get('state','')}"):
                        body_text = t.get("body",{}).get("text","") if isinstance(t.get("body"),dict) else ""
                        st.markdown(f"**Cuerpo:**\n\n{body_text}")
                        btns = t.get("buttons",[]) or []
                        if btns:
                            st.markdown("**Botones:**")
                            for b in btns:
                                st.markdown(f"- `{b.get('type','')}` → **{b.get('text','')}**"
                                            + (f"  [{b.get('url','')}]" if b.get("url") else ""))
            else:
                st.error(f"Error {sc}: {d}")

    with tab2:
        c1, c2, c3 = st.columns(3)
        with c1: tpl_name = st.text_input("Nombre (snake_case)")
        with c2: tpl_lang = st.selectbox("Idioma", ["es","en","pt_BR","fr","de","it"])
        with c3: tpl_cat  = st.selectbox("Categoría", ["MARKETING","UTILITY","OTP"])

        tpl_body   = st.text_area("Cuerpo del template", height=100,
                                  placeholder="Hola {{1}}, tu pedido {{2}} está listo.")
        tpl_header = st.text_input("Header (opcional)")
        tpl_footer = st.text_input("Footer (opcional)")

        if st.button("➕ Crear template") and tpl_name and tpl_body:
            body = {"name": tpl_name, "language": tpl_lang, "category": tpl_cat,
                    "components": [{"type":"BODY","text":tpl_body}]}
            if tpl_header: body["components"].insert(0, {"type":"HEADER","format":"TEXT","text":tpl_header})
            if tpl_footer: body["components"].append({"type":"FOOTER","text":tpl_footer})
            sc, resp = api_post(token, "whatsapp/templates", body)
            if sc in (200,201): st.success("Template creado."); st.json(resp)
            else: st.error(f"Error {sc}: {resp}")


# ══════════════════════════════════════════════════════════
# PAGE: AUDITORÍA
# ══════════════════════════════════════════════════════════
elif page == "🔍  Auditoría":
    st.markdown('<h2 style="font-family:Syne,sans-serif;font-weight:800">Auditoría</h2>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["👤 Agentes", "🎯 Intents"])

    def render_audit(endpoint, key_prefix):
        c1, c2, c3 = st.columns(3)
        with c1: a_from = st.date_input("Desde", value=datetime.utcnow()-timedelta(days=30), key=key_prefix+"_f")
        with c2: a_to   = st.date_input("Hasta", value=datetime.utcnow(), key=key_prefix+"_t")
        with c3:
            st.markdown(""); st.markdown("")
            load = st.button("🔄 Cargar", key=key_prefix+"_btn")

        if endpoint == "audits/agent":
            extra = st.text_input("Filtrar por emails de autores (opcional)", key=key_prefix+"_em")
        else:
            extra = st.text_input("Search keyword (opcional)", key=key_prefix+"_kw")

        if load:
            params = {"from": a_from.strftime("%Y-%m-%d"), "to": a_to.strftime("%Y-%m-%d")}
            if extra:
                params["authors" if endpoint == "audits/agent" else "search-keyword"] = extra.strip()

            with st.spinner("Cargando…"):
                sc, d = api_get(token, endpoint, params)

            if sc == 200:
                aud = items(d)
                if not aud: st.info("Sin registros."); return

                k1, k2, k3 = st.columns(3)
                actions  = [a.get("action","") for a in aud]
                authors  = [a.get("authorName","") for a in aud]
                with k1: kpi("Registros", len(aud), "", "var(--accent)")
                with k2: kpi("Autores únicos", len(set(authors)), "", "var(--green)")
                with k3: kpi("Tipo de acción top", Counter(actions).most_common(1)[0][0] if actions else "—", "", "var(--orange)")

                st.markdown("")
                col_l, col_r = st.columns(2)

                with col_l:
                    sh("Acciones por autor")
                    auth_df = pd.Series(authors).value_counts().reset_index()
                    auth_df.columns = ["Autor","n"]
                    f1 = px.bar(auth_df, x="n", y="Autor", orientation="h",
                                color_discrete_sequence=["#4f6ef7"])
                    f1.update_layout(**LAYOUT, margin=dict(l=140, r=10, t=10, b=10))
                    f1.update_traces(marker_cornerradius=3)
                    fig(f1)

                with col_r:
                    sh("Acciones por día")
                    df = pd.DataFrame(aud)
                    df["ts"] = pd.to_datetime(df["creationTime"], errors="coerce")
                    by_day = df.groupby(df["ts"].dt.date).size().reset_index(name="n")
                    by_day.columns = ["Fecha","n"]
                    f2 = px.area(by_day, x="Fecha", y="n", color_discrete_sequence=["#22d47b"])
                    f2.update_layout(**LAYOUT)
                    f2.update_traces(fill="tozeroy", fillcolor="rgba(34,212,123,.08)")
                    fig(f2)

                sh("Detalle de auditoría")
                rows = []
                for a in aud:
                    chg = a.get("change", {})
                    rows.append({
                        "Fecha":  a.get("creationTime","")[:16].replace("T"," "),
                        "Autor":  a.get("authorName",""),
                        "Email":  a.get("authorEmail",""),
                        "Rol":    a.get("authorRole","")[:12]+"…" if len(a.get("authorRole",""))>12 else a.get("authorRole",""),
                        "Acción": a.get("action",""),
                        "Entity": a.get("entityId","")[:14]+"…",
                        "Cambios": ", ".join([f"{k}→{v}" for k,v in chg.items() if k in ("NAME","EMAIL","AVAILABLE_STATUS","PRIORITY","SLOTS")][:3]),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.error(f"Error {sc}: {d}")

    with tab1: render_audit("audits/agent",  "ag")
    with tab2: render_audit("audits/intent", "in")
