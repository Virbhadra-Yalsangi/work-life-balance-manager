# Release notes: Work-Life Balance Manager

```markdown
## Version 3.1

### Added
- **AI Natural Language Quick-Log & Weekly Burnout Coach (`ai_coach.py`):** Integrated Google Gemini (`gemini-2.5-flash`) to parse multilingual free-text activity logs and provide personalized 7-day burnout and energy insights.
- **Energy & Mood Tracking:** Added 1–5 energy ratings per activity with an average energy comparison chart in Advanced Analytics.
- **Live Focus / Pomodoro Timer & One-Click Presets:** Added sidebar countdown timer with automatic dashboard logging and quick-preset buttons for daily routines.
- **Daily Logging Streak:** Added consecutive-day logging streak counter in the dashboard header.
- **Overnight & Recurring Plans:** Added support for past-midnight schedules (e.g., `23:00` to `06:00`) and Daily/Weekday recurring plan creation.
- **Two-Way Interactive Telegram Bot (`telegram_bot.py`):** Added inline `Mark Completed` / `Mark Missed` buttons on Telegram reminders and free-text logging via Telegram chat.
- **In-App Notification Settings:** Configure active reminder channels and send test Telegram/Email alerts directly from the UI.
- **Automated Tests:** Added 4 new tests in `tests/test_v3_features.py` (77 passing tests in total).

## Version 2.3

### Changed
- **New look.** Dark glass theme, gradient highlight cards with hover lift, pulsing active card, fade-in charts, rounded pill buttons, styled tabs and a shared chart palette. Styling lives in `styles.css` and `.streamlit/config.toml`; animations respect the reduced-motion setting.
- The balance score card no longer shows a misleading up arrow.
- 4 new tests (73 in total) cover the stylesheet and theme.

## Version 2.2

### Changed
- **One-screen dashboard.** Five clickable highlight cards (Overview, Analytics, Records, Balance, Planner) replace the long scrolling page. Clicking a card opens only that panel; the cards always show the key numbers.
- 3 new tests (69 in total) check that each card opens only its own panel.

## Version 2.1

### Added
- **My weekly goals** screen: set hours per week for each category in the app. Saved in the database, validated, resettable to defaults, and used by the balance score and suggestions.
- 15 new tests (66 in total) covering goal merging, validation, scoring with custom goals and storage.

### Fixed
- Scoring no longer divides by zero when a goal is set to 0 hours.

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
