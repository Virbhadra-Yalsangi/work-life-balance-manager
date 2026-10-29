# Work-Life Balance Manager

Beginner-friendly local app for activity logging, time analysis, rule-based prompts, charts, and CSV export.

## Run on Windows
1. Install Python from https://www.python.org/downloads/windows/
2. Open this folder in VS Code.
3. Open Terminal > New Terminal.
4. Run:
   ```powershell
   python -m venv .venv
   .venv\\Scripts\\python.exe -m pip install -r requirements.txt
   .venv\\Scripts\\python.exe -m streamlit run app.py
   ```
   If `python` is not recognized, try `py` for the first command.

## Features
- Add activities with date, category, duration, and notes.
- Store records in a local SQLite database (`data/work_life_balance.db`).
- Filter activity records by date.
- View KPI cards and interactive charts.
- Receive simple rule-based prompts.
- Download filtered records as CSV.

## Next improvements
- Add edit/delete controls and validations for daily totals.
- Add weekly/monthly summaries.
- Add tests, documentation, and a data dictionary.
- Add PDF export if required.
- Review privacy and security before any public deployment.

Suggestions are general prompts based on logged data, not medical advice or diagnosis.
