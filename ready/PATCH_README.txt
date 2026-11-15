# Work-Life Balance Manager: Independent Failed Status Patch

This patch contains replacement versions of:
- app.py
- database.py
- scheduler.py

## What changed

1. Activity status and notification status are independent.
2. Planned activities can be Planned, Completed, Failed, or Cancelled.
3. A still-Planned activity is automatically marked Failed after its planned end time.
4. The activity failure reason is stored separately in `planned_activities.activity_failure_reason`.
5. SMS, voice, and email each retain their own Pending/Sent/Failed result and notification failure reason in `reminders`.
6. The Streamlit planner displays separate tabs for Activity Failed and Notification Failed.
7. The scheduler checks overdue activities before processing due notifications.
8. Existing databases are migrated with `ALTER TABLE`; existing records are not intentionally deleted.

## Apply safely

1. Stop the Streamlit app and scheduler.
2. Back up your existing project folder and SQLite database.
3. Replace only the three matching Python files in your project with these files.
4. Keep your existing `notifications.py`, `requirements.txt`, `.env`, and database file. They are not included in this patch.
5. Restart the scheduler and Streamlit app.

Do not upload or share `.env`, API keys, Auth Tokens, or the SQLite database.

## Important behavior

An activity becomes Failed only when its end time has passed and its activity status is still Planned. Mark it Completed before the end time if it was completed. A notification failure does not change the activity status. Likewise, an activity failure does not rewrite a notification that was already Sent or Failed.

The app and scheduler use Asia/Kolkata time.
