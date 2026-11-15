# Work-Life Balance Manager: 5-minute presentation guide

## Project objective

Build a data-driven application that helps a person record how they spend their 24 hours, compare it with healthy weekly targets, and plan the free time that is left, with reminders sent to their phone.

## Business problem

People estimate their time from memory and rarely notice when work crowds out sleep, exercise or family. This application provides a structured activity log, a planner, a weekly balance score and practical suggestions, so the user can review time consistently and act on it.

## Solution and architecture

- **Streamlit** provides the user interface and interactive dashboard.
- **Python** implements application, validation and recommendation logic.
- **SQLite** stores activities, plans and reminder state locally.
- **pandas** prepares grouped summaries and the 7-day balance calculation.
- **Plotly** renders interactive charts.
- **suggestions.py** is a pure-Python module (no UI, no database) so the scoring and scheduling rules are easy to test.
- **APScheduler** drives a separate reminder worker. **SendGrid** (email) and the **Telegram Bot API** deliver reminders. **Twilio** (SMS and voice) is supported but needs a paid account for custom messages.
- **unittest** verifies database, planner, scheduler, notification and suggestion logic with mocks and temporary databases. **GitHub Actions** runs the 51 tests on every pull request.

## What makes it more than a tracker

1. **Completed plans update the dashboard automatically.** Marking a plan Completed adds its duration to the activity log, within the 24-hour daily limit, without double counting.
2. **Weekly balance score (0 to 100).** The last 7 days are compared with weekly targets per category (for example sleep minimum, work maximum). Targets scale with the number of active days, so a new user is not penalised.
3. **Smart suggestions for free time.** Free gaps between now and bedtime are found after removing planned activities. The most neglected categories are placed into those gaps at sensible times of day (no exercise at 10 pm), with a one-click Add to plan.
4. **Clear failure reasons.** A plan whose end time passes while still Planned becomes Failed with the exact time window and a hint to mark it Completed if it was done.
5. **Reliable reminders.** One reminder per enabled channel, five minutes before the start. A reminder that would arrive after the activity has begun is recorded as Missed instead of being sent.

## Suggested live demo

1. Add a sample activity such as Study for 1.5 hours and point out the KPI cards.
2. Change the date range and show how the charts respond. Download the filtered CSV.
3. Open **Balance Score & Smart Suggestions**. Explain the score, the free hours left today, and a suggestion with its reason.
4. Click **Add to plan** on a suggestion. Show the new plan in the planner.
5. Mark a plan Completed and show its hours appear in the dashboard log.
6. Show a Failed plan and its failure reason.
7. Show the email and Telegram reminders received on a phone, and explain that the scheduler must be running.

## Example explanation of the balance score

"Each category has a weekly target, such as at least 52.5 hours of sleep and at most 45 hours of work. For every category I calculate how close the last seven days are to its target, then average them into a score out of 100. Targets are scaled to the number of days that actually have data. The suggestions then place the most neglected categories into the real free gaps left in today's schedule. These are aids based on what the user logged, not measurements of their actual routine."

## Engineering decisions worth mentioning

- Recommendation rules live in a separate pure module, so they are covered by unit tests without a UI or database.
- Tests ignore the developer's personal `.env`, so they pass on any machine and in CI.
- Secrets are never committed: `.env`, databases and virtual environments are git-ignored, and error messages scrub the Telegram bot token.
- When Twilio's trial limits blocked custom SMS and voice, the system was made channel-configurable (`ENABLED_CHANNELS`) and a free Telegram channel was added, instead of leaving failing reminders.

## Honest project status statement

The application and automated tests run locally. Live email and Telegram reminders were verified by the author. Live SMS and voice were not, because Twilio trial accounts only allow template messages and restrict voice calls to the account's own country. A provider accepting a request is not the same as confirming end-user delivery. The scheduler is local, so reminders require the computer to be on and the scheduler to be running.
