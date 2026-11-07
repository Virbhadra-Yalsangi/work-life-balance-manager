# Work-Life Balance Manager: 5-minute presentation guide

## Project objective

Build a simple, data-driven application that helps a person record how they allocate time and review patterns across work, sleep, study, exercise and personal activities.

## Business problem

People often estimate how they spend their time from memory. This application provides a structured activity log, date filters, summary KPIs and visual analysis so the user can review recorded time consistently.

## Solution and architecture

- **Streamlit** provides the user interface and interactive dashboard.
- **Python** implements application and validation logic.
- **SQLite** stores activity plans and reminder state locally.
- **pandas** prepares grouped summaries and tabular reports.
- **Plotly** renders interactive charts.
- **APScheduler + Twilio + SendGrid** provide optional scheduled notifications.
- **unittest** verifies core database and reminder workflows. Reminder tests use mocks and never contact providers.

## Suggested live demo

1. Add a sample activity such as Study for 1.5 hours.
2. Point out the recorded-hours, work-hours and sleep-hours KPIs.
3. Change the dashboard date range and explain how the charts respond.
4. Show the activity allocation and trend visualizations.
5. Download the filtered CSV.
6. Add a future plan and show its three reminder records in the test environment. Explain that the reminder is set for five minutes before the start time and that the scheduler must be running.

## Example explanation of the analytics

"The dashboard summarizes the records entered by the user. The allocation chart shows each category's share of logged time, while the trend chart compares activity hours across daily, weekly or monthly periods. The data-quality section flags dates with more than 24 recorded hours and records without notes. These are checks on the entered data, not assumptions about the user's actual routine."

## Honest project status statement

The application and automated tests can be demonstrated locally. Live SMS, voice and email delivery is dependent on valid provider credentials, verified sender configuration, provider account status, network access and a continuously running scheduler. A provider accepting a request is not the same as confirming end-user delivery.
