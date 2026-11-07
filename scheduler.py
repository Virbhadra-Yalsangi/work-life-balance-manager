
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from database import get_connection
from notifications import send_sms, send_voice_call, send_email


TIMEZONE = ZoneInfo("Asia/Kolkata")
CHECK_INTERVAL_SECONDS = 15


def process_due_reminders(dry_run=True, sender_functions=None):
    """
    Find reminders that are due.

    dry_run=True:
        Preview reminders without sending or changing database records.

    dry_run=False:
        Claim due reminders, send notifications and update their status.
    """

    now = datetime.now(TIMEZONE)

    with get_connection() as conn:
        reminders = conn.execute(
            """
            SELECT
                r.id,
                r.planned_activity_id,
                r.reminder_at,
                r.channel,
                p.activity_date,
                p.activity_type,
                p.start_time
            FROM reminders r
            INNER JOIN planned_activities p
                ON r.planned_activity_id = p.id
            WHERE r.status = 'Pending'
              AND p.status = 'Planned'
            ORDER BY r.reminder_at
            """
        ).fetchall()

    due_reminders = []

    for reminder in reminders:
        try:
            reminder_time = datetime.fromisoformat(reminder[2])

            if reminder_time.tzinfo is None:
                reminder_time = reminder_time.replace(
                    tzinfo=TIMEZONE
                )
            else:
                reminder_time = reminder_time.astimezone(TIMEZONE)

            if reminder_time <= now:
                due_reminders.append(reminder)

        except (ValueError, TypeError):
            continue

    if dry_run:
        return [
            {
                "reminder_id": reminder[0],
                "activity": reminder[5],
                "channel": reminder[3],
                "reminder_at": reminder[2]
            }
            for reminder in due_reminders
        ]

    senders = sender_functions or {
        "sms": send_sms,
        "voice": send_voice_call,
        "email": send_email
    }

    results = []

    for reminder in due_reminders:
        reminder_id = reminder[0]
        activity_id = reminder[1]
        channel = reminder[3]

        # Claim the reminder to prevent concurrent duplicate processing.
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE reminders
                SET status = 'Processing'
                WHERE id = ?
                  AND status = 'Pending'
                  AND EXISTS (
                      SELECT 1
                      FROM planned_activities
                      WHERE id = ?
                        AND status = 'Planned'
                  )
                """,
                (reminder_id, activity_id)
            )

            conn.commit()

            if cursor.rowcount == 0:
                continue

        activity_name = reminder[5]
        activity_date = reminder[4]
        activity_start = reminder[6]

        message = (
            f"Activity reminder. Your {activity_name} activity "
            f"starts at {activity_start} on {activity_date}."
        )

        try:
            if channel == "sms":
                success, response = senders["sms"](
                    os.getenv("NOTIFICATION_TO_PHONE"),
                    message
                )

            elif channel == "voice":
                success, response = senders["voice"](
                    os.getenv("NOTIFICATION_TO_PHONE"),
                    message
                )

            elif channel == "email":
                success, response = senders["email"](
                    os.getenv("NOTIFICATION_TO_EMAIL"),
                    "Upcoming Activity Reminder",
                    message
                )

            else:
                success = False
                response = f"Unsupported channel: {channel}"

        except Exception as error:
            success = False
            response = str(error)

        final_status = "Sent" if success else "Failed"
        sent_time = (
            datetime.now(TIMEZONE).isoformat(timespec="seconds")
            if success else None
        )

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET status = ?,
                    sent_at = ?,
                    failure_reason = ?
                WHERE id = ?
                  AND status = 'Processing'
                """,
                (
                    final_status,
                    sent_time,
                    "" if success else str(response)[:500],
                    reminder_id,
                )
            )

            conn.commit()

        results.append({
            "reminder_id": reminder_id,
            "channel": channel,
            "status": final_status,
            "response": response
        })

    return results


def start_scheduler():
    """Start checking for due reminders every 15 seconds."""

    scheduler = BlockingScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        process_due_reminders,
        trigger="interval",
        seconds=CHECK_INTERVAL_SECONDS,
        id="activity_reminder_scheduler",
        kwargs={"dry_run": False},
        max_instances=1,
        coalesce=True
    )

    print("Activity reminder scheduler started.")
    print("Timezone: Asia/Kolkata")
    print(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
    print("Press Ctrl+C to stop.")

    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
