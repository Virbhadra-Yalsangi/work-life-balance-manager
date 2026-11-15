"""
Weekly balance score and smart "what should I do with my free time" logic.

This module is plain Python (no Streamlit, no database), so it is easy to test.
app.py loads the data and passes it in.

How it works
------------
1. WEEKLY_TARGETS says how many hours per week each life area should get
   ("min" = try to reach it, "max" = try not to exceed it, e.g. Work).
2. weekly_balance() compares the last 7 days of logged activities with those
   targets and gives a 0-100 score.
3. find_free_slots() finds the gaps left today between now and bedtime,
   after removing activities that are already planned.
4. suggest_activities() puts the most neglected categories into those gaps,
   respecting sensible times of day (no exercise at 10 pm, etc.).
"""

from datetime import date, datetime, time, timedelta

import pandas as pd

# Hours per 7 days. ("min", x) = aim for at least x. ("max", x) = aim for at most x.
# Edit these numbers to match your own life; nothing else needs to change.
WEEKLY_TARGETS = {
    "Sleep": ("min", 52.5),             # 7.5 h a night
    "Work": ("max", 45.0),
    "Exercise": ("min", 4.0),
    "Family & Friends": ("min", 10.0),
    "Leisure": ("min", 10.0),
    "Personal Care": ("min", 7.0),
    "Meals": ("min", 10.5),             # 1.5 h a day
    "Study": ("min", 5.0),
}

MAX_WEEKLY_HOURS = 168  # hours in a week


def merge_goals(saved):
    """
    Combine the user's saved weekly hours with the defaults.

    `saved` is {category: hours}. Missing, invalid or out-of-range values fall
    back to the default. Returns {category: (kind, hours)} for every category.
    """
    saved = saved or {}
    goals = {}
    for category, (kind, default_hours) in WEEKLY_TARGETS.items():
        try:
            hours = float(saved.get(category))
        except (TypeError, ValueError):
            hours = None
        if hours is None or hours != hours or not 0 <= hours <= MAX_WEEKLY_HOURS:
            hours = default_hours
        goals[category] = (kind, round(hours, 2))
    return goals


def validate_goals(hours_by_category):
    """Return a list of problems with the goals (empty list = valid)."""
    errors = []
    minimum_total = 0.0
    for category, (kind, _) in WEEKLY_TARGETS.items():
        hours = hours_by_category.get(category)
        if hours is None or not 0 <= hours <= MAX_WEEKLY_HOURS:
            errors.append(f"{category}: enter hours between 0 and {MAX_WEEKLY_HOURS}.")
            continue
        if kind == "min":
            minimum_total += hours
    if minimum_total > MAX_WEEKLY_HOURS:
        errors.append(
            f"Your 'at least' goals add up to {minimum_total:.1f} h, but a week "
            f"only has {MAX_WEEKLY_HOURS} h. Lower some goals."
        )
    return errors


# Typical length (hours) of one session of each category.
SESSION_HOURS = {
    "Exercise": 0.75,
    "Family & Friends": 1.0,
    "Leisure": 1.0,
    "Personal Care": 0.5,
    "Meals": 0.75,
    "Study": 1.0,
}

# Sensible time of day for each category ("HH:MM", "HH:MM").
PREFERRED_WINDOWS = {
    "Exercise": ("05:00", "21:00"),
    "Family & Friends": ("16:00", "22:30"),
    "Leisure": ("08:00", "22:30"),
    "Personal Care": ("06:00", "22:30"),
    "Meals": ("07:00", "21:30"),
    "Study": ("06:00", "21:00"),
}

BEDTIME = "22:30"          # suggestions never run past this
START_BUFFER_MINUTES = 10  # first suggestion starts at least this far from now
MIN_SLOT_MINUTES = 30      # ignore gaps shorter than this
MIN_DEFICIT_HOURS = 0.25   # ignore tiny shortfalls


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _at(day, hhmm):
    """Combine a date and an 'HH:MM' string into a datetime."""
    return datetime.combine(day, time.fromisoformat(hhmm))


def _round_up_15(moment):
    moment = moment.replace(second=0, microsecond=0)
    return moment + timedelta(minutes=(-moment.minute) % 15)


def _hours(delta):
    return delta.total_seconds() / 3600


# --------------------------------------------------------------------------
# Weekly balance score
# --------------------------------------------------------------------------

def weekly_balance(activities_df, today, targets=None):
    """
    Compare the last 7 days (including today) with WEEKLY_TARGETS.

    Targets are scaled by the number of days that actually have records, so a
    new user with 2 days of data is not punished for the other 5 days.
    `targets` is {category: (kind, weekly_hours)}; it defaults to WEEKLY_TARGETS
    (use merge_goals() to apply the user's own goals).
    Returns a dict with: score (0-100 or None), label, active_days, rows.
    """
    window_start = today - timedelta(days=6)
    totals = {}
    active_days = 0

    if activities_df is not None and not activities_df.empty:
        frame = activities_df.copy()
        frame["activity_date"] = pd.to_datetime(frame["activity_date"]).dt.date
        frame = frame[
            (frame["activity_date"] >= window_start)
            & (frame["activity_date"] <= today)
        ]
        active_days = int(frame["activity_date"].nunique())
        totals = frame.groupby("activity_type")["duration_hours"].sum().to_dict()

    if active_days == 0:
        return {"score": None, "label": "No data yet", "active_days": 0, "rows": []}

    scale = active_days / 7
    rows = []
    for category, (kind, weekly_target) in (targets or WEEKLY_TARGETS).items():
        target = weekly_target * scale
        actual = float(totals.get(category, 0.0))
        if kind == "min":
            ratio = 1.0 if target <= 0 else min(actual / target, 1.0)
            gap, excess = max(target - actual, 0.0), 0.0
        else:  # "max"
            excess = max(actual - target, 0.0)
            if excess == 0:
                ratio = 1.0
            elif target <= 0:
                ratio = 0.0
            else:
                ratio = max(0.0, 1.0 - excess / target)
            gap = 0.0
        rows.append(
            {
                "category": category,
                "kind": kind,
                "target": round(target, 2),
                "actual": round(actual, 2),
                "ratio": ratio,
                "gap": round(gap, 2),
                "excess": round(excess, 2),
            }
        )

    score = round(100 * sum(r["ratio"] for r in rows) / len(rows))
    if score >= 80:
        label = "Well balanced"
    elif score >= 60:
        label = "Fairly balanced"
    elif score >= 40:
        label = "Needs attention"
    else:
        label = "Out of balance"
    return {"score": score, "label": label, "active_days": active_days, "rows": rows}


# --------------------------------------------------------------------------
# Today's free time
# --------------------------------------------------------------------------

def planned_windows_today(plans_df, now):
    """
    Turn today's still-upcoming 'Planned' rows into (start, end) datetimes.
    Rows whose end time has already passed are ignored.
    """
    windows = []
    if plans_df is None or plans_df.empty:
        return windows
    for _, plan in plans_df.iterrows():
        if str(plan["status"]) != "Planned":
            continue
        day = pd.to_datetime(plan["activity_date"]).date()
        if day != now.date():
            continue
        start = _at(day, str(plan["start_time"]))
        end = _at(day, str(plan["end_time"]))
        if end > now:
            windows.append((start, end, str(plan["activity_type"])))
    return windows


def pending_planned_hours(windows, now):
    """Hours of today's planned activities that are still ahead of us."""
    return sum(_hours(end - max(start, now)) for start, end, *_ in windows)


def find_free_slots(
    now,
    windows,
    bedtime=BEDTIME,
    buffer_minutes=START_BUFFER_MINUTES,
    min_minutes=MIN_SLOT_MINUTES,
):
    """Gaps between (now + buffer) and bedtime that no planned activity uses."""
    start = _round_up_15(now + timedelta(minutes=buffer_minutes))
    end = _at(now.date(), bedtime)
    if start >= end:
        return []

    busy = sorted(
        (max(w[0], start), min(w[1], end))
        for w in windows
        if w[1] > start and w[0] < end
    )
    minimum = timedelta(minutes=min_minutes)
    slots, cursor = [], start
    for busy_start, busy_end in busy:
        if busy_start - cursor >= minimum:
            slots.append((cursor, busy_start))
        cursor = max(cursor, busy_end)
    if end - cursor >= minimum:
        slots.append((cursor, end))
    return slots


def remaining_today(logged_hours, pending_hours):
    """Hours of today that are neither logged nor already planned."""
    return max(0.0, 24.0 - float(logged_hours) - float(pending_hours))


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------

def _place(slots, day, category, hours):
    """
    Find the first free slot that can hold `category` inside its preferred
    time window. Returns (start, end, new_slots) or None.
    """
    window_start, window_end = PREFERRED_WINDOWS.get(category, ("00:00", BEDTIME))
    window_start, window_end = _at(day, window_start), _at(day, window_end)
    wanted = timedelta(hours=hours)
    minimum = timedelta(minutes=MIN_SLOT_MINUTES)

    for index, (slot_start, slot_end) in enumerate(slots):
        start = _round_up_15(max(slot_start, window_start))
        end_limit = min(slot_end, window_end)
        if end_limit - start < minimum:
            continue
        end = start + min(wanted, end_limit - start)
        new_slots = slots[:index]
        if start - slot_start >= minimum:
            new_slots.append((slot_start, start))
        if slot_end - end >= minimum:
            new_slots.append((end, slot_end))
        new_slots.extend(slots[index + 1:])
        return start, end, new_slots
    return None


def suggest_activities(now, windows, weekly, remaining_hours, max_suggestions=4):
    """
    Recommend what to do with today's free time.

    Returns (suggestions, tips):
      suggestions - list of dicts (category, start, end, hours, reason) that
                    can be added to the planner in one click.
      tips        - plain-text advice that cannot be scheduled as one block.
    """
    tips = []
    suggestions = []
    rows = {r["category"]: r for r in weekly.get("rows", [])}

    if weekly.get("score") is None:
        tips.append(
            "Log a few activities first. Suggestions are based on how your "
            "recent days compare with your weekly targets."
        )
        return suggestions, tips

    work = rows.get("Work")
    if work and work["excess"] > 0:
        tips.append(
            f"Work is {work['excess']:.1f} h over your limit for these days. "
            "Avoid scheduling more work and protect your evening."
        )
    sleep = rows.get("Sleep")
    if sleep and sleep["gap"] >= 1:
        tips.append(
            f"Sleep is {sleep['gap']:.1f} h below target. Try to be in bed by "
            f"{BEDTIME}."
        )

    if remaining_hours <= 0:
        tips.append("Today is already fully logged or planned. Nothing to add.")
        return suggestions, tips

    slots = find_free_slots(now, windows)
    if not slots:
        tips.append("No free gap of 30 minutes or more is left before bedtime today.")
        return suggestions, tips

    # Hours of each category already planned for the rest of today.
    planned = {}
    for start, end, category in windows:
        planned[category] = planned.get(category, 0.0) + _hours(end - start)

    needs = []
    for category in SESSION_HOURS:
        row = rows.get(category)
        if not row or row["kind"] != "min":
            continue
        deficit = row["gap"] - planned.get(category, 0.0)
        if deficit >= MIN_DEFICIT_HOURS:
            needs.append((deficit / max(row["target"], 0.01), deficit, category))
    needs.sort(reverse=True)  # most neglected first

    budget = remaining_hours
    for _, deficit, category in needs:
        if len(suggestions) >= max_suggestions or budget < 0.5:
            break
        hours = min(SESSION_HOURS[category], deficit, budget)
        hours = max(0.5, round(hours * 4) / 4)
        placed = _place(slots, now.date(), category, hours)
        if not placed:
            continue
        start, end, slots = placed
        actual_hours = _hours(end - start)
        budget -= actual_hours
        row = rows[category]
        suggestions.append(
            {
                "category": category,
                "start": start,
                "end": end,
                "hours": round(actual_hours, 2),
                "reason": (
                    f"{category}: {row['actual']:.1f} h logged vs "
                    f"{row['target']:.1f} h target for your last "
                    f"{weekly['active_days']} active day(s)."
                ),
            }
        )

    if not suggestions and not tips:
        tips.append(
            "You are on track with every weekly target. Enjoy your free time!"
        )
    return suggestions, tips
