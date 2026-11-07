
from database import (
    DB_PATH,
    initialize_database,
    get_daily_total,
    load_activities,
    save_activity,
    update_activity,
    delete_activity,
    save_planned_activity,
    load_planned_activities,
    update_planned_activity,
    update_planned_activity_status,
    delete_planned_activity,
    load_reminder_history,
)

import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st


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

st.set_page_config(
    page_title="Work-Life Balance Manager",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# 2. PROFESSIONAL RESPONSIVE DESIGN AND ANIMATIONS
# =========================================================

st.markdown("""
<style>
/* Main desktop layout */
.stApp {
    background: #0B1120;
    color: #E5E7EB;
}

.block-container,
[data-testid="stMainBlockContainer"] {
    width: 100% !important;
    max-width: 100% !important;
    padding: 1.5rem 2rem 3rem 2rem !important;
    margin: 0 !important;
    box-sizing: border-box;
}

/* Typography */
h1 {
    color: #F8FAFC !important;
    font-weight: 800 !important;
    letter-spacing: -0.7px;
}

h2, h3 {
    color: #E2E8F0 !important;
    font-weight: 650 !important;
}

p, label {
    color: #D1D5DB;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #111827;
    border-right: 1px solid #263449;
}

section[data-testid="stSidebar"] > div {
    padding-top: 1.5rem;
}

/* Animation */
@keyframes fadeSlideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* KPI cards */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #172033, #111827);
    border: 1px solid #263449;
    border-radius: 14px;
    padding: 18px;
    animation: fadeSlideIn 0.5s ease-out both;
    transition: transform 0.2s ease, border-color 0.2s ease;
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    border-color: #38BDF8;
}

div[data-testid="stMetricLabel"] {
    color: #A7B5CA !important;
}

div[data-testid="stMetricValue"] {
    color: #7DD3FC !important;
    font-weight: 750;
}

/* Forms and controls */
div[data-testid="stForm"] {
    border: 1px solid #263449;
    border-radius: 12px;
    padding: 16px;
}

.stButton button,
.stFormSubmitButton button,
.stDownloadButton button {
    border-radius: 9px;
    min-height: 40px;
    font-weight: 600;
    transition: border-color 0.2s ease;
}

/* Charts and tables */
div[data-testid="stPlotlyChart"],
div[data-testid="stDataFrame"] {
    width: 100%;
    animation: fadeSlideIn 0.6s ease-out both;
}

div[data-testid="stDataFrame"] {
    border: 1px solid #263449;
    border-radius: 10px;
    overflow: hidden;
}

hr {
    border-color: #263449;
    margin: 1.5rem 0;
}

/* Help messages */
div[data-testid="stAlert"] {
    border-radius: 10px;
}

/* Responsive layout for smaller screens */
@media (max-width: 768px) {
    .block-container,
    [data-testid="stMainBlockContainer"] {
        padding: 1rem !important;
    }

    h1 {
        font-size: 1.8rem !important;
    }

    div[data-testid="stMetric"] {
        padding: 12px;
    }
}

/* Respect reduced-motion accessibility settings */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation: none !important;
        transition: none !important;
    }
}
</style>
""", unsafe_allow_html=True)


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

st.title("⚖️ Work-Life Balance Manager")

st.markdown(
    "#### Your time, organized. Your routine, understood."
)

st.caption(
    "Track daily activities, monitor time allocation, "
    "and explore your work-life patterns."
)

with st.expander("Application information"):
    st.write("Application: Work-Life Balance Manager")
    st.write("Database: SQLite")
    st.write("Charts: Plotly")
    st.write("Interface: Streamlit")
    st.write("Database location:")
    st.code(str(DB_PATH))

st.divider()


# =========================================================
# 5. ADD ACTIVITY FORM
# =========================================================

st.sidebar.title("➕ Add an activity")

with st.sidebar.form("add_activity_form", clear_on_submit=True):
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

    notes = st.text_input(
        "Notes (optional)",
        max_chars=200,
    )

    save_clicked = st.form_submit_button(
        "💾 Save activity",
        use_container_width=True,
    )

if save_clicked:
    try:
        saved, message = save_activity(
            activity_date,
            activity_type,
            float(duration),
            notes,
        )

        if saved:
            st.sidebar.success(message)
            st.rerun()
        else:
            st.sidebar.error(message)

    except (sqlite3.Error, ValueError) as error:
        st.sidebar.error(f"Could not save activity: {error}")


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
# 7. KPI CARDS AND MAIN CHARTS
# =========================================================

if df.empty:
    st.info(
        "No activities found in this date range. "
        "Add an activity using the sidebar."
    )
else:
    total_hours = float(df["duration_hours"].sum())

    work_hours = float(
        df.loc[
            df["activity_type"] == "Work",
            "duration_hours",
        ].sum()
    )

    sleep_hours = float(
        df.loc[
            df["activity_type"] == "Sleep",
            "duration_hours",
        ].sum()
    )

    active_days = int(df["activity_date"].nunique())

    k1, k2, k3, k4 = st.columns(4)

    k1.metric("🕒 Recorded hours", f"{total_hours:.1f}")
    k2.metric("💼 Work hours", f"{work_hours:.1f}")
    k3.metric("🌙 Sleep hours", f"{sleep_hours:.1f}")
    k4.metric(
        "📅 Avg. hours per active day",
        f"{total_hours / active_days:.1f}",
    )

    # Daily tracker
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

    # Category totals
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
            use_container_width=True,
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
            margin=dict(l=10, r=10, t=20, b=10),
            legend_title_text="Activity",
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
            use_container_width=True,
            config={"displayModeBar": False},
        )


# =========================================================
# 8. ADVANCED ANALYTICS
# =========================================================

st.divider()
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
            use_container_width=True,
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
            use_container_width=True,
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
            use_container_width=True,
        )

    # Data quality
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

st.divider()
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
            "notes",
        ]
    ].copy()

    st.dataframe(
        display_records,
        use_container_width=True,
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
# 10. ACTIVITY PLANNER
# =========================================================

st.divider()
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
            planned_notes = st.text_input(
                "Notes (optional)",
                max_chars=200,
                key="planned_activity_notes",
            )

        save_plan_clicked = st.form_submit_button(
            "💾 Save planned activity",
            use_container_width=True,
        )

    if save_plan_clicked:
        try:
            saved, message = save_planned_activity(
                planned_date,
                planned_type,
                planned_start.strftime("%H:%M"),
                planned_end.strftime("%H:%M"),
                planned_notes,
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
            planned_df = load_planned_activities(planner_from, planner_to)
        except sqlite3.Error as error:
            st.error(f"Could not load planned activities: {error}")
            planned_df = pd.DataFrame()

        if planned_df.empty:
            st.info("No planned activities found in this date range. Add a plan in the first tab.")
        else:
            # Status dashboard: categories are calculated from the current India time.
            india_tz = ZoneInfo("Asia/Kolkata")
            now_local = datetime.now(india_tz)
            due_window_end = now_local + timedelta(minutes=5)

            def _plan_datetime(row, time_column):
                plan_date = row["activity_date"]
                if isinstance(plan_date, str):
                    plan_date = date.fromisoformat(plan_date)
                plan_time = datetime.strptime(str(row[time_column]), "%H:%M").time()
                return datetime.combine(plan_date, plan_time).replace(tzinfo=india_tz)

            plan_rows = planned_df.copy()
            plan_rows["_start_dt"] = plan_rows.apply(
                lambda row: _plan_datetime(row, "start_time"), axis=1
            )
            plan_rows["_end_dt"] = plan_rows.apply(
                lambda row: _plan_datetime(row, "end_time"), axis=1
            )
            is_planned = plan_rows["status"].eq("Planned")
            active_df = plan_rows[
                is_planned & (plan_rows["_start_dt"] <= now_local)
                & (plan_rows["_end_dt"] > now_local)
            ].copy()
            upcoming_df = plan_rows[
                is_planned & (plan_rows["_start_dt"] > due_window_end)
            ].copy()
            completed_df = plan_rows[plan_rows["status"].eq("Completed")].copy()

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
                # SQLite values are stored with India offset; normalise for comparison.
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
                st.dataframe(view[columns], use_container_width=True, hide_index=True)

            def _show_reminder_table(frame):
                if frame.empty:
                    st.info("No notification records in this section.")
                    return
                columns = ["reminder_id", "activity_id", "activity_date", "start_time", "activity_type", "channel", "reminder_at", "reminder_status"]
                if "failure_reason" in frame.columns:
                    columns.append("failure_reason")
                st.dataframe(frame[columns], use_container_width=True, hide_index=True)

            st.subheader("📌 Activity & Notification Status")
            status_tabs = st.tabs([
                f"🟢 Active ({len(active_df)})",
                f"⏰ Due in 5 min ({len(due_soon_df)})",
                f"📅 Upcoming ({len(upcoming_df)})",
                f"❌ Failed ({len(failed_df)})",
                f"📨 Sent ({len(sent_df)})",
                f"✅ Completed ({len(completed_df)})",
            ])
            with status_tabs[0]:
                _show_plan_table(active_df)
            with status_tabs[1]:
                _show_reminder_table(due_soon_df)
                st.caption("These are pending SMS, voice and email reminders scheduled between now and the next five minutes. Keep scheduler.py running for delivery.")
            with status_tabs[2]:
                _show_plan_table(upcoming_df)
            with status_tabs[3]:
                _show_reminder_table(failed_df)
                st.caption("Failed refers to notification attempts, not the activity itself. Review the failure reason before retrying.")
            with status_tabs[4]:
                _show_reminder_table(sent_df)
                st.caption("Sent means the provider accepted the notification request. Check the provider dashboard for final delivery details.")
            with status_tabs[5]:
                _show_plan_table(completed_df)

            st.divider()
            st.subheader("All planned activities")
            display_plans = planned_df.copy()
            display_plans["activity_date"] = display_plans["activity_date"].astype(str)
            st.dataframe(
                display_plans[
                    ["id", "activity_date", "start_time", "end_time", "activity_type", "status", "notes"]
                ],
                use_container_width=True,
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
                status_options = ["Planned", "Completed", "Cancelled"]
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
    "Work-Life Balance Manager | Python • Streamlit • SQLite • Plotly"
)

st.caption(
    "Records are stored locally in SQLite on this computer. "
    "Back up the database regularly."
)
