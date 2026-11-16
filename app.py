from database import (
    DB_PATH,
    ALL_CHANNELS,
    initialize_database,
    get_daily_total,
    get_logging_streak,
    get_enabled_channels,
    set_setting,
    load_activities,
    save_activity,
    update_activity,
    delete_activity,
    save_planned_activity,
    save_recurring_planned_activities,
    load_planned_activities,
    update_planned_activity,
    update_planned_activity_status,
    delete_planned_activity,
    load_reminder_history,
    mark_overdue_activities_failed,
    load_goal_hours,
    save_goal_hours,
    reset_goal_hours,
)
from suggestions import (
    WEEKLY_TARGETS,
    merge_goals,
    validate_goals,
    weekly_balance,
    planned_windows_today,
    pending_planned_hours,
    remaining_today,
    suggest_activities,
)
from ai_coach import (
    parse_natural_language_activities,
    generate_weekly_coach_insight,
)
import notifications

import os
import sqlite3
import time as time_module
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

# Load Streamlit Cloud Secrets into environment variables automatically
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _v.strip():
            os.environ[_k] = _v.strip()
except Exception:
    pass

# =========================================================
# 1. CONFIGURATION AND DATABASE PATH
# =========================================================

ACTIVITIES = [
    "Work",
    "Study",
    "Sleep",
    "Exercise",
    "Family & Friends",
    "Personal Care",
    "Commute",
    "Meals",
    "Leisure",
    "Other",
]

ENERGY_LABELS = {
    1: "1 - 😫 Drained",
    2: "2 - 😕 Low",
    3: "3 - 😐 Neutral",
    4: "4 - 🙂 Good",
    5: "5 - 🤩 Energized",
}

st.set_page_config(
    page_title="Work-Life Balance Manager",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# 2. PROFESSIONAL RESPONSIVE DESIGN AND ANIMATIONS
# =========================================================

try:
    st.markdown(
        f"<style>{Path(__file__).with_name('styles.css').read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )
except OSError:
    pass

CHART_COLORS = [
    "#2DD4BF", "#818CF8", "#F59E0B", "#F472B6", "#34D399",
    "#60A5FA", "#FB7185", "#A78BFA", "#FBBF24", "#22D3EE",
]
px.defaults.color_discrete_sequence = CHART_COLORS
_streamlit_plotly_chart = st.plotly_chart


def _styled_plotly_chart(figure, *args, **kwargs):
    figure.update_layout(
        colorway=CHART_COLORS,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    kwargs.setdefault("theme", None)
    return _streamlit_plotly_chart(figure, *args, **kwargs)


st.plotly_chart = _styled_plotly_chart


# =========================================================
# 3. INITIALIZE DATABASE
# =========================================================

try:
    initialize_database()
except sqlite3.Error as error:
    st.error(f"Database initialization failed: {error}")
    st.stop()


# =========================================================
# 4. APPLICATION HEADER
# =========================================================

streak_days = get_logging_streak()
header_col, streak_col = st.columns([4, 1])

with header_col:
    st.title("⚖️ Work-Life Balance Manager")
    st.markdown("#### Your time, organized. Your routine, understood.")
    st.caption(
        "Track daily activities, monitor time allocation & energy levels, "
        "and explore your work-life patterns."
    )

with streak_col:
    st.metric("🔥 Logging Streak", f"{streak_days} day{'s' if streak_days != 1 else ''}")

with st.expander("⚙️ Application Info & Notification Settings"):
    info_tab, notif_tab = st.tabs(["ℹ️ System Info", "🔔 Notification Channels & Tests"])
    with info_tab:
        st.write("Application: Work-Life Balance Manager (v3.1)")
        st.write("Database: SQLite | Charts: Plotly | AI: Gemini 2.5 Flash")
        st.code(str(DB_PATH))
    with notif_tab:
        current_channels = list(get_enabled_channels())
        selected_channels = st.multiselect(
            "Active Reminder Channels",
            options=list(ALL_CHANNELS),
            default=current_channels,
            help="Reminders will be created only for these channels.",
        )
        if st.button("💾 Save Channel Preferences"):
            set_setting("enabled_channels", ",".join(selected_channels))
            st.success(f"Saved active channels: {', '.join(selected_channels) or 'None'}")
            st.rerun()

        t_col1, t_col2 = st.columns(2)
        with t_col1:
            if st.button("📨 Send Test Telegram", width="stretch"):
                ok, msg = notifications.send_telegram("Test reminder from Work-Life Balance Manager v3.1!")
                (st.success if ok else st.error)(msg)
        with t_col2:
            if st.button("📧 Send Test Email", width="stretch"):
                to_email = os.getenv("NOTIFICATION_TO_EMAIL", "")
                ok, msg = notifications.send_email(
                    to_email,
                    "WLB Manager Test Email",
                    "Your email notifications are working properly!",
                )
                (st.success if ok else st.error)(msg)


# =========================================================
# 5. ADD ACTIVITY FORM, PRESETS & AI QUICK-LOG (SIDEBAR)
# =========================================================

st.sidebar.title("➕ Add an activity")

sidebar_tab_manual, sidebar_tab_ai, sidebar_tab_presets = st.sidebar.tabs(
    ["📝 Manual", "✨ AI Log", "⚡ Presets"]
)

with sidebar_tab_manual:
    with st.form("add_activity_form", clear_on_submit=True):
        activity_date = st.date_input(
            "Activity date",
            value=date.today(),
        )

        activity_type = st.selectbox(
            "Activity",
            ACTIVITIES,
        )

        duration = st.number_input(
            "Duration (hours)",
            min_value=0.25,
            max_value=24.0,
            value=1.0,
            step=0.25,
        )

        energy_level = st.select_slider(
            "Energy / Mood",
            options=[1, 2, 3, 4, 5],
            value=3,
            format_func=lambda x: ENERGY_LABELS[x],
        )

        notes = st.text_input(
            "Notes (optional)",
            max_chars=200,
        )

        save_clicked = st.form_submit_button(
            "💾 Save activity",
            width="stretch",
        )

    if save_clicked:
        try:
            saved, message = save_activity(
                activity_date,
                activity_type,
                float(duration),
                notes,
                energy_level=energy_level,
            )

            if saved:
                st.sidebar.success(message)
                st.rerun()
            else:
                st.sidebar.error(message)

        except (sqlite3.Error, ValueError) as error:
            st.sidebar.error(f"Could not save activity: {error}")

with sidebar_tab_ai:
    st.caption("Type naturally in English, Marathi, or Hindi (e.g., 'Aaj 2 taas SQL practice ani 1 taas gym keli').")
    quick_text = st.text_area(
        "What did you do?",
        placeholder="e.g., Worked 4 hours on dashboard, 1 hour gym feeling energized",
        height=95,
        key="ai_quick_log_input",
    )
    if st.button("🪄 Parse & Save with AI", width="stretch"):
        if not quick_text.strip():
            st.warning("Enter a sentence first.")
        else:
            with st.spinner("Parsing activities..."):
                parsed_items, ai_err = parse_natural_language_activities(quick_text, date.today())
            if ai_err:
                st.error(ai_err)
            elif not parsed_items:
                st.warning("Could not detect any activities in that text.")
            else:
                saved_any = False
                for item in parsed_items:
                    ok, msg = save_activity(
                        date.fromisoformat(item["activity_date"]),
                        item["activity_type"],
                        item["duration_hours"],
                        item["notes"],
                        energy_level=item["energy_level"],
                    )
                    if ok:
                        st.success(f"Saved: {item['activity_type']} ({item['duration_hours']}h)")
                        saved_any = True
                    else:
                        st.error(f"{item['activity_type']}: {msg}")
                if saved_any:
                    time_module.sleep(0.6)
                    st.rerun()

with sidebar_tab_presets:
    st.caption("One-click log common daily blocks for today:")
    presets = [
        ("😴 Full Sleep (7.5h)", "Sleep", 7.5, "Restful night sleep", 4),
        ("💼 Work Shift (8.0h)", "Work", 8.0, "Standard workday", 3),
        ("🏋️ Workout (1.0h)", "Exercise", 1.0, "Daily fitness session", 5),
        ("📚 Deep Study (2.0h)", "Study", 2.0, "Focused learning block", 4),
        ("🍽️ Daily Meals (1.5h)", "Meals", 1.5, "Breakfast, lunch & dinner", 3),
    ]
    for label, p_cat, p_hrs, p_note, p_energy in presets:
        if st.button(label, key=f"preset_{p_cat}_{p_hrs}", width="stretch"):
            ok, msg = save_activity(date.today(), p_cat, p_hrs, p_note, energy_level=p_energy)
            if ok:
                st.sidebar.success(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)


# =========================================================
# 5B. LIVE POMODORO / FOCUS TIMER (SIDEBAR)
# =========================================================

st.sidebar.divider()
st.sidebar.subheader("⏱️ Live Focus Timer")

st.session_state.setdefault("pomo_running", False)
st.session_state.setdefault("pomo_end_ts", None)
st.session_state.setdefault("pomo_minutes", 25)
st.session_state.setdefault("pomo_activity", "Work")

pomo_act = st.sidebar.selectbox("Focus category", ACTIVITIES, key="pomo_cat_select")
pomo_mins = st.sidebar.number_input("Minutes", min_value=5, max_value=180, value=25, step=5, key="pomo_min_input")

pomo_c1, pomo_c2 = st.sidebar.columns(2)
if pomo_c1.button("▶️ Start", width="stretch", disabled=st.session_state["pomo_running"]):
    st.session_state["pomo_running"] = True
    st.session_state["pomo_minutes"] = pomo_mins
    st.session_state["pomo_activity"] = pomo_act
    st.session_state["pomo_end_ts"] = datetime.now().timestamp() + (pomo_mins * 60)
    st.rerun()

if pomo_c2.button("⏹️ Stop", width="stretch", disabled=not st.session_state["pomo_running"]):
    st.session_state["pomo_running"] = False
    st.session_state["pomo_end_ts"] = None
    st.rerun()

if st.session_state["pomo_running"] and st.session_state["pomo_end_ts"]:
    remaining_sec = int(st.session_state["pomo_end_ts"] - datetime.now().timestamp())
    if remaining_sec > 0:
        mins_left, secs_left = divmod(remaining_sec, 60)
        st.sidebar.info(f"⏳ **{st.session_state['pomo_activity']}**: {mins_left:02d}:{secs_left:02d} left")
        if st.sidebar.button("🔄 Refresh timer", width="stretch"):
            st.rerun()
    else:
        logged_hrs = max(0.25, round(st.session_state["pomo_minutes"] / 60.0, 2))
        ok, msg = save_activity(
            date.today(),
            st.session_state["pomo_activity"],
            logged_hrs,
            f"Completed {st.session_state['pomo_minutes']}m Focus Timer session",
            energy_level=4,
        )
        st.session_state["pomo_running"] = False
        st.session_state["pomo_end_ts"] = None
        if ok:
            st.sidebar.success(f"🎉 Focus complete! Logged {logged_hrs}h to {st.session_state['pomo_activity']}.")
        else:
            st.sidebar.warning(msg)


# =========================================================
# 6. DATE FILTERS
# =========================================================

st.header("📊 Dashboard Overview")

today = date.today()

filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    start_date = st.date_input(
        "From",
        value=today - timedelta(days=6),
        key="filter_start",
    )

with filter_col2:
    end_date = st.date_input(
        "To",
        value=today,
        key="filter_end",
    )

if start_date > end_date:
    st.error("The start date cannot be later than the end date.")
    st.stop()

try:
    df = load_activities(start_date, end_date)
except (sqlite3.Error, pd.errors.DatabaseError) as error:
    st.error(f"Could not load activity records: {error}")
    st.stop()


# =========================================================
# 6B. HIGHLIGHT CARDS (5 cards matching test_panels.py)
# =========================================================

st.session_state.setdefault("panel", "overview")


def _open_panel(panel_name):
    """Button callback: show only this panel below the cards."""
    st.session_state["panel"] = panel_name


total_hours = float(df["duration_hours"].sum()) if not df.empty else 0.0
work_hours = float(df.loc[df["activity_type"] == "Work", "duration_hours"].sum()) if not df.empty else 0.0
sleep_hours = float(df.loc[df["activity_type"] == "Sleep", "duration_hours"].sum()) if not df.empty else 0.0
active_days = int(df["activity_date"].nunique()) if not df.empty else 0
average_per_day = total_hours / active_days if active_days else 0.0

try:
    card_now = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    card_week = weekly_balance(
        load_activities(card_now.date() - timedelta(days=6), card_now.date()),
        card_now.date(),
        merge_goals(load_goal_hours()),
    )
    card_plans = load_planned_activities(today, today + timedelta(days=30))
    upcoming_plans = int((card_plans["status"] == "Planned").sum()) if not card_plans.empty else 0
except (sqlite3.Error, pd.errors.DatabaseError):
    card_week, upcoming_plans = {"score": None, "label": ""}, 0

highlight_cards = [
    ("overview", "🕒 Overview", f"{total_hours:.1f} h", f"{work_hours:.1f} h work, {sleep_hours:.1f} h sleep"),
    ("analytics", "📈 Analytics", f"{average_per_day:.1f} h", "average per active day"),
    ("records", "🗂️ Records", f"{len(df)}", "activity records"),
    (
        "balance",
        "🧠 Balance",
        "n/a" if card_week["score"] is None else f"{card_week['score']} / 100",
        card_week["label"],
    ),
    ("planner", "🗓️ Planner", f"{upcoming_plans}", "plans in the next 30 days"),
]

for card_column, (card_key, card_label, card_value, card_note) in zip(
    st.columns(len(highlight_cards)), highlight_cards
):
    with card_column:
        card_active = st.session_state["panel"] == card_key
        st.metric(card_label, card_value)
        st.caption(card_note)
        st.button(
            "Showing" if card_active else "Open",
            key=f"open_{card_key}",
            on_click=_open_panel,
            args=(card_key,),
            type="primary" if card_active else "secondary",
            width="stretch",
        )


# =========================================================
# 7. MAIN CHARTS
# =========================================================

if st.session_state["panel"] == "overview":
    if df.empty:
        st.info(
            "No activities found in this date range. "
            "Add an activity using the sidebar."
        )
    else:
        st.subheader("⏱️ Today's Time Tracker")

        today_hours = get_daily_total(today)
        remaining_hours = max(0.0, 24.0 - today_hours)

        progress_col1, progress_col2 = st.columns([3, 1])

        with progress_col1:
            st.write(f"**{today_hours:.2f} of 24 hours logged**")
            st.progress(
                min(today_hours / 24.0, 1.0),
                text=f"{min(today_hours / 24.0 * 100, 100):.1f}% logged",
            )

        with progress_col2:
            st.metric("Unlogged hours", f"{remaining_hours:.2f}")

        if today_hours > 24:
            st.warning(
                "Today's records exceed 24 hours. Review overlapping entries."
            )
        elif today_hours == 24:
            st.success("All 24 hours have been accounted for.")
        else:
            st.caption(
                "Unlogged hours are time not recorded in the app, "
                "not necessarily free time."
            )

        st.divider()

        category_totals = (
            df.groupby("activity_type", as_index=False)
            ["duration_hours"]
            .sum()
            .sort_values("duration_hours", ascending=False)
        )

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Time by activity")

            pie_chart = px.pie(
                category_totals,
                names="activity_type",
                values="duration_hours",
                hole=0.48,
            )

            pie_chart.update_traces(
                textposition="inside",
                textinfo="percent",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Hours: %{value:.2f}<br>"
                    "Share: %{percent}"
                    "<extra></extra>"
                ),
            )

            pie_chart.update_layout(
                template="plotly_dark",
                margin=dict(l=10, r=10, t=20, b=10),
                legend_title_text="Activity",
            )

            st.plotly_chart(
                pie_chart,
                width="stretch",
            )

        with chart_col2:
            st.subheader("Daily hours by activity")

            daily = (
                df.groupby(
                    ["activity_date", "activity_type"],
                    as_index=False,
                )["duration_hours"]
                .sum()
            )

            daily["activity_date"] = daily[
                "activity_date"
            ].astype(str)

            bar_chart = px.bar(
                daily,
                x="activity_date",
                y="duration_hours",
                color="activity_type",
                barmode="stack",
                labels={
                    "activity_date": "Date",
                    "duration_hours": "Hours",
                    "activity_type": "Activity",
                },
            )

            bar_chart.update_traces(
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "Hours: %{y:.2f}"
                    "<extra></extra>"
                )
            )

            bar_chart.update_layout(
                template="plotly_dark",
                height=350,
                margin=dict(l=20, r=20, t=30, b=20),
                legend_title_text="Activity",
                xaxis=dict(
                    title="Date",
                    type="category",
                    tickangle=-30,
                ),
                yaxis=dict(
                    title="Hours",
                    rangemode="tozero",
                ),
            )

            st.plotly_chart(
                bar_chart,
                width="stretch",
                config={"displayModeBar": False},
            )


# =========================================================
# 8. ADVANCED ANALYTICS
# =========================================================

if st.session_state["panel"] == "analytics":
    st.header("📈 Advanced Analytics")

    if df.empty:
        st.info("Add activities to view advanced analytics.")
    else:
        analytics_col1, analytics_col2 = st.columns(2)

        allocation = (
            df.groupby("activity_type", as_index=False)
            ["duration_hours"]
            .sum()
            .sort_values("duration_hours", ascending=False)
        )

        total_allocation = float(allocation["duration_hours"].sum())

        allocation["percentage"] = (
            allocation["duration_hours"] / total_allocation * 100
        )

        allocation["percentage_label"] = allocation[
            "percentage"
        ].map(lambda value: f"{value:.2f}%")

        with analytics_col1:
            st.subheader("Time Allocation (%)")

            display_allocation = allocation[
                ["activity_type", "duration_hours", "percentage"]
            ].rename(
                columns={
                    "activity_type": "Activity",
                    "duration_hours": "Total Hours",
                    "percentage": "Share (%)",
                }
            )

            st.dataframe(
                display_allocation.style.format({
                    "Total Hours": "{:.2f}",
                    "Share (%)": "{:.2f}%",
                }),
                width="stretch",
                hide_index=True,
            )

            allocation_chart = px.bar(
                allocation,
                x="activity_type",
                y="percentage",
                text="percentage_label",
                labels={
                    "activity_type": "Activity",
                    "percentage": "Share of Logged Time (%)",
                },
                title="Activity Distribution",
            )

            allocation_chart.update_traces(
                texttemplate="%{y:.2f}%",
                textposition="outside",
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Share: %{y:.2f}%"
                    "<extra></extra>"
                ),
            )

            allocation_chart.update_layout(
                template="plotly_dark",
                yaxis_range=[0, 110],
                yaxis_ticksuffix="%",
                margin=dict(l=10, r=10, t=45, b=10),
            )

            st.plotly_chart(
                allocation_chart,
                width="stretch",
            )

        with analytics_col2:
            st.subheader("Time Trends")

            trend_period = st.selectbox(
                "Group data by",
                ["Daily", "Weekly", "Monthly"],
                key="trend_period",
            )

            trend_data = df.copy()

            trend_data["activity_date"] = pd.to_datetime(
                trend_data["activity_date"]
            )

            if trend_period == "Daily":
                trend_data["period"] = (
                    trend_data["activity_date"].dt.strftime("%Y-%m-%d")
                )
            elif trend_period == "Weekly":
                trend_data["period"] = (
                    trend_data["activity_date"]
                    .dt.to_period("W-SUN")
                    .dt.start_time.dt.strftime("%Y-%m-%d")
                )
            else:
                trend_data["period"] = (
                    trend_data["activity_date"].dt.strftime("%Y-%m")
                )

            trend_summary = (
                trend_data.groupby(
                    ["period", "activity_type"],
                    as_index=False,
                )["duration_hours"]
                .sum()
            )

            trend_chart = px.bar(
                trend_summary,
                x="period",
                y="duration_hours",
                color="activity_type",
                barmode="stack",
                labels={
                    "period": trend_period,
                    "duration_hours": "Hours",
                    "activity_type": "Activity",
                },
                title=f"{trend_period} Activity Hours",
            )

            trend_chart.update_layout(
                template="plotly_dark",
                height=380,
                margin=dict(l=20, r=20, t=45, b=30),
                legend_title_text="Activity",
                xaxis=dict(
                    title=trend_period,
                    type="category",
                    tickangle=-30,
                ),
                yaxis=dict(
                    title="Hours",
                    rangemode="tozero",
                ),
                hovermode="x unified",
            )

            trend_chart.update_xaxes(type="category")

            st.plotly_chart(
                trend_chart,
                width="stretch",
            )

        st.divider()
        st.subheader("⚡ Energy & Mood Rating by Activity")
        energy_summary = (
            df.groupby("activity_type", as_index=False)["energy_level"]
            .mean()
            .sort_values("energy_level", ascending=False)
        )
        energy_fig = px.bar(
            energy_summary,
            x="activity_type",
            y="energy_level",
            title="Average Energy Rating (1 = Drained to 5 = Energized)",
            labels={"activity_type": "Activity", "energy_level": "Avg Energy (1-5)"},
        )
        energy_fig.update_layout(template="plotly_dark", yaxis_range=[0, 5.5])
        st.plotly_chart(energy_fig, width="stretch")

        st.subheader("🔎 Data Quality Checks")

        daily_totals = df.groupby("activity_date")[
            "duration_hours"
        ].sum()

        missing_notes = (
            df["notes"]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

        q1, q2, q3 = st.columns(3)

        q1.metric("Dates with records", int(df["activity_date"].nunique()))
        q2.metric(
            "Dates exceeding 24 hours",
            int((daily_totals > 24).sum()),
        )
        q3.metric("Records with missing notes", int(missing_notes))

        if (daily_totals > 24).any():
            st.warning(
                "Some dates exceed 24 logged hours. "
                "Review records for overlaps or errors."
            )
        else:
            st.success(
                "No daily totals exceed 24 hours in the selected period."
            )

        st.caption(
            "Missing notes are an indicator, not necessarily an error. "
            "Suggestions are informational and not medical advice."
        )


# =========================================================
# 9. ACTIVITY RECORDS, CSV EXPORT, EDIT AND DELETE
# =========================================================

if st.session_state["panel"] == "records":
    st.header("🗂️ Activity Records")

    if df.empty:
        st.info("No records are available for the selected date range.")
    else:
        display_records = df[
            [
                "id",
                "activity_date",
                "activity_type",
                "duration_hours",
                "energy_level",
                "notes",
            ]
        ].copy()

        st.dataframe(
            display_records,
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            "⬇️ Download filtered report (CSV)",
            data=display_records.to_csv(index=False).encode("utf-8"),
            file_name="work_life_balance_report.csv",
            mime="text/csv",
        )

        st.subheader("✏️ Edit or delete a record")

        record_ids = df["id"].astype(int).tolist()

        selected_id = st.selectbox(
            "Select record ID",
            record_ids,
            key="selected_record_id",
        )

        selected = df.loc[df["id"] == selected_id].iloc[0]

        selected_type = selected["activity_type"]

        if selected_type not in ACTIVITIES:
            edit_activities = ACTIVITIES + [selected_type]
        else:
            edit_activities = ACTIVITIES

        with st.form("edit_activity_form"):
            edit_date = st.date_input(
                "Edit date",
                value=selected["activity_date"],
            )

            edit_type = st.selectbox(
                "Edit activity",
                edit_activities,
                index=edit_activities.index(selected_type),
            )

            edit_hours = st.number_input(
                "Edit duration (hours)",
                min_value=0.25,
                max_value=24.0,
                value=float(selected["duration_hours"]),
                step=0.25,
            )

            edit_energy = st.select_slider(
                "Edit Energy / Mood",
                options=[1, 2, 3, 4, 5],
                value=int(selected.get("energy_level", 3)),
                format_func=lambda x: ENERGY_LABELS[x],
            )

            current_notes = (
                "" if pd.isna(selected["notes"])
                else str(selected["notes"])
            )

            edit_notes = st.text_input(
                "Edit notes",
                value=current_notes,
                max_chars=200,
            )

            update_clicked = st.form_submit_button("Update record")

        if update_clicked:
            try:
                updated, message = update_activity(
                    selected_id,
                    edit_date,
                    edit_type,
                    float(edit_hours),
                    edit_notes,
                    new_energy=edit_energy,
                )

                if updated:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

            except sqlite3.Error as error:
                st.error(f"Could not update record: {error}")

        confirm_delete = st.checkbox(
            f"I confirm that I want to delete record ID {selected_id}",
            key="confirm_delete",
        )

        if st.button("🗑️ Delete selected record"):
            if not confirm_delete:
                st.warning("Confirm deletion before continuing.")
            else:
                try:
                    if delete_activity(selected_id):
                        st.success("Record deleted successfully.")
                        st.rerun()
                    else:
                        st.error("Record not found.")

                except sqlite3.Error as error:
                    st.error(f"Could not delete record: {error}")


# =========================================================
# 9B. WEEKLY BALANCE SCORE, AI COACH & SMART SUGGESTIONS
# =========================================================

if st.session_state["panel"] == "balance":
    st.header("🧠 Balance Score & Smart Suggestions")
    st.caption(
        "Your last 7 days are compared with weekly targets for each life area. "
        "Free time left today is then filled with what you have neglected most."
    )

    now_ist = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    today_ist = now_ist.date()

    try:
        week_df = load_activities(today_ist - timedelta(days=6), today_ist)
        todays_plans = load_planned_activities(today_ist, today_ist)
        logged_today = get_daily_total(today_ist)
        goals = merge_goals(load_goal_hours())
    except (sqlite3.Error, pd.errors.DatabaseError) as error:
        st.error(f"Could not load data for suggestions: {error}")
        week_df, todays_plans, logged_today = pd.DataFrame(), pd.DataFrame(), 0.0
        goals = merge_goals({})

    weekly = weekly_balance(week_df, today_ist, goals)
    plan_windows = planned_windows_today(todays_plans, now_ist)
    pending_hours = pending_planned_hours(plan_windows, now_ist)
    free_hours = remaining_today(logged_today, pending_hours)

    score_col, logged_col, planned_col, free_col = st.columns(4)
    score_col.metric(
        "⚖️ Weekly balance score",
        "—" if weekly["score"] is None else f"{weekly['score']} / 100",
    )
    score_col.caption(weekly["label"])
    logged_col.metric("✅ Logged today", f"{logged_today:.2f} h")
    planned_col.metric("📅 Planned (still ahead)", f"{pending_hours:.2f} h")
    free_col.metric("🆓 Unplanned today", f"{free_hours:.2f} h")

    with st.expander("🤖 AI Burnout & Weekly Routine Coach", expanded=True):
        if st.button("✨ Generate AI Weekly Coaching Insight", key="run_ai_coach"):
            with st.spinner("Analyzing your 7-day logs & energy patterns..."):
                coach_reply, coach_err = generate_weekly_coach_insight(week_df, weekly)
            if coach_err:
                st.warning(coach_err)
            else:
                st.session_state["ai_coach_text"] = coach_reply
        if st.session_state.get("ai_coach_text"):
            st.markdown(st.session_state["ai_coach_text"])

    if weekly["rows"]:
        chart_rows = []
        for row in weekly["rows"]:
            chart_rows.append({"Category": row["category"], "Hours": row["actual"], "Type": "Logged"})
            chart_rows.append({"Category": row["category"], "Hours": row["target"], "Type": "Target / limit"})
        balance_fig = px.bar(
            pd.DataFrame(chart_rows),
            x="Category",
            y="Hours",
            color="Type",
            barmode="group",
            title=f"Logged vs target ({weekly['active_days']} active day(s) in the last 7)",
        )
        st.plotly_chart(balance_fig, width="stretch")

    def _reset_goals_callback():
        try:
            reset_goal_hours()
            for goal_category, (_, default_hours) in WEEKLY_TARGETS.items():
                st.session_state[f"goal_{goal_category}"] = float(default_hours)
            st.session_state["goals_message"] = ("success", "Goals reset to the defaults.")
        except sqlite3.Error as error:
            st.session_state["goals_message"] = ("error", f"Could not reset goals: {error}")

    with st.expander("⚙️ My weekly goals", expanded=False):
        st.caption(
            "Set how many hours per week you want for each area. 'At least' goals "
            "are minimums to reach; 'at most' is a limit (for example work)."
        )
        for goal_category, (_, _) in goals.items():
            st.session_state.setdefault(f"goal_{goal_category}", float(goals[goal_category][1]))

        with st.form("goals_form"):
            goal_cols = st.columns(2)
            new_goals = {}
            for position, (goal_category, (goal_kind, _)) in enumerate(WEEKLY_TARGETS.items()):
                limit_word = "at most" if goal_kind == "max" else "at least"
                new_goals[goal_category] = goal_cols[position % 2].number_input(
                    f"{goal_category} ({limit_word}, h/week)",
                    min_value=0.0,
                    max_value=168.0,
                    step=0.5,
                    key=f"goal_{goal_category}",
                )
            goals_submitted = st.form_submit_button("💾 Save goals")

        st.button("↩️ Reset to defaults", on_click=_reset_goals_callback)

        minimum_total = sum(
            hours for name, hours in new_goals.items() if WEEKLY_TARGETS[name][0] == "min"
        )
        st.caption(f"Your 'at least' goals add up to {minimum_total:.1f} of 168 hours in a week.")

        goals_message = st.session_state.pop("goals_message", None)
        if goals_message:
            (st.success if goals_message[0] == "success" else st.error)(goals_message[1])

        if goals_submitted:
            goal_errors = validate_goals(new_goals)
            if goal_errors:
                for goal_error in goal_errors:
                    st.error(goal_error)
            else:
                try:
                    save_goal_hours(new_goals)
                    st.session_state["goals_message"] = ("success", "Goals saved.")
                    st.rerun()
                except sqlite3.Error as error:
                    st.error(f"Could not save goals: {error}")

    st.subheader("💡 Suggested plan for the rest of today")
    suggestions, suggestion_tips = suggest_activities(
        now_ist, plan_windows, weekly, free_hours
    )

    for tip in suggestion_tips:
        st.info(tip)

    for index, item in enumerate(suggestions):
        text_col, button_col = st.columns([4, 1])
        with text_col:
            st.markdown(
                f"**🕒 {item['start']:%H:%M} – {item['end']:%H:%M} · "
                f"{item['category']}** ({item['hours']:.2f} h)"
            )
            st.caption(item["reason"])
        with button_col:
            if st.button(
                "➕ Add to plan",
                key=f"add_suggestion_{index}_{item['category']}_{item['start']:%H%M}",
                width="stretch",
            ):
                try:
                    saved, message = save_planned_activity(
                        today_ist,
                        item["category"],
                        f"{item['start']:%H:%M}",
                        f"{item['end']:%H:%M}",
                        "Suggested by balance assistant",
                    )
                    if saved:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                except sqlite3.Error as error:
                    st.error(f"Could not save planned activity: {error}")


# =========================================================
# 10. ACTIVITY PLANNER
# =========================================================

if st.session_state["panel"] == "planner":
    st.header("🗓️ Activity Planner")
    st.caption("Plan your day, then update each activity as it progresses.")

    planner_tab_add, planner_tab_manage = st.tabs(
        ["➕ Add a plan", "📋 Manage plans"]
    )

    with planner_tab_add:
        with st.form("add_planned_activity_form", clear_on_submit=True):
            plan_col1, plan_col2 = st.columns(2)

            with plan_col1:
                planned_date = st.date_input(
                    "Planned date",
                    value=date.today(),
                    key="planned_activity_date",
                )
                planned_type = st.selectbox(
                    "Activity type",
                    ACTIVITIES,
                    key="planned_activity_type",
                )
                planned_start = st.time_input(
                    "Start time",
                    value=datetime.strptime("09:00", "%H:%M").time(),
                    key="planned_start_time",
                )

            with plan_col2:
                planned_end = st.time_input(
                    "End time",
                    value=datetime.strptime("10:00", "%H:%M").time(),
                    key="planned_end_time",
                )
                allow_overnight = st.checkbox(
                    "🌙 Overnight plan (crosses midnight, e.g. 23:00 to 06:00)",
                    value=False,
                    key="planned_allow_overnight",
                )
                repeat_mode = st.selectbox(
                    "Repeat schedule",
                    ["None", "Daily (Next 7 days)", "Weekdays (Mon-Fri)"],
                    key="planned_repeat_mode",
                )
                planned_notes = st.text_input(
                    "Notes (optional)",
                    max_chars=200,
                    key="planned_activity_notes",
                )

            save_plan_clicked = st.form_submit_button(
                "💾 Save planned activity",
                width="stretch",
            )

        if save_plan_clicked:
            try:
                saved, message = save_recurring_planned_activities(
                    planned_date,
                    planned_type,
                    planned_start.strftime("%H:%M"),
                    planned_end.strftime("%H:%M"),
                    planned_notes,
                    repeat_mode=repeat_mode,
                    allow_overnight=allow_overnight,
                )
                if saved:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            except sqlite3.Error as error:
                st.error(f"Could not save planned activity: {error}")

    with planner_tab_manage:
        range_col1, range_col2 = st.columns(2)
        with range_col1:
            planner_from = st.date_input(
                "Show plans from",
                value=date.today() - timedelta(days=7),
                key="planner_filter_from",
            )
        with range_col2:
            planner_to = st.date_input(
                "Show plans to",
                value=date.today() + timedelta(days=30),
                key="planner_filter_to",
            )

        if planner_from > planner_to:
            st.error("The start date cannot be later than the end date.")
        else:
            try:
                mark_overdue_activities_failed()
                planned_df = load_planned_activities(planner_from, planner_to)
            except sqlite3.Error as error:
                st.error(f"Could not load planned activities: {error}")
                planned_df = pd.DataFrame()

            if planned_df.empty:
                st.info("No planned activities found in this date range. Add a plan in the first tab.")
            else:
                india_tz = ZoneInfo("Asia/Kolkata")
                now_local = datetime.now(india_tz)
                due_window_end = now_local + timedelta(minutes=5)

                def _plan_start_dt(row):
                    plan_date = row["activity_date"]
                    if isinstance(plan_date, str):
                        plan_date = date.fromisoformat(plan_date)
                    plan_time = datetime.strptime(str(row["start_time"]), "%H:%M").time()
                    return datetime.combine(plan_date, plan_time).replace(tzinfo=india_tz)

                def _plan_end_dt(row):
                    plan_date = row["activity_date"]
                    if isinstance(plan_date, str):
                        plan_date = date.fromisoformat(plan_date)
                    start_t = datetime.strptime(str(row["start_time"]), "%H:%M").time()
                    end_t = datetime.strptime(str(row["end_time"]), "%H:%M").time()
                    end_date = plan_date + timedelta(days=1) if end_t <= start_t else plan_date
                    return datetime.combine(end_date, end_t).replace(tzinfo=india_tz)

                plan_rows = planned_df.copy()
                plan_rows["_start_dt"] = plan_rows.apply(_plan_start_dt, axis=1)
                plan_rows["_end_dt"] = plan_rows.apply(_plan_end_dt, axis=1)

                is_planned = plan_rows["status"].eq("Planned")
                active_df = plan_rows[
                    is_planned & (plan_rows["_start_dt"] <= now_local)
                    & (plan_rows["_end_dt"] > now_local)
                ].copy()
                upcoming_df = plan_rows[
                    is_planned & (plan_rows["_start_dt"] > due_window_end)
                ].copy()
                completed_df = plan_rows[plan_rows["status"].eq("Completed")].copy()
                activity_failed_df = plan_rows[plan_rows["status"].eq("Failed")].copy()

                try:
                    reminder_df = load_reminder_history(planner_from, planner_to)
                except sqlite3.Error as error:
                    st.error(f"Could not load reminder history: {error}")
                    reminder_df = pd.DataFrame()

                if reminder_df.empty:
                    due_soon_df = pd.DataFrame()
                    failed_df = pd.DataFrame()
                    sent_df = pd.DataFrame()
                else:
                    reminder_df["_reminder_dt"] = pd.to_datetime(
                        reminder_df["reminder_at"], errors="coerce"
                    )

                    def _as_india_time(value):
                        if pd.isna(value):
                            return None
                        parsed = pd.Timestamp(value).to_pydatetime()
                        if parsed.tzinfo is None:
                            return parsed.replace(tzinfo=india_tz)
                        return parsed.astimezone(india_tz)

                    reminder_df["_reminder_dt"] = reminder_df["_reminder_dt"].apply(_as_india_time)
                    due_soon_df = reminder_df[
                        reminder_df["reminder_status"].eq("Pending")
                        & reminder_df["_reminder_dt"].apply(
                            lambda value: value is not None and now_local <= value <= due_window_end
                        )
                    ].copy()
                    failed_df = reminder_df[
                        reminder_df["reminder_status"].eq("Failed")
                    ].copy()
                    sent_df = reminder_df[
                        reminder_df["reminder_status"].eq("Sent")
                    ].copy()

                def _show_plan_table(frame):
                    if frame.empty:
                        st.info("Nothing to show in this section right now.")
                        return
                    view = frame.drop(columns=[c for c in ["_start_dt", "_end_dt"] if c in frame.columns]).copy()
                    view["activity_date"] = view["activity_date"].astype(str)
                    columns = ["id", "activity_date", "start_time", "end_time", "activity_type", "status", "notes"]
                    if "activity_failure_reason" in view.columns:
                        columns.append("activity_failure_reason")
                    view = view.rename(columns={"activity_failure_reason": "why_failed"})
                    columns = ["why_failed" if c == "activity_failure_reason" else c for c in columns]
                    st.dataframe(view[columns], width="stretch", hide_index=True)

                def _show_reminder_table(frame):
                    if frame.empty:
                        st.info("No notification records in this section.")
                        return
                    columns = ["reminder_id", "activity_id", "activity_date", "start_time", "activity_type", "channel", "reminder_at", "reminder_status"]
                    if "failure_reason" in frame.columns:
                        columns.append("failure_reason")
                    st.dataframe(frame[columns], width="stretch", hide_index=True)

                st.subheader("📌 Activity & Notification Status")
                status_tabs = st.tabs([
                    f"🟢 Active ({len(active_df)})",
                    f"⏰ Due in 5 min ({len(due_soon_df)})",
                    f"📅 Upcoming ({len(upcoming_df)})",
                    f"❌ Activity Failed ({len(activity_failed_df)})",
                    f"📨 Notification Failed ({len(failed_df)})",
                    f"📨 Sent ({len(sent_df)})",
                    f"✅ Completed ({len(completed_df)})",
                ])
                with status_tabs[0]:
                    _show_plan_table(active_df)
                with status_tabs[1]:
                    _show_reminder_table(due_soon_df)
                with status_tabs[2]:
                    _show_plan_table(upcoming_df)
                with status_tabs[3]:
                    _show_plan_table(activity_failed_df)
                with status_tabs[4]:
                    _show_reminder_table(failed_df)
                with status_tabs[5]:
                    _show_reminder_table(sent_df)
                with status_tabs[6]:
                    _show_plan_table(completed_df)

                st.divider()
                st.subheader("All planned activities")
                display_plans = planned_df.copy()
                display_plans["activity_date"] = display_plans["activity_date"].astype(str)
                st.dataframe(
                    display_plans[
                        ["id", "activity_date", "start_time", "end_time", "activity_type", "status", "notes", "activity_failure_reason"]
                    ],
                    width="stretch",
                    hide_index=True,
                )

                plan_ids = planned_df["id"].astype(int).tolist()
                selected_plan_id = st.selectbox(
                    "Select a planned activity to manage",
                    plan_ids,
                    format_func=lambda plan_id: (
                        f"#{plan_id} | "
                        f"{planned_df.loc[planned_df['id'] == plan_id, 'activity_date'].iloc[0]} | "
                        f"{planned_df.loc[planned_df['id'] == plan_id, 'activity_type'].iloc[0]}"
                    ),
                    key="selected_planned_activity_id",
                )
                selected_plan = planned_df.loc[
                    planned_df["id"] == selected_plan_id
                ].iloc[0]

                selected_start = datetime.strptime(
                    str(selected_plan["start_time"]), "%H:%M"
                ).time()
                selected_end = datetime.strptime(
                    str(selected_plan["end_time"]), "%H:%M"
                ).time()

                st.subheader("✏️ Edit planned activity")
                with st.form("edit_planned_activity_form"):
                    edit_plan_col1, edit_plan_col2 = st.columns(2)
                    with edit_plan_col1:
                        edit_plan_date = st.date_input(
                            "Edit date",
                            value=selected_plan["activity_date"],
                            key="edit_planned_date",
                        )
                        edit_plan_type = st.selectbox(
                            "Edit activity",
                            ACTIVITIES,
                            index=(ACTIVITIES.index(selected_plan["activity_type"])
                                   if selected_plan["activity_type"] in ACTIVITIES else 0),
                            key="edit_planned_type",
                        )
                        edit_plan_start = st.time_input(
                            "Edit start time",
                            value=selected_start,
                            key="edit_planned_start",
                        )
                    with edit_plan_col2:
                        edit_plan_end = st.time_input(
                            "Edit end time",
                            value=selected_end,
                            key="edit_planned_end",
                        )
                        edit_overnight = st.checkbox(
                            "🌙 Overnight plan",
                            value=(selected_end <= selected_start),
                            key="edit_planned_overnight",
                        )
                        edit_plan_notes = st.text_input(
                            "Edit notes",
                            value="" if pd.isna(selected_plan["notes"]) else str(selected_plan["notes"]),
                            max_chars=200,
                            key="edit_planned_notes",
                        )

                    update_plan_clicked = st.form_submit_button("Update planned activity")

                if update_plan_clicked:
                    try:
                        updated, message = update_planned_activity(
                            selected_plan_id,
                            edit_plan_date,
                            edit_plan_type,
                            edit_plan_start.strftime("%H:%M"),
                            edit_plan_end.strftime("%H:%M"),
                            edit_plan_notes,
                            allow_overnight=edit_overnight,
                        )
                        if updated:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    except sqlite3.Error as error:
                        st.error(f"Could not update planned activity: {error}")

                status_col, delete_col = st.columns(2)
                with status_col:
                    status_options = ["Planned", "Completed", "Failed", "Cancelled"]
                    current_status = str(selected_plan["status"])
                    if current_status not in status_options:
                        current_status = "Planned"
                    new_plan_status = st.selectbox(
                        "Activity status",
                        status_options,
                        index=status_options.index(current_status),
                        key="planned_activity_status",
                    )
                    if st.button("Update status", key="update_planned_status"):
                        try:
                            changed, message = update_planned_activity_status(
                                selected_plan_id, new_plan_status
                            )
                            if changed:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                        except sqlite3.Error as error:
                            st.error(f"Could not update status: {error}")

                with delete_col:
                    confirm_plan_delete = st.checkbox(
                        f"Confirm deletion of planned activity #{selected_plan_id}",
                        key=f"confirm_planned_delete_{selected_plan_id}",
                    )
                    if st.button("🗑️ Delete planned activity", key="delete_planned_activity"):
                        if not confirm_plan_delete:
                            st.warning("Please confirm before deleting this planned activity.")
                        else:
                            try:
                                if delete_planned_activity(selected_plan_id):
                                    st.success("Planned activity deleted successfully.")
                                    st.rerun()
                                else:
                                    st.error("Planned activity not found.")
                            except sqlite3.Error as error:
                                st.error(f"Could not delete planned activity: {error}")


# =========================================================
# 11. FOOTER
# =========================================================

st.divider()

st.caption(
    "Work-Life Balance Manager v3.1 | Python • Streamlit • SQLite • Plotly • Gemini AI"
)

st.caption(
    "Records are stored locally in SQLite on this computer. "
    "Back up the database regularly."
)
