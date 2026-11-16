# Work-Life Balance Manager (v3.1)

An AI-assisted, local-first activity tracking, planning, and analytics application built with **Python, Streamlit, SQLite, pandas, Plotly, and Google Gemini AI**. It features a daily activity dashboard, smart routine planner, weekly balance scoring, energy/mood analytics, a live Pomodoro focus timer, and a two-way interactive Telegram & Email reminder system.

## Key Features

- **Activity Tracking & Energy Analytics:** Log daily activities with duration (24-hour daily validation), notes, and a **1–5 Energy/Mood rating** to analyze which routines boost or drain your energy.
- **AI Natural Language Quick-Log (`ai_coach.py`):** Type naturally in English, Marathi, or Hindi (e.g., *"Worked 4 hours on SQL and 1 hour gym"*), and Gemini 2.5 Flash parses and logs structured records automatically.
- **AI Weekly Burnout & Routine Coach:** Analyzes your last 7 days of activity logs and energy patterns to spot overwork/low-sleep trends and suggest 3 concrete improvements.
- **One-Click Routine Presets & Live Focus Timer:** Log common daily blocks (Sleep, Work, Workout, Study) in one click, or run a live countdown Pomodoro timer that auto-logs completed sessions.
- **Daily Logging Streak:** Tracks consecutive active logging days right on the dashboard header.
- **Weekly Balance Score & Smart Suggestions (`suggestions.py`):** Compares the last 7 days against customizable weekly targets (`My weekly goals`) to generate a 0–100 score and fills remaining free time today with neglected categories.
- **Advanced Planner (Overnight & Recurring Support):** Schedule single, daily, or weekday routines—including overnight sleep across midnight (e.g., `23:00` to `06:00`). Marking a plan **Completed** automatically syncs hours to the dashboard log.
- **Two-Way Interactive Telegram Bot (`telegram_bot.py`) & Multi-Channel Reminders:** Receive reminders 5 minutes before planned tasks via Telegram, Email (SendGrid), or SMS/Voice (Twilio), and tap **Mark Completed** or **Mark Missed** directly on your phone.
- **In-App Notification Settings:** Toggle active channels and send live test notifications directly from the UI without manually editing `.env`.

## Project Structure

```text
Work_Life_Balance_Manager_Ready/
├── app.py                  # Main Streamlit dashboard, AI Quick-Log, Focus Timer & Settings UI
├── database.py             # SQLite persistence, schema migrations, streak & recurring logic
├── ai_coach.py             # Gemini API natural language parser & weekly burnout coach
├── suggestions.py          # Pure-Python 0-100 weekly balance score & free-time scheduler
├── notifications.py        # SendGrid, Telegram (inline buttons) & Twilio senders
├── scheduler.py            # Background reminder worker (APScheduler)
├── telegram_bot.py         # Two-way Telegram listener for inline button actions & text logs
├── requirements.txt
├── .env.example
├── scripts/
│   └── check_notifications.py
└── tests/                  # 77 automated unit & UI tests (unittest + Streamlit AppTest)