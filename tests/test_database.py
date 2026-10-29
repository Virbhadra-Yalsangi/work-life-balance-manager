
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

# Make database.py importable from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import database as db


class TestActivityDatabase(unittest.TestCase):

    def setUp(self):
        # Every test gets its own temporary database.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH

        db.DB_PATH = Path(self.temp_dir.name) / "test_activities.db"
        db.initialize_database()

        self.today = date(2026, 10, 29)

    def tearDown(self):
        # Restore the original database path.
        db.DB_PATH = self.original_db_path

        # Remove the temporary test database.
        self.temp_dir.cleanup()

    def test_save_activity(self):
        saved, message = db.save_activity(
            self.today, "Study", 1.0, "Test record"
        )

        self.assertTrue(saved)
        self.assertEqual(message, "Activity saved successfully!")
        self.assertEqual(db.get_daily_total(self.today), 1.0)

    def test_update_activity(self):
        db.save_activity(self.today, "Study", 1.0, "Original")

        records = db.load_activities(self.today, self.today)
        record_id = int(records.iloc[0]["id"])

        updated, message = db.update_activity(
            record_id, self.today, "Work", 2.0, "Updated"
        )

        self.assertTrue(updated)
        self.assertEqual(db.get_daily_total(self.today), 2.0)

        records = db.load_activities(self.today, self.today)
        self.assertEqual(records.iloc[0]["activity_type"], "Work")
        self.assertEqual(records.iloc[0]["notes"], "Updated")

    def test_delete_activity(self):
        db.save_activity(self.today, "Study", 1.0, "Delete test")

        records = db.load_activities(self.today, self.today)
        record_id = int(records.iloc[0]["id"])

        self.assertTrue(db.delete_activity(record_id))
        self.assertEqual(db.get_daily_total(self.today), 0.0)

    def test_daily_limit_rejects_excess_hours(self):
        db.save_activity(self.today, "Work", 23.0, "Existing")

        saved, message = db.save_activity(
            self.today, "Study", 2.0, "Should be rejected"
        )

        self.assertFalse(saved)
        self.assertIn("exceed 24 hours", message)
        self.assertEqual(db.get_daily_total(self.today), 23.0)

    def test_date_filter(self):
        yesterday = self.today - timedelta(days=1)

        db.save_activity(yesterday, "Study", 1.0, "Yesterday")
        db.save_activity(self.today, "Work", 2.0, "Today")

        records = db.load_activities(self.today, self.today)

        self.assertEqual(len(records), 1)
        self.assertEqual(records.iloc[0]["activity_type"], "Work")

    def test_missing_record_cannot_be_updated(self):
        updated, message = db.update_activity(
            99999, self.today, "Work", 1.0, "Missing"
        )

        self.assertFalse(updated)
        self.assertEqual(message, "Record not found. Refresh and try again.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
