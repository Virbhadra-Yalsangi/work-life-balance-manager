# Release notes: Work-Life Balance Manager

## Fixes in this package

- Fixed the empty-dashboard crash: the daily Plotly bar chart is now rendered only when the selected date range contains activity records.
- Added a regression test that checks the chart is both created and rendered inside the non-empty-data branch.
- Kept planner lifecycle behaviour: editing a plan replaces pending reminders, completing/cancelling a plan cancels pending reminders, and deleting a plan removes its reminder rows.
- Kept reminder processing tests isolated with mocked senders. The test suite does not send real SMS messages, voice calls or emails.

## Validation performed for this release

- Python compilation: passed.
- Automated tests: 15 passed.
- ZIP integrity check: passed.
- Package review: no `.env`, SQLite database, backup database, virtual environment or Python cache is included.

## Important operational notes

- Install dependencies from `requirements.txt` before starting the app.
- Run the Streamlit app and reminder scheduler in separate terminals.
- Real SMS, voice and email delivery remains optional and depends on your own rotated provider credentials, verified senders, provider permissions, billing and internet access.
- A provider accepting a message request is not proof of end-user delivery.
- This release was not live-tested against Twilio or SendGrid and does not include any credentials.
