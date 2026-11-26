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
    mark_overdue_activities_failed,
    load_goal_hours,
    save_goal_hours,
    reset_goal_hours,
    load_activity_templates,
    save_activity_template,
    save_daily_checkin,
    load_daily_checkin,
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

st.title("⚖️ Work-Life Balance Manager")

st.markdown("#### Your time, organized. Your routine, understood.")

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


# =========================================================
# 5. ADD ACTIVITY FORM & COMPACT QUICK PRESETS (Direct Save)
# =========================================================

today = date.today()

st.sidebar.title("➕ Add an activity")

st.sidebar.markdown("**⚡ Quick Presets (1-Click Save):**")
preset_col1, preset_col2, preset_col3 = st.sidebar.columns(3)

with preset_col1:
    if st.button("⏱️ Work", use_container_width=True, help="Quick save 7h Work"):
        try:
            saved, message = save_activity(today, "Work", 7.0, "Quick preset work")
            if saved:
                st.sidebar.success("7h Work added!")
                st.rerun()
        except Exception as e:
            st.sidebar.error(str(e))

with preset_col2:
    if st.button("🏃 Exer", use_container_width=True, help="Quick save 45m Exercise"):
        try:
            saved, message = save_activity(today, "Exercise", 0.75, "Quick preset exercise")
            if saved:
                st.sidebar.success("45m Exercise added!")
                st.rerun()
        except Exception as e:
            st.sidebar.error(str(e))

with preset_col3:
    if st.button("💤 Sleep", use_container_width=True, help="Quick save 7h Sleep"):
        try:
            saved, message = save_activity(today, "Sleep", 7.0, "Quick preset sleep")
            if saved:
                st.sidebar.success("7h Sleep added!")
                st.rerun()
        except Exception as e:
            st.sidebar.error(str(e))

st.sidebar.markdown("---")

templates = load_activity_templates()
template_labels = [
    f"{t['name']} ({t['duration_hours']}h · {t['activity_type']})" for t in templates
]

with st.sidebar.expander("📌 Routine Templates & Catch-Up", expanded=False):
    catchup_choice = st.radio(
        "Log for",
        ["Today", "Yesterday"],
        horizontal=True,
        key="catchup_day_choice",
    )
    target_log_date = today - timedelta(days=1) if catchup_choice == "Yesterday" else today

    selected_tpl_idx = st.selectbox(
        "Choose template",
        options=range(len(templates)),
        format_func=lambda idx: template_labels[idx],
        key="selected_routine_template",
    )
    chosen_tpl = templates[selected_tpl_idx]

    if st.button(f"⚡ Log to {catchup_choice}", use_container_width=True, key="apply_template_btn"):
        saved, message = save_activity(
            target_log_date,
            chosen_tpl["activity_type"],
            float(chosen_tpl["duration_hours"]),
            chosen_tpl.get("notes") or chosen_tpl["name"],
        )
        if saved:
            st.sidebar.success(f"Logged {chosen_tpl['name']} for {catchup_choice.lower()}!")
            st.rerun()
        else:
            st.sidebar.error(message)

    with st.form("new_template_form", clear_on_submit=True):
        tpl_name = st.text_input("New template name", max_chars=40)
        tpl_type = st.selectbox("Activity", ACTIVITIES, key="new_tpl_type")
        tpl_hrs = st.number_input(
            "Hours", min_value=0.25, max_value=12.0, value=1.0, step=0.25, key="new_tpl_hrs"
        )
        tpl_notes = st.text_input("Default note", max_chars=120, key="new_tpl_notes")
        if st.form_submit_button("➕ Save template", use_container_width=True):
            ok, msg = save_activity_template(tpl_name, tpl_type, tpl_hrs, tpl_notes)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

with st.sidebar.form("add_activity_form", clear_on_submit=True):
    activity_date = st.date_input(
        "Activity date",
        value=today,
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
# 6B. HIGHLIGHT CARDS (click a card to open its panel)
# =========================================================

st.session_state.setdefault("panel", "overview")

if st.session_state["panel"] == "overview" and not df.empty:
    total_work_in_df = float(df.loc[df["activity_type"] == "Work", "duration_hours"].sum())
    active_days_count = int(df["activity_date"].nunique())
    avg_work_per_day = total_work_in_df / max(active_days_count, 1)

    if avg_work_per_day >= 8.0:
        st.warning(
            f"⚠️ **High Workload Alert:** Your average work duration is **{avg_work_per_day:.1f} hours/day** in this date range. "
            "Consider taking short breaks, scheduling personal care, or light exercise to avoid burnout!"
        )
    elif total_work_in_df > 0:
        st.info("💡 **Tip:** Your work-life balance is looking healthy and balanced for this period. Keep it up!")


def _open_panel(panel_name):
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
        clean_name = card_label.split(" ", 1)[1] if " " in card_label else card_label
        button_text = f"Viewing {clean_name}" if card_active else f"Open {clean_name}"

        st.button(
            button_text,
            key=f"open_{card_key}",
            on_click=_open_panel,
            args=(card_key,),
            type="primary" if card_active else "secondary",
            use_container_width=True,
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
            st.warning("Today's records exceed 24 hours. Review overlapping entries.")
        elif today_hours == 24:
            st.success("All 24 hours have been accounted for.")
        else:
            st.caption(
                "Unlogged hours are time not recorded in the app, "
                "not necessarily free time."
            )

        st.divider()

        category_totals = (
            df.groupby("activity_type", as_index=False)["duration_hours"]
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

            st.plotly_chart(pie_chart, use_container_width=True)

        with chart_col2:
            st.subheader("Daily hours by activity")

            daily = (
                df.groupby(["activity_date", "activity_type"], as_index=False)["duration_hours"]
                .sum()
            )
            daily["activity_date"] = daily["activity_date"].astype(str)

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
                xaxis=dict(title="Date", type="category", tickangle=-30),
                yaxis=dict(title="Hours", rangemode="tozero"),
            )

            st.plotly_chart(
                bar_chart,
                use_container_width=True,
                config={"displayModeBar": False},
            )

    st.divider()
    st.subheader("🎯 Focus Session & Daily Check-In")
    f_col1, f_col2 = st.columns(2)

    with f_col1:
        st.markdown("**⏱️ Quick Focus Logger**")
        focus_preset = st.selectbox(
            "Session block",
            [
                ("25 min Focus (0.50h)", "Work", 0.50),
                ("50 min Deep Work (0.75h)", "Work", 0.75),
                ("45 min Study Block (0.75h)", "Study", 0.75),
                ("15 min Reset Break (0.25h)", "Personal Care", 0.25),
            ],
            format_func=lambda item: item[0],
            key="focus_session_preset",
        )
        focus_note = st.text_input(
            "Session topic",
            placeholder="e.g. SQL queries, API check",
            key="focus_session_note",
        )
        if st.button("✅ Log Completed Focus Block", use_container_width=True, key="log_focus_block_btn"):
            saved, message = save_activity(
                today,
                focus_preset[1],
                focus_preset[2],
                focus_note or focus_preset[0],
            )
            if saved:
                st.success(f"Logged {focus_preset[0]}!")
                st.rerun()
            else:
                st.error(message)

    with f_col2:
        st.markdown("**📝 Daily Check-In**")
        existing_checkin = load_daily_checkin(today)
        mood_options = ["Energized", "Steady", "Drained / Heavy"]
        default_mood = (
            existing_checkin["mood"]
            if existing_checkin and existing_checkin.get("mood") in mood_options
            else "Steady"
        )
        default_note = existing_checkin.get("note", "") if existing_checkin else ""

        chosen_mood = st.radio(
            "How does today feel?",
            mood_options,
            index=mood_options.index(default_mood),
            horizontal=True,
            key="daily_checkin_mood",
        )
        checkin_note = st.text_input("Quick wrap-up note", value=default_note, key="daily_checkin_note")
        if st.button("💾 Save Check-In", use_container_width=True, key="save_checkin_btn"):
            save_daily_checkin(today, chosen_mood, checkin_note)
            st.success(f"Check-in saved: {chosen_mood}")
            st.rerun()

        if existing_checkin:
            st.caption(
                f"Saved today: **{existing_checkin['mood']}** — "
                f"{existing_checkin.get('note') or 'No note'}"
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
            df.groupby("activity_type", as_index=False)["duration_hours"]
            .sum()
            .sort_values("duration_hours", ascending=False)
        )

        total_allocation = float(allocation["duration_hours"].sum())
        allocation["percentage"] = allocation["duration_hours"] / total_allocation * 100
        allocation["percentage_label"] = allocation["percentage"].map(lambda value: f"{value:.2f}%")

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
                hovertemplate="<b>%{x}</b><br>Share: %{y:.2f}%<extra></extra>",
            )

            allocation_chart.update_layout(
                template="plotly_dark",
                yaxis_range=[0, 110],
                yaxis_ticksuffix="%",
                margin=dict(l=10, r=10, t=45, b=10),
            )

            st.plotly_chart(allocation_chart, use_container_width=True)

        with analytics_col2:
            st.subheader("Time Trends")

            trend_period = st.selectbox(
                "Group data by",
                ["Daily", "Weekly", "Monthly"],
                key="trend_period",
            )

            trend_data = df.copy()
            trend_data["activity_date"] = pd.to_datetime(trend_data["activity_date"])

            if trend_period == "Daily":
                trend_data["period"] = trend_data["activity_date"].dt.strftime("%Y-%m-%d")
            elif trend_period == "Weekly":
                trend_data["period"] = (
                    trend_data["activity_date"]
                    .dt.to_period("W-SUN")
                    .dt.start_time.dt.strftime("%Y-%m-%d")
                )
            else:
                trend_data["period"] = trend_data["activity_date"].dt.strftime("%Y-%m")

            trend_summary = (
                trend_data.groupby(["period", "activity_type"], as_index=False)["duration_hours"]
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
                xaxis=dict(title=trend_period, type="category", tickangle=-30),
                yaxis=dict(title="Hours", rangemode="tozero"),
                hovermode="x unified",
            )

            trend_chart.update_xaxes(type="category")
            st.plotly_chart(trend_chart, use_container_width=True)

        st.subheader("🔎 Data Quality Checks")

        daily_totals = df.groupby("activity_date")["duration_hours"].sum()
        missing_notes = df["notes"].fillna("").astype(str).str.strip().eq("").sum()

        q1, q2, q3 = st.columns(3)
        q1.metric("Dates with records", int(df["activity_date"].nunique()))
        q2.metric("Dates exceeding 24 hours", int((daily_totals > 24).sum()))
        q3.metric("Records with missing notes", int(missing_notes))

        if (daily_totals > 24).any():
            st.warning("Some dates exceed 24 logged hours. Review records for overlaps or errors.")
        else:
            st.success("No daily totals exceed 24 hours in the selected period.")

        st.caption(
            "Missing notes are an indicator, not necessarily an error. "
            "Suggestions are informational and not medical advice."
        )


# =========================================================
# 9. ACTIVITY RECORDS, CSV EXPORT, EDIT AND DELETE
# =========================================================

if st.session_state["panel"] == "records":
    st.header("🗂️ Activity Records & Export")

    if df.empty:
        st.info("No records are available for the selected date range.")
    else:
        display_records = df[
            ["id", "activity_date", "activity_type", "duration_hours", "notes"]
        ].copy()

        st.dataframe(display_records, use_container_width=True, hide_index=True)

        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            st.download_button(
                "⬇️ Download Filtered Report (CSV)",
                data=display_records.to_csv(index=False).encode("utf-8"),
                file_name=f"work_life_balance_report_{start_date}_to_{end_date}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_exp2:
            total_logged_hours = display_records["duration_hours"].sum()
            st.info(
                f"📊 Total hours in this report: **{total_logged_hours:.2f} hrs** "
                f"across {len(display_records)} records."
            )

        st.divider()
        st.subheader("✏️ Edit or delete a record")

        record_ids = df["id"].astype(int).tolist()
        selected_id = st.selectbox("Select record ID", record_ids, key="selected_record_id")
        selected = df.loc[df["id"] == selected_id].iloc[0]
        selected_type = selected["activity_type"]
        edit_activities = ACTIVITIES + [selected_type] if selected_type not in ACTIVITIES else ACTIVITIES

        with st.form("edit_activity_form"):
            edit_date = st.date_input("Edit date", value=selected["activity_date"])
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
            current_notes = "" if pd.isna(selected["notes"]) else str(selected["notes"])
            edit_notes = st.text_input("Edit notes", value=current_notes, max_chars=200)
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
# 9B. WEEKLY BALANCE SCORE, PROGRESS BARS & SMART SUGGESTIONS
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

    st.divider()

    st.subheader("🤖 AI Weekly Health & Productivity Coach")
    with st.spinner("Analyzing your weekly routine with Gemini AI..."):
        from ai_coach import get_ai_weekly_coach_insights

        week_work = (
            float(week_df.loc[week_df["activity_type"] == "Work", "duration_hours"].sum())
            if not week_df.empty
            else 0.0
        )
        week_sleep = (
            float(week_df.loc[week_df["activity_type"] == "Sleep", "duration_hours"].sum())
            if not week_df.empty
            else 0.0
        )
        total_week_hrs = float(week_df["duration_hours"].sum()) if not week_df.empty else 0.0
        score_val = weekly["score"] if weekly["score"] is not None else 50

        ai_advice = get_ai_weekly_coach_insights(
            week_df, total_week_hrs, week_work, week_sleep, score_val
        )
        st.markdown(ai_advice)

    st.divider()

    st.subheader("🎯 Weekly Goals Progress")
    st.caption("Track your actual logged hours over the last 7 days against your set weekly targets.")

    if weekly["rows"]:
        for row in weekly["rows"]:
            cat = row["category"]
            actual = float(row["actual"])
            target = float(row["target"])
            ratio = min(actual / target, 1.0) if target > 0 else 0.0

            col_p1, col_p2 = st.columns([2, 3])
            with col_p1:
                st.markdown(f"**{cat}**: {actual:.1f}h / {target:.1f}h target")
            with col_p2:
                st.progress(ratio, text=f"{actual:.1f} of {target:.1f} hours ({ratio * 100:.0f}%)")

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
        st.plotly_chart(balance_fig, use_container_width=True)


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
            "are minimums to reach; 'at most' is a limit (for example work). The "
            "score and suggestions above use these numbers."
        )
        for goal_category in goals:
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
                use_container_width=True,
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
                        st.success("Suggested activity added to plan successfully!")
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

    planner_tab_add, planner_tab_manage = st.tabs(["➕ Add a plan", "📋 Manage plans"])

    with planner_tab_add:
        with st.form("add_planned_activity_form", clear_on_submit=True):
            plan_col1, plan_col2 = st.columns(2)

            with plan_col1:
                planned_date = st.date_input(
                    "Planned date",
                    value=today,
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
                value=today - timedelta(days=7),
                key="planner_filter_from",
            )
        with range_col2:
            planner_to = st.date_input(
                "Show plans to",
                value=today + timedelta(days=30),
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
                    is_planned & (plan_rows["_start_dt"] > now_local)
                ].copy()
                completed_df = plan_rows[plan_rows["status"].eq("Completed")].copy()
                activity_failed_df = plan_rows[plan_rows["status"].eq("Failed")].copy()

                try:
                    reminder_df = load_reminder_history(planner_from, planner_to)
                except sqlite3.Error as error:
                    st.error(f"Could not load reminder history: {error}")
                    reminder_df = pd.DataFrame()

                if reminder_df.empty:
                    failed_df = pd.DataFrame()
                    sent_df = pd.DataFrame()
                else:
                    failed_df = reminder_df[reminder_df["reminder_status"].eq("Failed")].copy()
                    sent_df = reminder_df[reminder_df["reminder_status"].eq("Sent")].copy()

                def _show_plan_table(frame):
                    if frame.empty:
                        st.info("Nothing to show in this section right now.")
                        return
                    view = frame.drop(
                        columns=[c for c in ["_start_dt", "_end_dt"] if c in frame.columns]
                    ).copy()
                    view["activity_date"] = view["activity_date"].astype(str)
                    columns = ["id", "activity_date", "start_time", "end_time", "activity_type", "status", "notes"]
                    if "activity_failure_reason" in view.columns:
                        view = view.rename(columns={"activity_failure_reason": "why_failed"})
                        columns.append("why_failed")
                    st.dataframe(view[columns], use_container_width=True, hide_index=True)

                def _show_reminder_table(frame):
                    if frame.empty:
                        st.info("No notification records in this section.")
                        return
                    columns = [
                        "reminder_id",
                        "activity_id",
                        "activity_date",
                        "start_time",
                        "activity_type",
                        "channel",
                        "reminder_at",
                        "reminder_status",
                    ]
                    if "failure_reason" in frame.columns:
                        columns.append("failure_reason")
                    st.dataframe(frame[columns], use_container_width=True, hide_index=True)

                st.subheader("📌 Activity & Notification Status")
                status_tabs = st.tabs([
                    f"🟢 Active ({len(active_df)})",
                    f"📅 Upcoming ({len(upcoming_df)})",
                    f"❌ Activity Failed ({len(activity_failed_df)})",
                    f"📨 Notification Failed ({len(failed_df)})",
                    f"📨 Sent ({len(sent_df)})",
                    f"✅ Completed ({len(completed_df)})",
                ])
                with status_tabs[0]:
                    _show_plan_table(active_df)
                with status_tabs[1]:
                    _show_plan_table(upcoming_df)
                with status_tabs[2]:
                    _show_plan_table(activity_failed_df)
                    st.caption(
                        "Activity Failed means its planned end time passed while it was still marked Planned. "
                        "If you did complete it, select it below and set the status to Completed, "
                        "and its hours will be added to the dashboard."
                    )
                with status_tabs[3]:
                    _show_reminder_table(failed_df)
                    st.caption(
                        "Notification Failed applies only to the individual email, Telegram, SMS or voice attempt. "
                        "It does not change the activity status."
                    )
                with status_tabs[4]:
                    _show_reminder_table(sent_df)
                    st.caption(
                        "Sent means the provider accepted the notification request. "
                        "Check the provider dashboard for final delivery details."
                    )
                with status_tabs[5]:
                    _show_plan_table(completed_df)
                    st.caption(
                        "Completed plans are added automatically to the dashboard activity log "
                        "(duration = end time minus start time, within the 24-hour daily limit)."
                    )

                st.divider()
                st.subheader("All planned activities")
                display_plans = planned_df.copy()
                display_plans["activity_date"] = display_plans["activity_date"].astype(str)
                st.dataframe(
                    display_plans[
                        [
                            "id",
                            "activity_date",
                            "start_time",
                            "end_time",
                            "activity_type",
                            "status",
                            "notes",
                            "activity_failure_reason",
                        ]
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
                selected_plan = planned_df.loc[planned_df["id"] == selected_plan_id].iloc[0]

                selected_start = datetime.strptime(str(selected_plan["start_time"]), "%H:%M").time()
                selected_end = datetime.strptime(str(selected_plan["end_time"]), "%H:%M").time()

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
                            index=(
                                ACTIVITIES.index(selected_plan["activity_type"])
                                if selected_plan["activity_type"] in ACTIVITIES
                                else 0
                            ),
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

st.caption("Work-Life Balance Manager | Python • Streamlit • SQLite • Plotly")

st.caption(
    "Records are stored locally in SQLite on this computer. "
    "Back up the database regularly. \n"
    "\n Application developed by Virbhadra Yalsangi."
)