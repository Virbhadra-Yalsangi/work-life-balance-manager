import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import database as db


class TestV3Features(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "v3_test.db"
        db.initialize_database()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_energy_level_saved_and_updated(self):
        today = date.today()
        ok, _ = db.save_activity(today, "Exercise", 1.5, "Morning run", energy_level=5)
        self.assertTrue(ok)
        df = db.load_activities(today, today)
        self.assertEqual(int(df.iloc[0]["energy_level"]), 5)

        rec_id = int(df.iloc[0]["id"])
        ok_upd, _ = db.update_activity(rec_id, today, "Exercise", 1.5, "Morning run", new_energy=2)
        self.assertTrue(ok_upd)
        df2 = db.load_activities(today, today)
        self.assertEqual(int(df2.iloc[0]["energy_level"]), 2)

    def test_overnight_plan_saves_and_logs_correct_hours(self):
        tomorrow = date.today() + timedelta(days=1)
        ok, msg = db.save_planned_activity(
            tomorrow, "Sleep", "23:00", "06:00", "Overnight sleep", allow_overnight=True
        )
        self.assertTrue(ok, msg)
        plans = db.load_planned_activities(tomorrow, tomorrow)
        plan_id = int(plans.iloc[0]["id"])
        db.update_planned_activity_status(plan_id, "Completed")
        logged = db.load_activities(tomorrow, tomorrow)
        self.assertEqual(float(logged.iloc[0]["duration_hours"]), 7.0)

    def test_recurring_weekdays_plan(self):
        start = date(2026, 11, 16)  # Monday
        ok, msg = db.save_recurring_planned_activities(
            start, "Work", "09:00", "17:00", "Office", repeat_mode="Weekdays (Mon-Fri)", days_count=7
        )
        self.assertTrue(ok, msg)
        plans = db.load_planned_activities(start, start + timedelta(days=6))
        self.assertEqual(len(plans), 5)

    def test_logging_streak_calculation(self):
        today = date.today()
        db.save_activity(today, "Work", 4.0, "")
        db.save_activity(today - timedelta(days=1), "Work", 4.0, "")
        db.save_activity(today - timedelta(days=2), "Work", 4.0, "")
        self.assertEqual(db.get_logging_streak(today), 3)


if __name__ == "__main__":
    unittest.main()
