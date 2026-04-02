import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests as req_lib
from api_client import (
    health_check, get_students, create_student, run_pipeline,
    get_insights, get_ranking, get_student_status, get_features,
    get_student_history,
)

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Placement Intelligence System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ════════════════════════════════════════════════
   PIS DARK THEME — Design System
   Primary:   #22C55E  Hover: #16A34A  Glow: rgba(34,197,94,0.15)
   BG:        #0B0F14  Card: #111827   Surface: #1F2937
   Text:      #E5E7EB  Secondary: #9CA3AF  Muted: #6B7280
   Danger:    #EF4444  Warning: #F59E0B  Info: #3B82F6
════════════════════════════════════════════════ */

/* ── Base ── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main, .block-container {
    background-color: #0B0F14 !important;
    color: #E5E7EB !important;
}
[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid #1F2937 !important;
}
[data-testid="stSidebar"] * { color: #E5E7EB !important; }

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 { color: #F9FAFB !important; }
p, li, label, span, div { color: #E5E7EB; }
.stMarkdown p { color: #9CA3AF; }

/* ── Inputs ── */
input, textarea,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
    background: #1F2937 !important;
    border: 1px solid #374151 !important;
    color: #E5E7EB !important;
    border-radius: 8px !important;
    transition: border-color 0.2s ease;
}
input:focus, textarea:focus {
    border-color: #22C55E !important;
    box-shadow: 0 0 0 2px rgba(34,197,94,0.2) !important;
}
[data-baseweb="select"] > div {
    background: #1F2937 !important;
    border: 1px solid #374151 !important;
    color: #E5E7EB !important;
    border-radius: 8px !important;
}

/* ── Buttons ── */
[data-testid="stFormSubmitButton"] > button,
button[kind="primary"] {
    background: #22C55E !important;
    color: #000000 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    transition: background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease !important;
}
[data-testid="stFormSubmitButton"] > button:hover,
button[kind="primary"]:hover {
    background: #16A34A !important;
    transform: scale(1.02) !important;
    box-shadow: 0 0 16px rgba(34,197,94,0.35) !important;
}
button[kind="secondary"] {
    background: transparent !important;
    color: #22C55E !important;
    border: 1px solid #22C55E !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: background 0.2s ease, transform 0.15s ease !important;
}
button[kind="secondary"]:hover {
    background: rgba(34,197,94,0.1) !important;
    transform: scale(1.02) !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [role="slider"] {
    background: #22C55E !important;
    border-color: #22C55E !important;
}
[data-testid="stSlider"] > div > div > div > div {
    background: #22C55E !important;
}

/* ── Cards ── */
.pis-card {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    transition: box-shadow 0.2s ease;
}
.pis-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.5); }
.pis-card-accent {
    background: linear-gradient(135deg, rgba(34,197,94,0.08) 0%, #111827 100%);
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 2px 12px rgba(34,197,94,0.1);
}

/* ── Score hero ── */
.score-number {
    font-size: 3.2rem; font-weight: 800;
    color: #22C55E; line-height: 1; margin: 0;
}
.score-label {
    font-size: 0.78rem; color: #6B7280;
    text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px;
}
.category-badge {
    display: inline-block; padding: 4px 14px;
    border-radius: 20px; font-size: 0.85rem; font-weight: 600; margin-top: 10px;
}
.badge-ready    { background: rgba(34,197,94,0.15);  color: #22C55E; border: 1px solid rgba(34,197,94,0.3); }
.badge-near     { background: rgba(245,158,11,0.15); color: #F59E0B; border: 1px solid rgba(245,158,11,0.3); }
.badge-needs    { background: rgba(239,68,68,0.15);  color: #EF4444; border: 1px solid rgba(239,68,68,0.3); }

/* ── Section headers ── */
.section-title {
    font-size: 0.95rem; font-weight: 700; color: #F9FAFB;
    margin-bottom: 14px; padding-bottom: 8px;
    border-bottom: 1px solid #1F2937;
    letter-spacing: 0.02em;
}

/* ── Strength chips ── */
.strength-chip {
    background: rgba(34,197,94,0.08);
    border: 1px solid rgba(34,197,94,0.2);
    border-radius: 10px; padding: 10px 14px;
    font-size: 0.87rem; color: #86EFAC; margin-bottom: 8px;
}

/* ── Rec blocks ── */
.rec-block {
    border-left: 3px solid #22C55E;
    background: rgba(255,255,255,0.03);
    border-radius: 0 10px 10px 0;
    padding: 12px 16px; margin-bottom: 10px;
    transition: background 0.2s ease;
}
.rec-block:hover { background: rgba(255,255,255,0.05); }
.rec-block-critical  { border-left-color: #EF4444; }
.rec-block-important { border-left-color: #F59E0B; }
.rec-block-suggested { border-left-color: #3B82F6; }

/* ── Hero landing ── */
.hero-wrap { text-align: center; padding: 80px 20px 60px; }
.hero-title {
    font-size: 3.2rem; font-weight: 900;
    background: linear-gradient(135deg, #22C55E, #86EFAC);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 12px; line-height: 1.1;
}
.hero-sub {
    font-size: 1.2rem; color: #9CA3AF;
    margin-bottom: 40px; font-weight: 400;
}
.hero-pills {
    display: flex; justify-content: center;
    gap: 10px; flex-wrap: wrap; margin-bottom: 48px;
}
.hero-pill {
    background: rgba(34,197,94,0.08);
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 20px; padding: 5px 14px;
    font-size: 0.85rem; color: #86EFAC; font-weight: 500;
    transition: box-shadow 0.2s ease;
}
.hero-pill:hover { box-shadow: 0 0 10px rgba(34,197,94,0.3); }

/* ── Metrics ── */
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important; font-weight: 700 !important;
    color: #F9FAFB !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important; color: #6B7280 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.82rem !important; }

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: #111827 !important;
    border: 1px solid #1F2937 !important;
    border-radius: 10px !important;
    transition: border-color 0.2s ease;
}
[data-testid="stExpander"]:hover { border-color: #374151 !important; }
[data-testid="stExpander"] summary { color: #E5E7EB !important; }

/* ── Alerts ── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: 1px solid #1F2937 !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    background: #111827 !important;
    border-radius: 10px !important;
}
[data-testid="stDataFrame"] * { color: #E5E7EB !important; }

/* ── Divider ── */
hr { border-color: #1F2937 !important; margin: 20px 0 !important; }

/* ── Sidebar nav ── */
[data-testid="stSidebarNav"] { display: none; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0B0F14; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4B5563; }

/* ── Spacing ── */
[data-testid="stVerticalBlock"] > div { margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────
def card(content_fn, accent=False):
    cls = "pis-card-accent" if accent else "pis-card"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    content_fn()
    st.markdown('</div>', unsafe_allow_html=True)


def section_title(text: str):
    st.markdown(f'<p class="section-title">{text}</p>', unsafe_allow_html=True)


def render_radar_chart(features: dict, student_name: str, cgpa: float = 0.0):
    MAX_PROBLEMS = 200; MAX_DIFFICULTY = 3.0; MAX_CONSISTENCY = 1.0
    MAX_COMMIT_FREQ = 0.8; MAX_CGPA = 10.0

    raw_problems    = features.get("total_problems", 0)
    raw_difficulty  = features.get("avg_difficulty", 0)
    raw_consistency = features.get("consistency_score", 0)
    raw_commit_freq = features.get("commit_frequency", 0)
    raw_cgpa        = cgpa

    values = [
        min(raw_problems    / MAX_PROBLEMS,    1.0),
        min(raw_difficulty  / MAX_DIFFICULTY,  1.0),
        min(raw_consistency / MAX_CONSISTENCY, 1.0),
        min(raw_commit_freq / MAX_COMMIT_FREQ, 1.0),
        min(raw_cgpa        / MAX_CGPA,        1.0),
    ]
    labels = ["DSA Volume", "Problem Depth", "Consistency", "GitHub Activity", "CGPA"]
    values_closed = values + [values[0]]
    labels_closed = labels + [labels[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed, theta=labels_closed, fill="toself",
        fillcolor="rgba(34,197,94,0.15)", line=dict(color="#22C55E", width=2.5),
        name=student_name,
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0,1],
                tickvals=[0.25,0.5,0.75,1.0], ticktext=["25%","50%","75%","100%"],
                gridcolor="rgba(255,255,255,0.06)", tickfont=dict(size=10, color="#6B7280"),
                linecolor="rgba(255,255,255,0.06)"),
            angularaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickfont=dict(size=11, color="#9CA3AF"),
                linecolor="rgba(255,255,255,0.06)"),
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=False, margin=dict(l=30,r=30,t=20,b=20), height=300,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Problems: **{raw_problems}** · Difficulty: **{raw_difficulty:.2f}/3** · "
        f"Consistency: **{raw_consistency:.0%}** · Commits/day: **{raw_commit_freq:.3f}**"
    )


def render_insight(result: dict, show_pipeline_steps: bool = False):
    """Used by Onboard page after pipeline run."""
    score    = result.get("readiness_score") or 0
    category = result.get("category", "Unknown")
    trend    = result.get("score_trend")
    delta    = result.get("score_delta_7d")
    stale    = result.get("features_stale", False)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        delta_str = f" ({delta:+.1f} vs 7d ago)" if delta is not None else ""
        st.metric("Readiness Score", f"{score:.1f}/100", delta=f"{trend}{delta_str}" if trend else None)
    with col2:
        badge = "🟢" if category == "Ready" else "🟡" if category == "Near Ready" else "🔴"
        st.metric("Category", f"{badge} {category}")
    with col3:
        top = result.get("top_priority", "")
        if top and top != "No critical gaps detected.":
            st.warning(f"**Top Priority:** {top}")
        else:
            st.success("No critical gaps detected — student is well-prepared!")

    # ── Company tier ───────────────────────────────────────────────────
    company_tier = result.get("company_tier")
    if company_tier:
        with st.container(border=True):
            tier_col1, tier_col2 = st.columns([2, 3])
            with tier_col1:
                st.markdown("**🏢 Target Companies**")
                st.markdown(f"**{company_tier['tier']}**")
                st.caption(company_tier["focus"])
            with tier_col2:
                st.markdown("**Examples:**")
                st.markdown("  ".join(f"`{c}`" for c in company_tier["examples"]))

    if stale:
        st.warning(f"⚠️ Features were computed {result.get('features_age_hours',0):.0f}h ago.")

    composites = result.get("composite_insights", [])
    if composites:
        st.subheader("Pattern Insights")
        for c in composites:
            with st.expander(f"🔍 {c['pattern'].replace('_',' ').title()}"):
                st.write(c["message"])
                st.info(f"**Action:** {c['action']}")

    strengths = result.get("strengths", [])
    if strengths:
        st.subheader("Strengths")
        cols = st.columns(min(len(strengths), 3))
        for i, s in enumerate(strengths):
            with cols[i % 3]:
                st.success(s["message"])

    recommendations = result.get("recommendations", [])
    if recommendations:
        st.subheader("Recommendations")
        for rec in recommendations:
            tier_icon = "🔴" if rec["tier"] == "critical" else "🟡" if rec["tier"] == "important" else "🔵"
            with st.expander(f"{tier_icon} #{rec['priority']} [{rec['tier'].upper()}] {rec['area'].replace('_',' ').title()}"):
                st.write(rec["action"])
                st.caption(rec["why_it_matters"])

    if show_pipeline_steps:
        steps = result.get("pipeline_steps", [])
        if steps:
            with st.expander("Pipeline execution details"):
                for step in steps:
                    icon   = "✅" if step["status"] == "success" else "❌"
                    source = f" ({step.get('data_source','')})" if step.get("data_source") else ""
                    err    = f" — {step['error']}" if step.get("error") else ""
                    st.text(f"{icon} {step['step']}{source} — {step['duration_ms']}ms{err}")
                st.caption(f"Total: {result.get('total_duration_ms',0)}ms  |  ran_at: {result.get('ran_at','')}")


@st.cache_data(ttl=30)
def _cached_health():
    return health_check()


# ── Session state ─────────────────────────────────────────────────────
if "entered" not in st.session_state:
    st.session_state.entered = False

# ═══════════════════════════════════════════════════════════════════════
# LANDING PAGE
# ═══════════════════════════════════════════════════════════════════════
if not st.session_state.entered:
    st.markdown("""
    <div class="hero-wrap">
        <div class="hero-title">Placement Intelligence<br>System</div>
        <div class="hero-sub">Analyze. Predict. Dominate your placements.</div>
        <div class="hero-pills">
            <span class="hero-pill">🧠 ML-Powered Insights</span>
            <span class="hero-pill">📊 SQL Feature Engineering</span>
            <span class="hero-pill">🐙 Real GitHub Data</span>
            <span class="hero-pill">💻 LeetCode Integration</span>
            <span class="hero-pill">🎯 Placement Readiness Score</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([2, 1, 2])
    with col_c:
        if st.button("Enter Dashboard →", type="primary", use_container_width=True):
            st.session_state.entered = True
            st.rerun()
    st.stop()

# ── Sidebar (shown only after entering) ──────────────────────────────
st.sidebar.markdown("## 🎯 PIS")
st.sidebar.markdown("Placement Intelligence System")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Onboard Student", "Student Dashboard", "Leaderboard"],
    index=0,
)

with st.sidebar:
    st.divider()
    try:
        health = _cached_health()
        st.success(f"API Online v{health.get('version','?')}")
    except Exception:
        st.error("API Offline — start FastAPI server")


# ═══════════════════════════════════════════════════════════════════════
# PAGE 1: ONBOARD A STUDENT
# ═══════════════════════════════════════════════════════════════════════
if page == "Onboard Student":
    st.markdown('<h2 style="color:#F9FAFB;margin-bottom:4px">Onboard a New Student</h2>', unsafe_allow_html=True)
    st.markdown('<p style="color:#9CA3AF;margin-bottom:24px">Add platform usernames for real data. Leave blank for synthetic.</p>', unsafe_allow_html=True)

    st.markdown('<div class="pis-card">', unsafe_allow_html=True)
    with st.form("student_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name   = st.text_input("Full Name *", placeholder="Aryan Mehta")
            email  = st.text_input("Email *", placeholder="aryan@example.com")
            branch = st.selectbox("Branch *", ["CSE", "IT", "ECE", "MECH", "EEE", "OTHER"])
        with col2:
            cgpa              = st.slider("CGPA *", 0.0, 10.0, 7.5, step=0.1)
            github_username   = st.text_input("GitHub Username", placeholder="e.g. octocat (optional)")
            leetcode_username = st.text_input("LeetCode Username", placeholder="e.g. neal_wu (optional)")
        submitted = st.form_submit_button("🚀 Create Student & Run Analysis", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        if not name or not email:
            st.error("Name and email are required.")
        else:
            result = None
            with st.status("Creating student profile...", expanded=True) as status:
                try:
                    payload = {
                        "name": name, "email": email, "cgpa": cgpa, "branch": branch,
                        "github_username": github_username or None,
                        "leetcode_username": leetcode_username or None,
                    }
                    student    = create_student(payload)
                    student_id = student["id"]
                    st.write(f"✅ Student created (ID: {student_id})")
                    status.update(label="Running placement analysis pipeline...")
                    st.write("⏳ Ingesting data, computing features, running ML...")
                    result = run_pipeline(student_id, force_refresh=True)
                    status.update(label="Analysis complete!", state="complete")
                except req_lib.exceptions.HTTPError as e:
                    if e.response.status_code == 409:
                        st.error(f"A student with email '{email}' already exists.")
                    elif e.response.status_code == 422:
                        st.error(f"Validation error: {e.response.json().get('detail', str(e))}")
                    else:
                        st.error(f"API error: {e}")
                    result = None
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
                    result = None

            if result:
                st.divider()
                render_insight(result, show_pipeline_steps=True)


# ═══════════════════════════════════════════════════════════════════════
# PAGE 2: STUDENT DASHBOARD
# ═══════════════════════════════════════════════════════════════════════
elif page == "Student Dashboard":

    try:
        students = get_students()
    except Exception as e:
        st.error(f"Cannot load students: {e}")
        st.stop()

    if not students:
        st.info("No students yet. Use 'Onboard Student' to add one.")
        st.stop()

    # ── Student selector ───────────────────────────────────────────────
    student_options = {
        f"{s['name']} ({s['branch']}) — {s.get('category','No prediction')}": s["id"]
        for s in students
    }
    selected_label   = st.selectbox("Select Student", list(student_options.keys()))
    selected_id      = student_options[selected_label]
    selected_student = next((s for s in students if s["id"] == selected_id), {})

    # ── Action buttons ─────────────────────────────────────────────────
    col_run, col_force, col_spacer = st.columns([1, 1, 4])
    with col_run:
        if st.button("🔄 Re-run Pipeline"):
            with st.spinner("Running..."):
                try:
                    run_pipeline(selected_id)
                    st.rerun()
                except Exception as e:
                    st.error(f"Pipeline failed: {e}")
    with col_force:
        if st.button("⚡ Force Refresh"):
            with st.spinner("Force-refreshing..."):
                try:
                    run_pipeline(selected_id, force_refresh=True)
                    st.rerun()
                except Exception as e:
                    st.error(f"Force refresh failed: {e}")

    # ── Edit profile ───────────────────────────────────────────────────
    with st.expander("✏️ Edit Username / CGPA"):
        try:
            from api_client import update_student
        except ImportError:
            update_student = None
        edit_col1, edit_col2, edit_col3 = st.columns(3)
        with edit_col1:
            new_github = st.text_input(
                "GitHub Username",
                value=selected_student.get("github_username") or "",
                key="edit_github",
            )
        with edit_col2:
            new_leetcode = st.text_input(
                "LeetCode Username",
                value=selected_student.get("leetcode_username") or "",
                key="edit_leetcode",
            )
        with edit_col3:
            new_cgpa = st.number_input(
                "CGPA", 0.0, 10.0,
                value=float(selected_student.get("cgpa", 7.5)),
                step=0.1, key="edit_cgpa",
            )
        if st.button("Save Changes", key="save_profile") and update_student:
            payload = {}
            if new_github.strip():
                payload["github_username"] = new_github.strip()
            if new_leetcode.strip():
                payload["leetcode_username"] = new_leetcode.strip()
            payload["cgpa"] = new_cgpa
            try:
                update_student(selected_id, payload)
                st.success("Profile updated! Run pipeline to apply changes.")
                st.rerun()
            except Exception as e:
                st.error(f"Update failed: {e}")

    # ── Load data ──────────────────────────────────────────────────────
    try:
        insight = get_insights(selected_id)
    except Exception as e:
        st.warning(f"No insight data yet. Run the pipeline first. ({e})")
        st.stop()

    student_name = insight.get("student_name", selected_student.get("name", ""))
    branch       = selected_student.get("branch", "")
    score        = insight.get("readiness_score") or 0
    category     = insight.get("category", "Unknown")
    trend        = insight.get("score_trend")
    delta        = insight.get("score_delta_7d")
    stale        = insight.get("features_stale", False)
    top          = insight.get("top_priority", "")

    try:
        status_data     = get_student_status(selected_id)
        github_synced   = status_data.get("github_username") is not None
        leetcode_synced = status_data.get("leetcode_username") is not None
        data_badge      = "📡 Real Data" if (github_synced or leetcode_synced) else "🔄 Synthetic"
        stage           = status_data.get("pipeline_stage", "unknown")
        stage_icon      = {"complete":"🟢","features_computed":"🟠","no_data":"🔴"}.get(stage,"⚪")
    except Exception:
        data_badge = ""; stage_icon = "⚪"; stage = "unknown"

    # ── HEADER BANNER ─────────────────────────────────────────────────
    st.markdown(f"""
    <div class="pis-card-accent" style="margin-bottom:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <div>
                <span style="font-size:1.6rem;font-weight:800;color:#F9FAFB">{student_name}</span>
                &nbsp;<span style="background:#1F2937;color:#86EFAC;padding:3px 10px;border-radius:8px;font-size:0.85rem;font-weight:600">{branch}</span>
                &nbsp;<span style="background:rgba(34,197,94,0.1);color:#86EFAC;padding:3px 10px;border-radius:8px;font-size:0.82rem;border:1px solid rgba(34,197,94,0.2)">{data_badge}</span>
            </div>
            <div style="font-size:0.9rem;color:#9CA3AF">{stage_icon} Pipeline: <strong style="color:#E5E7EB">{stage}</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if stale:
        st.warning(f"⚠️ Features are {insight.get('features_age_hours',0):.0f}h old — run pipeline for fresh analysis.")

    # ── HERO SCORE SECTION ─────────────────────────────────────────────
    badge_cls = "badge-ready" if category == "Ready" else "badge-near" if category == "Near Ready" else "badge-needs"
    badge_txt = category
    delta_html = f'<div style="font-size:0.85rem;color:#9CA3AF;margin-top:6px">{trend} &nbsp; {delta:+.1f} pts vs 7d ago</div>' if (trend and delta is not None) else ""

    top_html = ""
    if top and top != "No critical gaps detected.":
        top_html = f'<div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.25);border-radius:10px;padding:12px 16px;font-size:0.92rem;color:#FCD34D"><strong>🎯 Next Move:</strong> {top}</div>'
    else:
        top_html = '<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:10px;padding:12px 16px;font-size:0.92rem;color:#86EFAC">✅ No critical gaps — placement-ready!</div>'

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"""
        <div class="pis-card" style="text-align:center;padding:28px 16px">
            <div class="score-label">Readiness Score</div>
            <div class="score-number">{score:.1f}</div>
            <div class="score-label">/ 100</div>
            {delta_html}
        </div>""", unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""
        <div class="pis-card" style="text-align:center;padding:28px 16px">
            <div class="score-label">Category</div>
            <div style="font-size:2rem;margin:8px 0">{"🟢" if category=="Ready" else "🟡" if category=="Near Ready" else "🔴"}</div>
            <span class="category-badge {badge_cls}">{badge_txt}</span>
        </div>""", unsafe_allow_html=True)
    with sc3:
        st.markdown(f"""
        <div class="pis-card" style="padding:20px">
            <div class="score-label" style="margin-bottom:10px">Your Next Move</div>
            {top_html}
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── RADAR CHART ────────────────────────────────────────────────────
    try:
        features = get_features(selected_id)
        if features:
            st.markdown('<div class="pis-card">', unsafe_allow_html=True)
            section_title("🕸️ Skill Profile")
            render_radar_chart(features, student_name, cgpa=float(selected_student.get("cgpa") or 0))
            st.markdown('</div>', unsafe_allow_html=True)
    except Exception:
        pass

    # ── PATTERN INSIGHTS ───────────────────────────────────────────────
    composites = insight.get("composite_insights", [])
    if composites:
        st.markdown('<div class="pis-card">', unsafe_allow_html=True)
        section_title("🔍 Pattern Insights")
        for c in composites:
            with st.expander(f"🔍 {c['pattern'].replace('_',' ').title()}"):
                st.write(c["message"])
                st.info(f"**Action:** {c['action']}")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── RECOMMENDATIONS ────────────────────────────────────────────────
    recommendations = insight.get("recommendations", [])
    if recommendations:
        st.markdown('<div class="pis-card">', unsafe_allow_html=True)
        section_title("🛠️ What to Fix")
        for rec in recommendations:
            tier      = rec["tier"]
            tier_icon = "🔴" if tier == "critical" else "🟡" if tier == "important" else "🔵"
            cls       = f"rec-block rec-block-{tier}"
            area      = rec["area"].replace("_"," ").title()
            st.markdown(f"""
            <div class="{cls}">
                <div style="font-weight:700;font-size:0.95rem;margin-bottom:4px">
                    {tier_icon} #{rec['priority']} &nbsp;<span style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.06em;opacity:0.7">[{tier}]</span> &nbsp;{area}
                </div>
                <div style="font-size:0.9rem;color:#D1D5DB;margin-bottom:4px">{rec['action']}</div>
                <div style="font-size:0.8rem;color:#6B7280">ℹ️ {rec['why_it_matters']}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── STRENGTHS ──────────────────────────────────────────────────────
    strengths = insight.get("strengths", [])
    if strengths:
        st.markdown('<div class="pis-card">', unsafe_allow_html=True)
        section_title(f"✅ Strengths ({len(strengths)} areas)")
        cols = st.columns(min(len(strengths), 3))
        for i, s in enumerate(strengths):
            with cols[i % 3]:
                st.markdown(f'<div class="strength-chip">✅ {s["message"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── SCORE HISTORY ──────────────────────────────────────────────────
    try:
        history = get_student_history(selected_id)
        st.markdown('<div class="pis-card">', unsafe_allow_html=True)
        section_title("📈 Progress Over Time")
        if history and len(history) > 1:
            hist_df = pd.DataFrame(history)
            hist_df["recorded_at"] = pd.to_datetime(hist_df["recorded_at"])
            hist_df = hist_df.sort_values("recorded_at")
            st.line_chart(hist_df.set_index("recorded_at")["readiness_score"])
        else:
            st.caption("Run the pipeline multiple times over several sessions to build a score history trend.")
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# PAGE 3: LEADERBOARD
# ═══════════════════════════════════════════════════════════════════════
elif page == "Leaderboard":
    st.markdown('<h2 style="color:#F9FAFB;margin-bottom:4px">🏆 Placement Readiness Leaderboard</h2>', unsafe_allow_html=True)
    st.markdown('<p style="color:#9CA3AF;margin-bottom:20px">Ranked by ML-predicted readiness score.</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_branch = st.selectbox("Filter by Branch", ["All Branches","CSE","IT","ECE","MECH","EEE"])
    with col2:
        limit = st.slider("Show top N", 5, 50, 20)

    branch_param = None if selected_branch == "All Branches" else selected_branch

    try:
        ranking = get_ranking(branch=branch_param, limit=limit)
    except Exception as e:
        st.error(f"Cannot load ranking: {e}")
        st.stop()

    if not ranking:
        st.info("No ranked students yet. Run the pipeline for some students first.")
        st.stop()

    # ── Summary cards ──────────────────────────────────────────────────
    avg_score = sum(r["composite_score"] for r in ranking) / len(ranking)
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f'<div class="pis-card" style="text-align:center"><div class="score-label">Students Ranked</div><div style="font-size:2rem;font-weight:800;color:#22C55E">{len(ranking)}</div></div>', unsafe_allow_html=True)
    with s2:
        st.markdown(f'<div class="pis-card" style="text-align:center"><div class="score-label">Average Score</div><div style="font-size:2rem;font-weight:800;color:#22C55E">{avg_score:.1f}</div></div>', unsafe_allow_html=True)
    with s3:
        top_name = ranking[0]["name"]
        st.markdown(f'<div class="pis-card-accent" style="text-align:center"><div class="score-label">Top Performer</div><div style="font-size:1.2rem;font-weight:800;color:#86EFAC">🥇 {top_name}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Table ──────────────────────────────────────────────────────────
    df = pd.DataFrame(ranking)
    df = df.rename(columns={
        "global_rank":"Rank","name":"Name","branch":"Branch","cgpa":"CGPA",
        "total_problems":"Problems","composite_score":"Score",
        "percentile":"Percentile %","branch_rank":"Branch Rank",
    })

    def cat_emoji(cat):
        if not cat: return "⚪"
        return "🟢" if cat == "Ready" else "🟡" if cat == "Near Ready" else "🔴"

    if "category" in df.columns:
        df["Status"] = df["category"].apply(cat_emoji)

    display_cols = [c for c in ["Rank","Status","Name","Branch","CGPA","Problems","Score","Percentile %"] if c in df.columns]

    def highlight_top(row):
        if row["Rank"] == 1:
            return ["background-color:rgba(34,197,94,0.12)"] * len(row)
        if row["Rank"] == 2:
            return ["background-color:rgba(255,255,255,0.04)"] * len(row)
        if row["Rank"] == 3:
            return ["background-color:rgba(255,255,255,0.02)"] * len(row)
        return [""] * len(row)

    st.markdown('<div class="pis-card">', unsafe_allow_html=True)
    st.dataframe(
        df[display_cols].style.apply(highlight_top, axis=1),
        use_container_width=True, hide_index=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)
