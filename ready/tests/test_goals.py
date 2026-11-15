import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

os.environ["ENABLED_CHANNELS"] = "sms,voice,email"  # tests must not depend on your .env

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import database as db
import suggestions as sg

TODAY = date(2026, 11, 13)


def frame(rows):
    return pd.DataFrame(rows, columns=["activity_date", "activity_type", "duration_hours"])


class TestGoalLogic(unittest.TestCase):
    def test_defaults_used_when_nothing_saved(self):
        goals = sg.merge_goals({})
        for category, (kind, hours) in sg.WEEKLY_TARGETS.items():
            self.assertEqual(goals[category], (kind, hours))

    def test_saved_value_overrides_default(self):
        goals = sg.merge_goals({"Exercise": 6})
        self.assertEqual(goals["Exercise"], ("min", 6.0))
        self.assertEqual(goals["Sleep"], sg.WEEKLY_TARGETS["Sleep"])

    def test_invalid_saved_values_fall_back_to_default(self):
        goals = sg.merge_goals({"Exercise": "abc", "Study": -3, "Leisure": 500, "Meals": float("nan"), "Bogus": 5})
        for category in ("Exercise", "Study", "Leisure", "Meals"):
            self.assertEqual(goals[category], sg.WEEKLY_TARGETS[category])
        self.assertNotIn("Bogus", goals)

    def test_validation_accepts_defaults(self):
        defaults = {c: h for c, (k, h) in sg.WEEKLY_TARGETS.items()}
        self.assertEqual(sg.validate_goals(defaults), [])

    def test_validation_rejects_out_of_range(self):
        hours = {c: h for c, (k, h) in sg.WEEKLY_TARGETS.items()}
        hours["Exercise"] = 200
        self.assertTrue(any("Exercise" in e for e in sg.validate_goals(hours)))

    def test_validation_rejects_goals_longer_than_a_week(self):
        hours = {c: 0 for c in sg.WEEKLY_TARGETS}
        hours["Sleep"] = 100
        hours["Study"] = 100
        errors = sg.validate_goals(hours)
        self.assertTrue(any("168" in e for e in errors))

    def test_work_limit_does_not_count_towards_week_total(self):
        hours = {c: 0 for c in sg.WEEKLY_TARGETS}
        hours["Work"] = 168
        hours["Sleep"] = 168
        self.assertEqual(sg.validate_goals(hours), [])

    def test_custom_goal_changes_the_gap(self):
        data = frame([(TODAY, "Exercise", 0.5)])
        default = sg.weekly_balance(data, TODAY)
        custom = sg.weekly_balance(data, TODAY, sg.merge_goals({"Exercise": 14}))
        gap = lambda r: next(x for x in r["rows"] if x["category"] == "Exercise")["gap"]
        self.assertGreater(gap(custom), gap(default))

    def test_zero_goals_do_not_crash(self):
        goals = sg.merge_goals({c: 0 for c in sg.WEEKLY_TARGETS})
        result = sg.weekly_balance(frame([(TODAY, "Work", 8), (TODAY, "Exercise", 1)]), TODAY, goals)
        self.assertIsNotNone(result["score"])

    def test_suggestions_follow_custom_goals(self):
        from datetime import datetime
        now = datetime(2026, 11, 13, 14, 0)
        data = frame([(TODAY, c, h / 7) for c, (k, h) in sg.WEEKLY_TARGETS.items()])
        goals = sg.merge_goals({"Study": 20})  # now Study is far below its goal
        weekly = sg.weekly_balance(data, TODAY, goals)
        items, _ = sg.suggest_activities(now, [], weekly, 8)
        self.assertEqual(items[0]["category"], "Study")


class TestGoalStorage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "t.db"
        db.initialize_database()

    def tearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()

    def test_nothing_saved_initially(self):
        self.assertEqual(db.load_goal_hours(), {})

    def test_save_and_load_round_trip(self):
        db.save_goal_hours({"Exercise": 5.5, "Sleep": 49})
        self.assertEqual(db.load_goal_hours(), {"Exercise": 5.5, "Sleep": 49.0})

    def test_saving_again_overwrites_without_duplicates(self):
        db.save_goal_hours({"Exercise": 5})
        db.save_goal_hours({"Exercise": 7})
        self.assertEqual(db.load_goal_hours(), {"Exercise": 7.0})

    def test_reset_removes_saved_goals(self):
        db.save_goal_hours({"Exercise": 5})
        db.reset_goal_hours()
        self.assertEqual(db.load_goal_hours(), {})

    def test_goals_survive_re_initialisation(self):
        db.save_goal_hours({"Exercise": 5})
        db.initialize_database()
        self.assertEqual(db.load_goal_hours(), {"Exercise": 5.0})


if __name__ == "__main__":
    unittest.main()
