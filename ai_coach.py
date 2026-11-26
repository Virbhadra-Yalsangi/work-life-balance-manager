import pandas as pd


def get_ai_weekly_coach_insights(week_df, total_hours, work_hours, sleep_hours, balance_score):
    """Generates reliable local health and productivity coaching insights from weekly activity logs."""
    if week_df is None or not isinstance(week_df, pd.DataFrame) or week_df.empty:
        return (
            "### 📋 Weekly Routine Summary\n"
            "- **Status:** No activity logs found for the past 7 days.\n"
            "- **Next Step:** Log your daily Work, Sleep, Exercise, and personal hours using the sidebar or quick presets to unlock tailored weekly recommendations."
        )

    active_days = int(week_df["activity_date"].nunique()) if "activity_date" in week_df.columns else 1
    active_days = max(active_days, 1)

    avg_work_day = work_hours / active_days
    avg_sleep_day = sleep_hours / active_days

    exercise_hours = (
        float(week_df.loc[week_df["activity_type"] == "Exercise", "duration_hours"].sum())
        if "activity_type" in week_df.columns and "duration_hours" in week_df.columns
        else 0.0
    )
    leisure_hours = (
        float(week_df.loc[week_df["activity_type"] == "Leisure", "duration_hours"].sum())
        if "activity_type" in week_df.columns and "duration_hours" in week_df.columns
        else 0.0
    )

    if balance_score >= 75:
        assessment = (
            f"Your routine looks well-structured this week with a balance score of **{balance_score} / 100** "
            f"across **{active_days}** active day(s)."
        )
    elif balance_score >= 45:
        assessment = (
            f"Your routine shows moderate balance (**{balance_score} / 100**), with room to tighten "
            f"recovery and consistency across **{active_days}** active day(s)."
        )
    else:
        assessment = (
            f"Your balance score is **{balance_score} / 100**, indicating notable strain or uneven "
            f"time allocation over the last 7 days."
        )

    strengths = []
    if avg_sleep_day >= 7.0:
        strengths.append(f"Consistent sleep average of **{avg_sleep_day:.1f} h/day** supporting mental recovery.")
    if exercise_hours >= 3.0:
        strengths.append(f"Strong physical activity with **{exercise_hours:.1f} h** of exercise logged.")
    if total_hours >= 40.0:
        strengths.append(f"Solid tracking discipline with **{total_hours:.1f} h** total logged time.")
    if not strengths:
        strengths.append(f"Active tracking maintained across **{active_days}** day(s) (**{total_hours:.1f} h** logged).")

    improvements = []
    if avg_work_day > 8.5:
        improvements.append(
            f"**High Work Load:** Averaging **{avg_work_day:.1f} h/day** of work raises fatigue and burnout risk."
        )
    if avg_sleep_day < 7.0:
        improvements.append(
            f"**Sleep Deficit:** Averaging **{avg_sleep_day:.1f} h/day** of sleep is below the 7h+ recovery mark."
        )
    if exercise_hours < 2.5:
        improvements.append(
            f"**Low Exercise:** Only **{exercise_hours:.1f} h** of exercise logged; aim for short daily movement sessions."
        )
    if leisure_hours < 2.0:
        improvements.append(
            f"**Limited Downtime:** Only **{leisure_hours:.1f} h** of leisure logged to decompress."
        )
    if not improvements:
        improvements.append("No major workload or recovery red flags detected; keep protecting your rest windows.")

    actions = [
        "Set a hard stop time for work blocks and take a 10-minute screen break every 60–90 minutes.",
        "Lock in a consistent wind-down routine before sleep to protect next-day focus.",
        "Schedule a short daily slot for Exercise or Personal Care before evening fatigue sets in.",
    ]

    strengths_md = "\n".join(f"- {item}" for item in strengths)
    improvements_md = "\n".join(f"- {item}" for item in improvements)
    actions_md = "\n".join(f"- {item}" for item in actions)

    return (
        f"### 🌟 Overall Assessment\n{assessment}\n\n"
        f"### ⚡ Strengths\n{strengths_md}\n\n"
        f"### ⚠️ Areas of Improvement / Burnout Risk\n{improvements_md}\n\n"
        f"### 🎯 Actionable Advice\n{actions_md}"
    )