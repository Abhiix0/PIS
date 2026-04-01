import streamlit as st
import pandas as pd
import requests as req_lib
from api_client import  (
    health_check, get_students, create_student, run_pipeline,
    get_insights, get_ranking, get_student_status, get_features,
    get_student_history,
)

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Placement Intelligence System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Shared rendering helper ───────────────────────────────────────────
def render_insight(result: dict, show_pipeline_steps: bool = False):
    """Render a full insight result dict — used by both Onboard and Dashboard pages."""
    score    = result.get("readiness_score") or 0
    category = result.get("category", "Unknown")
    trend    = result.get("score_trend")
    delta    = result.get("score_delta_7d")
    stale    = result.get("features_stale", False)

    # ── Score row ─────────────────────────────────────────────────────
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

    # ── Stale features warning ────────────────────────────────────────
    if stale:
        age = result.get("features_age_hours", 0)
        st.warning(f"⚠️ Features were computed {age:.0f}h ago — re-run pipeline for fresh data.")

    # ── Composite insights ────────────────────────────────────────────
    composites = result.get("composite_insights", [])
    if composites:
        st.subheader("Pattern Insights")
        for c in composites:
            with st.expander(f"🔍 {c['pattern'].replace('_', ' ').title()}"):
                st.write(c["message"])
                st.info(f"**Action:** {c['action']}")

    # ── Strengths ─────────────────────────────────────────────────────
    strengths = result.get("strengths", [])
    if strengths:
        st.subheader("Strengths")
        cols = st.columns(min(len(strengths), 3))
        for i, s in enumerate(strengths):
            with cols[i % 3]:
                st.success(s["message"])

    # ── Recommendations ───────────────────────────────────────────────
    recommendations = result.get("recommendations", [])
    if recommendations:
        st.subheader("Recommendations")
        for rec in recommendations:
            tier_icon = "🔴" if rec["tier"] == "critical" else "🟡" if rec["tier"] == "important" else "🔵"
            with st.expander(
                f"{tier_icon} #{rec['priority']} [{rec['tier'].upper()}] "
                f"{rec['area'].replace('_', ' ').title()}"
            ):
                st.write(rec["action"])
                st.caption(rec["why_it_matters"])

    # ── Pipeline steps (optional) ─────────────────────────────────────
    if show_pipeline_steps:
        steps = result.get("pipeline_steps", [])
        if steps:
            with st.expander("Pipeline execution details"):
                for step in steps:
                    icon   = "✅" if step["status"] == "success" else "❌"
                    source = f" ({step.get('data_source', '')})" if step.get("data_source") else ""
                    err    = f" — {step['error']}" if step.get("error") else ""
                    st.text(f"{icon} {step['step']}{source} — {step['duration_ms']}ms{err}")
                st.caption(f"Total: {result.get('total_duration_ms', 0)}ms  |  ran_at: {result.get('ran_at', '')}")


# ── Sidebar navigation ────────────────────────────────────────────────
st.sidebar.title("🎯 PIS")
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
        health = health_check()
        st.success(f"API Online v{health.get('version', '?')}")
    except Exception:
        st.error("API Offline — start FastAPI server")


# ═══════════════════════════════════════════════════════════════════════
# PAGE 1: ONBOARD A STUDENT
# ═══════════════════════════════════════════════════════════════════════
if page == "Onboard Student":
    st.title("Onboard a New Student")
    st.markdown(
        "Fill in the student details. Add platform usernames to use "
        "**real data** from GitHub and LeetCode. Leave blank for synthetic data."
    )

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

        submitted = st.form_submit_button(
            "Create Student & Run Analysis", type="primary", use_container_width=True
        )

    if submitted:
        if not name or not email:
            st.error("Name and email are required.")
        else:
            result = None
            with st.status("Creating student profile...", expanded=True) as status:
                try:
                    payload = {
                        "name":              name,
                        "email":             email,
                        "cgpa":              cgpa,
                        "branch":            branch,
                        "github_username":   github_username or None,
                        "leetcode_username": leetcode_username or None,
                    }
                    student    = create_student(payload)
                    student_id = student["id"]
                    st.write(f"✅ Student created (ID: {student_id})")

                    status.update(label="Running placement analysis pipeline...")
                    st.write("⏳ Ingesting data, computing features, running ML...")
                    # force_refresh=True on new students — no cache to respect
                    result = run_pipeline(student_id, force_refresh=True)
                    status.update(label="Analysis complete!", state="complete")

                except req_lib.exceptions.HTTPError as e:
                    if e.response.status_code == 409:
                        st.error(f"A student with email '{email}' already exists.")
                    elif e.response.status_code == 422:
                        detail = e.response.json().get("detail", str(e))
                        st.error(f"Validation error: {detail}")
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
    st.title("Student Dashboard")

    try:
        students = get_students()
    except Exception as e:
        st.error(f"Cannot load students: {e}")
        st.stop()

    if not students:
        st.info("No students yet. Use 'Onboard Student' to add one.")
        st.stop()

    student_options = {
        f"{s['name']} ({s['branch']}) — {s.get('category', 'No prediction')}": s["id"]
        for s in students
    }
    selected_label = st.selectbox("Select Student", list(student_options.keys()))
    selected_id    = student_options[selected_label]

    # ── Action buttons ────────────────────────────────────────────────
    col_run, col_force, _ = st.columns([1, 1, 3])
    with col_run:
        if st.button("🔄 Re-run Pipeline"):
            with st.spinner("Running pipeline..."):
                try:
                    run_pipeline(selected_id)
                    st.success("Done! Refreshing...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Pipeline failed: {e}")
    with col_force:
        if st.button("⚡ Force Refresh"):
            with st.spinner("Force-refreshing (bypassing cache)..."):
                try:
                    run_pipeline(selected_id, force_refresh=True)
                    st.success("Force refresh complete! Refreshing...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Force refresh failed: {e}")

    st.divider()

    # ── Load insight data ─────────────────────────────────────────────
    try:
        insight = get_insights(selected_id)
    except Exception as e:
        st.warning(f"No insight data yet. Run the pipeline first. ({e})")
        st.stop()

    # ── Pipeline stage badge ──────────────────────────────────────────
    try:
        status_data = get_student_status(selected_id)
        stage = status_data.get("pipeline_stage", "unknown")
        stage_color = {"complete": "🟢", "predicted": "🟡", "features_computed": "🟠", "no_data": "🔴"}
        st.caption(f"{stage_color.get(stage, '⚪')} Pipeline stage: **{stage}**")
    except Exception:
        pass

    # ── Feature bar chart ─────────────────────────────────────────────
    try:
        features = get_features(selected_id)
        if features:
            st.subheader("Feature Profile")
            total_p = features.get("total_problems", 0)
            chart_data = pd.DataFrame({
                "Feature": ["Total Problems (÷10)", "Avg Difficulty (×33)", "Consistency %", "Commit Freq %"],
                "Value": [
                    total_p / 10,
                    features.get("avg_difficulty", 0) * 33.3,
                    features.get("consistency_score", 0) * 100,
                    min(features.get("commit_frequency", 0) * 100, 100),
                ],
            }).set_index("Feature")
            st.bar_chart(chart_data)
            st.caption(f"Raw total_problems: **{total_p}**  |  avg_difficulty: **{features.get('avg_difficulty', 0):.2f}**  |  consistency: **{features.get('consistency_score', 0):.3f}**")
    except Exception:
        pass

    # ── Full insight render ───────────────────────────────────────────
    render_insight(insight)

    # ── Score history chart ───────────────────────────────────────────
    try:
        history = get_student_history(selected_id)
        if history and len(history) > 1:
            st.subheader("Score History")
            hist_df = pd.DataFrame(history)
            hist_df["recorded_at"] = pd.to_datetime(hist_df["recorded_at"])
            hist_df = hist_df.sort_values("recorded_at")
            st.line_chart(hist_df.set_index("recorded_at")["readiness_score"])
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# PAGE 3: LEADERBOARD
# ═══════════════════════════════════════════════════════════════════════
elif page == "Leaderboard":
    st.title("Placement Readiness Leaderboard")

    col1, col2 = st.columns([2, 1])
    with col1:
        branch_options  = ["All Branches", "CSE", "IT", "ECE", "MECH", "EEE"]
        selected_branch = st.selectbox("Filter by Branch", branch_options)
    with col2:
        limit = st.slider("Show top N students", 5, 50, 20)

    branch_param = None if selected_branch == "All Branches" else selected_branch

    try:
        ranking = get_ranking(branch=branch_param, limit=limit)
    except Exception as e:
        st.error(f"Cannot load ranking: {e}")
        st.stop()

    if not ranking:
        st.info("No ranked students yet. Run the pipeline for some students first.")
        st.stop()

    df = pd.DataFrame(ranking)
    df = df.rename(columns={
        "global_rank":     "Rank",
        "name":            "Name",
        "branch":          "Branch",
        "cgpa":            "CGPA",
        "total_problems":  "Problems",
        "composite_score": "Score",
        "percentile":      "Percentile %",
        "branch_rank":     "Branch Rank",
    })
    display_cols = [c for c in ["Rank", "Name", "Branch", "CGPA", "Problems", "Score", "Percentile %"] if c in df.columns]

    def highlight_top(row):
        if row["Rank"] == 1:
            return ["background-color: #E1F5EE"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df[display_cols].style.apply(highlight_top, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Students Ranked", len(ranking))
    with col2:
        avg_score = sum(r["composite_score"] for r in ranking) / len(ranking)
        st.metric("Average Score", f"{avg_score:.1f}")
    with col3:
        st.metric("Top Student", ranking[0]["name"])
