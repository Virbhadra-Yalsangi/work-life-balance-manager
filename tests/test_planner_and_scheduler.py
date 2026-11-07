import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import database as db
import scheduler

TZ = ZoneInfo("Asia/Kolkata")

class IsolatedDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test.db"
        db.initialize_database()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def create_future_plan(self):
        day = date.today() + timedelta(days=2)
        saved, message = db.save_planned_activity(day, "Study", "10:00", "11:00", "Test")
        self.assertTrue(saved, message)
        with db.get_connection() as conn:
            return conn.execute("SELECT id FROM planned_activities ORDER BY id DESC LIMIT 1").fetchone()[0]

class TestPlannerLifecycle(IsolatedDatabaseTest):
    def test_edit_replaces_pending_reminders_without_duplicates(self):
        activity_id = self.create_future_plan()
        new_day = date.today() + timedelta(days=3)
        updated, message = db.update_planned_activity(activity_id, new_day, "Work", "12:00", "13:00", "Updated")
        self.assertTrue(updated, message)
        with db.get_connection() as conn:
            rows = conn.execute("SELECT channel, status, reminder_at FROM reminders WHERE planned_activity_id = ? ORDER BY channel", (activity_id,)).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual([r[0] for r in rows], ["email", "sms", "voice"])
        self.assertTrue(all(r[1] == "Pending" for r in rows))
        self.assertTrue(all(new_day.isoformat() in r[2] for r in rows))

    def test_completed_plan_cancels_pending_reminders(self):
        activity_id = self.create_future_plan()
        changed, message = db.update_planned_activity_status(activity_id, "Completed")
        self.assertTrue(changed, message)
        with db.get_connection() as conn:
            rows = conn.execute("SELECT status FROM reminders WHERE planned_activity_id = ?", (activity_id,)).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row[0] == "Cancelled" for row in rows))

    def test_delete_plan_removes_reminders(self):
        activity_id = self.create_future_plan()
        self.assertTrue(db.delete_planned_activity(activity_id))
        with db.get_connection() as conn:
            plan = conn.execute("SELECT id FROM planned_activities WHERE id = ?", (activity_id,)).fetchone()
            count = conn.execute("SELECT COUNT(*) FROM reminders WHERE planned_activity_id = ?", (activity_id,)).fetchone()[0]
        self.assertIsNone(plan)
        self.assertEqual(count, 0)

    def test_invalid_time_range_is_rejected(self):
        saved, message = db.save_planned_activity(date.today() + timedelta(days=1), "Study", "11:00", "10:00")
        self.assertFalse(saved)
        self.assertIn("later", message)

class TestReminderProcessing(IsolatedDatabaseTest):
    def make_due(self):
        activity_id = self.create_future_plan()
        due_at = (datetime.now(TZ) - timedelta(minutes=1)).isoformat(timespec="seconds")
        with db.get_connection() as conn:
            conn.execute("UPDATE reminders SET reminder_at = ? WHERE planned_activity_id = ?", (due_at, activity_id))
            conn.commit()
        return activity_id

    def test_dry_run_does_not_change_status(self):
        activity_id = self.make_due()
        preview = scheduler.process_due_reminders(dry_run=True)
        self.assertEqual(len(preview), 3)
        with db.get_connection() as conn:
            statuses = conn.execute("SELECT DISTINCT status FROM reminders WHERE planned_activity_id = ?", (activity_id,)).fetchall()
        self.assertEqual(statuses, [("Pending",)])

    def test_real_processing_calls_three_mock_senders(self):
        activity_id = self.make_due()
        senders = {
            "sms": Mock(return_value=(True, "mock accepted")),
            "voice": Mock(return_value=(True, "mock accepted")),
            "email": Mock(return_value=(True, "mock accepted")),
        }
        with patch.dict("os.environ", {"NOTIFICATION_TO_PHONE": "+10000000000", "NOTIFICATION_TO_EMAIL": "test@example.invalid"}):
            results = scheduler.process_due_reminders(dry_run=False, sender_functions=senders)
        self.assertEqual(len(results), 3)
        self.assertEqual([senders[k].call_count for k in ("sms", "voice", "email")], [1, 1, 1])
        self.assertTrue(all(item["status"] == "Sent" for item in results))
        with db.get_connection() as conn:
            statuses = conn.execute("SELECT DISTINCT status FROM reminders WHERE planned_activity_id = ?", (activity_id,)).fetchall()
        self.assertEqual(statuses, [("Sent",)])

    def test_failed_senders_mark_reminders_failed(self):
        activity_id = self.make_due()
        senders = {key: Mock(return_value=(False, "mock failure")) for key in ("sms", "voice", "email")}
        with patch.dict("os.environ", {"NOTIFICATION_TO_PHONE": "+10000000000", "NOTIFICATION_TO_EMAIL": "test@example.invalid"}):
            results = scheduler.process_due_reminders(dry_run=False, sender_functions=senders)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(item["status"] == "Failed" for item in results))
        with db.get_connection() as conn:
            statuses = conn.execute("SELECT DISTINCT status FROM reminders WHERE planned_activity_id = ?", (activity_id,)).fetchall()
        self.assertEqual(statuses, [("Failed",)])

if __name__ == "__main__":
    unittest.main()
