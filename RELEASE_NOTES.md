# Release notes: Work-Life Balance Manager

## Version 2

### Added
- **Completed plans update the dashboard.** Marking a plan Completed adds its hours to the activity log (within the 24-hour limit). Changing the status back or editing the plan updates that record; deleting a plan keeps the logged hours.
- **Weekly balance score and smart suggestions** (`suggestions.py`): 0-100 score from the last 7 days, free-time detection, and one-click **Add to plan** suggestions.
- **Telegram reminders** (free) as a new channel, plus `ENABLED_CHANNELS` in `.env` to choose which channels get reminders. Disabled channels are marked Skipped.
- **Go-live checker** `scripts/check_notifications.py`: validates `.env` without printing secrets, sends test email/Telegram/SMS/voice, shows real Twilio delivery status, and finds your Telegram chat id.
- `setup.bat` one-click setup and `.env.example`.

### Changed
- Failed plans now explain why (planned window and a hint to mark Completed).
- Phone numbers are normalised (`98765 43210` and `+91...` both work).
- A reminder that would arrive after the activity already started is recorded as Missed instead of being sent.
- The `.env` file is always loaded from the project folder.

### Fixed
- Tests no longer depend on the developer's own `.env`.
- Twilio trial restrictions are documented (custom SMS and voice need a paid account).

### Validation
- Python compilation: passed.
- Automated tests: 51 passed locally and in GitHub Actions.
- Live email and Telegram reminders verified by the author. Live SMS and voice not verified (Twilio trial limits).

## Version 1

- Dashboard, planner, reminder scheduler and 15 automated tests.
- Fixed the empty-dashboard crash so the daily bar chart renders only when the selected range has records.
