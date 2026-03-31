import streamlit as st
import pandas as pd
import requests as req_lib
from dashboard.api_client import (
    health_check, get_students, create_student, run_pipeline,
    get_insights, get_ranking, get_student_status, get_features,
)

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Placement Intelligence System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar navigation ────────────────────────────────────────────────
st.sidebar.title("🎯 PIS")
st.sidebar.markdown("Placement Intelligence System")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Onboard Student", "Student Dashboard", "Leaderboard"],
    index=0,
)

# ── API health check in sidebar ───────────────────────────────────────
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
                    result = run_pipeline(student_id)
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
                score    = result.get("readiness_score") or 0
                category = result.get("category", "Unknown")

                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    st.metric("Readiness Score", f"{score:.1f}/100")
                with col2:
                    badge = "🟢" if category == "Ready" else "🟡" if category == "Near Ready" else "🔴"
                    st.metric("Category", f"{badge} {category}")
                with col3:
                    top = result.get("top_priority", "")
                    if top and top != "No critical gaps detected.":
                        st.info(f"**Top Priority:** {top}")
                    else:
                        st.success("No critical gaps detected — student is well-prepared!")

                strengths = result.get("strengths", [])
                if strengths:
                    st.subheader("Strengths")
                    for s in strengths:
                        st.markdown(f"✅ {s['message']}")

                recommendations = result.get("recommendations", [])
                if recommendations:
                    st.subheader("Recommendations")
                    for rec in recommendations:
                        tier_icon = "🔴" if rec["tier"] == "critical" else "🟡" if rec["tier"] == "important" else "🔵"
                        with st.expander(f"{tier_icon} {rec['priority']}. {rec['area'].replace('_', ' ').title()}"):
                            st.write(rec["action"])
                            st.caption(rec["why_it_matters"])

                with st.expander("Pipeline execution details"):
                    steps = result.get("pipeline_steps", [])
                    for step in steps:
                        icon   = "✅" if step["status"] == "success" else "❌"
                        source = f" ({step.get('data_source', '')})" if step.get("data_source") else ""
                        st.text(f"{icon} {step['step']}{source} — {step['duration_ms']}ms")
                    st.caption(f"Total duration: {result.get('total_duration_ms', 0)}ms")


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

    col_refresh, _ = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Re-run Pipeline"):
            with st.spinner("Running pipeline..."):
                try:
                    run_pipeline(selected_id)
                    st.success("Pipeline complete! Refreshing...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Pipeline failed: {e}")

    st.divider()

    try:
        insight = get_insights(selected_id)
    except Exception as e:
        st.warning(f"No insight data yet. Run the pipeline first. ({e})")
        st.stop()

    score    = insight.get("readiness_score") or 0
    category = insight.get("category", "Unknown")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Readiness Score", f"{score:.1f} / 100")
    with col2:
        icon = "🟢" if category == "Ready" else "🟡" if category == "Near Ready" else "🔴"
        st.metric("Category", f"{icon} {category}")
    with col3:
        try:
            status_data = get_student_status(selected_id)
            st.metric("Pipeline Stage", status_data.get("pipeline_stage", "unknown"))
        except Exception:
            pass

    st.divider()

    try:
        features = get_features(selected_id)
        if features:
            st.subheader("Feature Profile")
            chart_data = pd.DataFrame({
                "Feature": ["Total Problems", "Avg Difficulty", "Consistency", "Commit Frequency"],
                "Value": [
                    features.get("total_problems", 0),
                    features.get("avg_difficulty", 0) * 33.3,
                    features.get("consistency_score", 0) * 100,
                    min(features.get("commit_frequency", 0) * 100, 100),
                ],
            }).set_index("Feature")
            st.bar_chart(chart_data)
    except Exception:
        pass

    strengths = insight.get("strengths", [])
    if strengths:
        st.subheader("Strengths")
        cols = st.columns(min(len(strengths), 3))
        for i, s in enumerate(strengths):
            with cols[i % 3]:
                st.success(s["message"])

    recommendations = insight.get("recommendations", [])
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
    elif not recommendations:
        st.success("🎉 No gaps detected — this student is placement-ready!")


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
    display_cols = ["Rank", "Name", "Branch", "CGPA", "Problems", "Score", "Percentile %"]

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
        top = ranking[0]
        st.metric("Top Student", top["name"])
