# Work-Life Balance Manager

A local-first activity tracking and analytics application built with Python, Streamlit, SQLite, pandas and Plotly. It includes a daily activity dashboard, a planner, and an optional reminder worker that can submit SMS, voice-call and email reminders.

## Features

- Log activities by date, category, duration and notes.
- Add, edit and delete activity records.
- Enforce a maximum of 24 recorded hours per date when adding or editing.
- Filter records by date range and export the filtered records to CSV.
- Review KPI cards for recorded, work and sleep hours and average hours per active day.
- Explore activity allocation, daily activity totals and daily/weekly/monthly trends.
- Review data-quality indicators, including dates above 24 hours and missing notes.
- Plan activities with start/end times and notes.
- Edit, complete, cancel and delete planned activities.
- Generate three reminders (SMS, voice and email) five minutes before a planned activity, provided that reminder time is still in the future when the plan is saved or edited.
- Run the reminder scheduler as a separate process. It checks every 15 seconds and prints each processing result.
- Run automated database and reminder tests using isolated temporary SQLite databases and mocked notification senders.

## Technology

- Python 3.10+
- Streamlit
- SQLite
- pandas
- Plotly
- Twilio Python SDK
- SendGrid Python SDK
- python-dotenv
- APScheduler 3.x
- unittest

## Project structure

```text
Work_Life_Balance_Manager_Ready/
├── app.py
├── database.py
├── notifications.py
├── scheduler.py
├── requirements.txt
├── .env.example
├── .gitignore
├── run_app.bat
├── run_scheduler.bat
├── run_tests.bat
├── tests/
│   ├── test_database.py
│   └── test_planner_and_scheduler.py
└── data/                  # SQLite database is created here at first run
```

## Windows setup

Open this folder in VS Code. In the integrated terminal, run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, use the executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Start the application

In terminal 1:

```powershell
python -m streamlit run app.py
```

Or double-click `run_app.bat` after installing the dependencies.

## Start reminders (optional)

Reminders run in a separate process. Keep the computer awake, connected to the internet, and keep this terminal open.

In terminal 2, from the same project folder and with the virtual environment active:

```powershell
python scheduler.py
```

Or double-click `run_scheduler.bat`.

The scheduler runs a check immediately at startup and then every 15 seconds. It processes only reminders whose scheduled time has arrived and whose planned activity is still in `Planned` status. The reminder worker uses real provider APIs when it is running in normal mode. Stop it with `Ctrl+C`.

### Reminder timing and delivery notes

- A reminder is scheduled for **five minutes before** the activity start time.
- If that five-minute point has already passed when you create or edit the plan, the application does not create a late reminder for that plan.
- SMS and voice calls use Twilio. Email uses SendGrid. Provider account setup, sender verification, recipient permissions, service availability and billing can affect delivery.
- A `Sent` status means the provider API accepted the submission. It does not prove that a phone displayed the SMS, a person answered a call, or an email reached the inbox.
- `Failed` means the application did not receive a successful submission response. Review the scheduler log and provider dashboard before retrying.
- The scheduler is local. It cannot send reminders while the computer is shut down, asleep, offline or while the scheduler process is stopped.
- Do not run multiple scheduler processes against the same database.

### Configure notification credentials safely

Notifications are optional. The dashboard and planner work without provider credentials.

1. Copy `.env.example` to a new file named `.env` in the project root.
2. Add your own current Twilio and SendGrid values to `.env` locally.
3. Use provider-approved sender details and recipients.
4. Keep `.env` private. Never upload it, commit it, or share screenshots of it.

The `.gitignore` excludes `.env`, database files, virtual environments and Python caches. `.env.example` contains blank placeholders only.

## Run automated tests

Run:

```powershell
python -m unittest discover -s tests -v
```

The current package was validated with **15 passing tests**. The suite checks activity CRUD and validation, planner reminder creation/edit/status/delete behaviour, and reminder processing using mocked senders. The tests do not make real SMS messages, calls or emails and use temporary databases instead of the user's local database.

## Database and backups

The app creates `data/work_life_balance.db` automatically. Existing databases are not deleted by initialization. Back up this file before manual database maintenance or code changes that affect the schema. Do not include the database in a public repository or demo ZIP.

## Portfolio demonstration flow

1. Open the dashboard and explain the activity categories and date filters.
2. Add a sample activity and show how the KPI cards and charts respond.
3. Edit a record and demonstrate the 24-hour validation.
4. Review allocation, trend charts and data-quality checks.
5. Download a filtered CSV report.
6. Add a future planned activity, edit it, change its status, and delete a disposable test plan.
7. Explain that reminders are an optional background process and show the mocked automated tests. Only demonstrate live provider delivery if the credentials are configured securely and a controlled test is appropriate.

## Known operational limitations

- This is a local portfolio application, not a multi-user hosted service. It does not include user authentication or cloud database hosting.
- Notifications depend on third-party services and a continuously running local scheduler.
- A process interruption during an in-flight provider request can require manual reconciliation with the provider dashboard before retrying, to avoid duplicate messages.
- The dashboard reflects logged data; it does not automatically detect actual sleep, work or exercise.

## Author

**Virbhadra Yalsangi**

GitHub: https://github.com/Virbhadra-Yalsangi
