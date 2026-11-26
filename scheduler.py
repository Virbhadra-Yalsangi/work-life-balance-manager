import time
from apscheduler.schedulers.background import BackgroundScheduler
from notifications import process_pending_reminders
from database import mark_overdue_activities_failed, init_db

def run_scheduler_job():
    try:
        init_db()
        mark_overdue_activities_failed()
        process_pending_reminders()
        print("Scheduler heartbeat: Checked reminders and activities successfully.")
    except Exception as e:
        print(f"Error in scheduler job: {e}")

def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scheduler_job, 'interval', minutes=1)
    scheduler.start()

if __name__ == "__main__":
    init_db()
    init_scheduler()
    print("Local Background Scheduler started successfully...")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")
