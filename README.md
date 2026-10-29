from pathlib import Path
import zipfile, textwrap

base = Path("/mnt/data/work_life_balance_portfolio_pack")
(base / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

readme = r"""# Work-Life Balance Manager

A Python and Streamlit application for logging daily activities, reviewing time allocation, and exploring work-life patterns with interactive analytics.

> **Project status:** Local prototype with SQLite persistence and six passing automated database tests. This project is for learning and personal tracking; its suggestions are general prompts, not medical advice or diagnosis.

## Features

- **Activity logging:** Record a date, activity category, duration, and optional notes.
- **SQLite persistence:** Store activity records locally on the computer.
- **Record management:** Add, update, and delete activity records.
- **Daily validation:** Reject activity entries that would take a date's logged total above 24 hours.
- **Date-range review:** Filter records for a selected period.
- **Dashboard KPIs:** Review recorded hours, work hours, sleep hours, and average hours per active day where supported by the selected data.
- **Interactive analytics:** Explore time allocation percentages and daily, weekly, or other available time trends.
- **Data-quality prompts:** Highlight patterns such as dates exceeding 24 logged hours or missing notes.
- **CSV export:** Download the filtered activity report.
- **Automated tests:** Verify core database operations using a temporary test database.

## Technology stack

- Python
- Streamlit
- SQLite
- pandas
- Plotly
- Python `unittest`
- GitHub Actions (automated test workflow)

## Project structure

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

Your local database and virtual environment should not be committed to Git.

## Run locally on Windows

### 1. Install Python and Git

Install a supported Python 3 version from [python.org](https://www.python.org/downloads/windows/) and Git from [git-scm.com](https://git-scm.com/download/win).

### 2. Open the repository folder

Open the folder in VS Code, then choose **Terminal → New Terminal**.

### 3. Create and activate a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the project using the virtual environment's executable directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### 4. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 5. Launch the app

```powershell
python -m streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`, which you can open in your browser.

## Run automated tests

Tests should use a temporary SQLite database and must not be run against the database containing your personal records.

```powershell
python -m unittest discover -s tests -v
```

Or, on Windows, double-click `run_tests.bat` if it is present and configured in your local checkout.

The current test suite covers:

1. Saving an activity
2. Updating an activity
3. Deleting an activity
4. Rejecting a daily total over 24 hours
5. Filtering activities by date
6. Handling an update request for a nonexistent record

The test run recorded during development completed with **6 tests passing**. GitHub Actions is configured in this repository pack to repeat the test suite on pushes and pull requests.

## Data storage and privacy

- The app uses a local SQLite database. The database path is selected in `database.py`.
- Back up the database before making schema changes or moving the project.
- Never commit `.db`, `.sqlite`, `.env`, credentials, or virtual-environment files.
- Do not use sensitive personal data in a public demo.
- A public GitHub repository publishes source code, not a private hosted instance of the app.
- If you deploy the app, review authentication, access control, persistent storage, and privacy before collecting real users' data.

## Architecture overview

```text
User
 |
 v
Streamlit UI (app.py)
 |  form submissions, filters, charts, CSV export
 v
Database functions (database.py)
 |  validation and parameterized SQL
 v
SQLite database (local file)
```

The automated tests call the database functions using a temporary test database so test records remain isolated from normal local records.

## Known limitations and future improvements

- Add a deployment configuration with persistent storage and access controls if a hosted version is needed.
- Add broader automated tests for invalid durations, date boundaries, and update validation.
- Add a sample-data/demo mode that does not expose personal activity records.
- Add accessibility checks and verify the dashboard on desktop and mobile layouts.
- Document the database schema and expected activity categories.
- Capture a fresh dashboard screenshot and add it to the repository if you want it displayed here.

## Author

**Virbhadra Yalsangi**

- GitHub: [@Virbhadra-Yalsangi](https://github.com/Virbhadra-Yalsangi)
- Project repository: [work-life-balance-manager](https://github.com/Virbhadra-Yalsangi/work-life-balance-manager)
"""

workflow = r"""name: Python tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: requirements.txt

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt

      - name: Run unit tests
        run: python -m unittest discover -s tests -v
"""

gitignore = r"""# Python environments and cache
.venv/
venv/
__pycache__/
*.py[cod]

# Local databases and SQLite sidecar files
*.db
*.sqlite
*.sqlite3
*.db-shm
*.db-wal

# Backups and local secrets
*_backup.py
*.bak
.env
.env.*

# Editor / OS files
.vscode/
.DS_Store
Thumbs.db
"""

(base / "README.md").write_text(readme, encoding="utf-8")
(base / ".github" / "workflows" / "tests.yml").write_text(workflow, encoding="utf-8")
(base / ".gitignore").write_text(gitignore, encoding="utf-8")

zip_path = Path("/mnt/data/work_life_balance_portfolio_pack.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for p in base.rglob("*"):
        if p.is_file():
            z.write(p, p.relative_to(base))
print(f"Created: {zip_path}")
print("Files:")
for p in base.rglob("*"):
    if p.is_file():
        print(p.relative_to(base))
