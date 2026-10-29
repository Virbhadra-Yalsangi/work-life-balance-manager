# Work-Life Balance Manager

A Python-based application built with Streamlit to track daily activities, understand time allocation, and explore work-life patterns through interactive dashboards and analytics.

## Project Overview

The Work-Life Balance Manager helps users record how they spend their time across activities such as work, study, sleep, exercise, family, and personal care. It presents recorded activity data through KPIs, interactive charts, date filters, and data-quality checks.

## Features

- **Activity Tracking:** Record activity dates, categories, durations, and optional notes.
- **SQLite Database:** Store activity records locally.
- **Record Management:** Add, edit, and delete activities.
- **Time Validation:** Prevent daily recorded activity totals from exceeding 24 hours.
- **Interactive Dashboard:** Monitor recorded hours, work hours, sleep hours, and average hours per active day.
- **Data Visualization:** Explore activity distribution, time allocation, and daily, weekly, and monthly trends.
- **Date Filtering:** Analyze activities over a selected date range.
- **Data Quality Checks:** Identify dates exceeding daily limits and records with missing notes.
- **CSV Export:** Export filtered activity records.
- **Automated Testing:** Test database operations using Python's `unittest` framework.
- **Continuous Integration:** Run automated tests through GitHub Actions.

## Technology Stack

- Python
- Streamlit
- SQLite
- Pandas
- Plotly
- Git and GitHub
- GitHub Actions
- Python `unittest`

## Project Structure

```text
work-life-balance-manager/
├── .github/
│   └── workflows/
│       └── tests.yml
├── tests/
│   └── test_database.py
├── app.py
├── database.py
├── requirements.txt
├── run_tests.bat
├── .gitignore
└── README.md
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Virbhadra-Yalsangi/work-life-balance-manager.git
cd work-life-balance-manager
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Run the application

```bash
python -m streamlit run app.py
```

Open the local URL displayed in the terminal, usually `http://localhost:8501`.

## Running the Tests

Run the automated database tests with:

```bash
python -m unittest discover -s tests -v
```

The test suite covers:

1. Saving an activity
2. Updating an activity
3. Deleting an activity
4. Rejecting daily totals above 24 hours
5. Filtering records by date
6. Handling updates for nonexistent records

Six database tests passed during development. Run the command above to verify the current version.

GitHub Actions is configured to run the test suite on pushes and pull requests targeting the `main` branch.

## Data Storage and Privacy

- Activity records are stored in a local SQLite database.
- Back up your database before making structural changes.
- Do not commit database files, credentials, environment files, or personal records to GitHub.
- Review database persistence, authentication, and privacy before deploying the application publicly.

## Future Improvements

- Add a demo mode with sample activity data.
- Expand automated tests for validation and edge cases.
- Improve accessibility and mobile usability.
- Add additional time-allocation insights.
- Prepare a deployment configuration with persistent storage.

## Author

**Virbhadra Yalsangi**

- GitHub: https://github.com/Virbhadra-Yalsangi
- Repository: https://github.com/Virbhadra-Yalsangi/work-life-balance-manager
