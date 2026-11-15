import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import suggestions as sg

TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 14, 0)


def frame(rows):
    return pd.DataFrame(rows, columns=["activity_date", "activity_type", "duration_hours"])


def day(category, hours, d=TODAY):
    return (d, category, hours)


class TestWeeklyBalance(unittest.TestCase):
    def test_no_data_gives_no_score(self):
        self.assertIsNone(sg.weekly_balance(frame([]), TODAY)["score"])

    def test_meeting_all_targets_scores_100(self):
        rows = [day(cat, target) for cat, (kind, target) in sg.WEEKLY_TARGETS.items()]
        # one active day only -> targets scaled by 1/7, so log 1/7 of each
        rows = [(d, c, h / 7) for d, c, h in rows]
        result = sg.weekly_balance(frame(rows), TODAY)
        self.assertEqual(result["score"], 100)

    def test_overworking_lowers_score(self):
        balanced = [(TODAY, "Work", 6.0)]
        overworked = [(TODAY, "Work", 14.0)]
        a = sg.weekly_balance(frame(balanced), TODAY)["score"]
        b = sg.weekly_balance(frame(overworked), TODAY)["score"]
        self.assertGreater(a, b)

    def test_old_records_are_ignored(self):
        old = date(2026, 10, 1)
        result = sg.weekly_balance(frame([(old, "Work", 8)]), TODAY)
        self.assertIsNone(result["score"])

    def test_targets_scale_with_active_days(self):
        result = sg.weekly_balance(frame([day("Exercise", 0.5)]), TODAY)
        exercise = next(r for r in result["rows"] if r["category"] == "Exercise")
        self.assertAlmostEqual(exercise["target"], 4.0 / 7, places=2)


class TestFreeSlots(unittest.TestCase):
    def test_first_slot_starts_after_buffer_on_quarter_hour(self):
        slots = sg.find_free_slots(NOW, [])
        self.assertEqual(slots[0][0], datetime(2026, 11, 13, 14, 15))
        self.assertEqual(slots[-1][1], datetime(2026, 11, 13, 22, 30))

    def test_planned_activity_splits_the_day(self):
        plan = (datetime(2026, 11, 13, 16, 0), datetime(2026, 11, 13, 17, 0), "Work")
        slots = sg.find_free_slots(NOW, [plan])
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0][1], plan[0])
        self.assertEqual(slots[1][0], plan[1])

    def test_no_slots_after_bedtime(self):
        late = datetime(2026, 11, 13, 22, 20)
        self.assertEqual(sg.find_free_slots(late, []), [])

    def test_pending_hours_counts_only_future_part(self):
        plan = (datetime(2026, 11, 13, 13, 0), datetime(2026, 11, 13, 15, 0), "Work")
        self.assertAlmostEqual(sg.pending_planned_hours([plan], NOW), 1.0)

    def test_remaining_today(self):
        self.assertEqual(sg.remaining_today(20, 5), 0.0)
        self.assertEqual(sg.remaining_today(10, 2), 12.0)


class TestSuggestions(unittest.TestCase):
    def weekly(self, rows):
        return sg.weekly_balance(frame(rows), TODAY)

    def test_most_neglected_category_comes_first(self):
        weekly = self.weekly([day("Work", 8), day("Sleep", 7.5), day("Meals", 1.5),
                              day("Leisure", 1.5), day("Personal Care", 1),
                              day("Family & Friends", 1.5), day("Study", 1)])
        items, _ = sg.suggest_activities(NOW, [], weekly, 10)
        self.assertTrue(items)
        self.assertEqual(items[0]["category"], "Exercise")

    def test_suggestions_never_overlap_plans_or_each_other(self):
        weekly = self.weekly([day("Work", 8)])
        plan = (datetime(2026, 11, 13, 16, 0), datetime(2026, 11, 13, 18, 0), "Study")
        items, _ = sg.suggest_activities(NOW, [plan], weekly, 8)
        spans = sorted([(i["start"], i["end"]) for i in items] + [(plan[0], plan[1])])
        for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
            self.assertLessEqual(e1, s2)

    def test_total_never_exceeds_remaining_hours(self):
        weekly = self.weekly([day("Work", 8)])
        items, _ = sg.suggest_activities(NOW, [], weekly, 1.0)
        self.assertLessEqual(sum(i["hours"] for i in items), 1.0)

    def test_exercise_not_suggested_late_evening(self):
        weekly = self.weekly([day("Work", 8)])
        late = datetime(2026, 11, 13, 21, 15)
        items, _ = sg.suggest_activities(late, [], weekly, 5)
        self.assertNotIn("Exercise", [i["category"] for i in items])

    def test_work_overload_gives_tip_and_no_work_suggestion(self):
        weekly = self.weekly([day("Work", 14)])
        items, tips = sg.suggest_activities(NOW, [], weekly, 5)
        self.assertTrue(any("over your limit" in t for t in tips))
        self.assertNotIn("Work", [i["category"] for i in items])

    def test_fully_planned_day_returns_tip_only(self):
        weekly = self.weekly([day("Work", 8)])
        items, tips = sg.suggest_activities(NOW, [], weekly, 0)
        self.assertEqual(items, [])
        self.assertTrue(tips)

    def test_already_planned_category_is_not_suggested_again(self):
        weekly = self.weekly([day("Work", 8)])
        plan = (datetime(2026, 11, 13, 17, 0), datetime(2026, 11, 13, 20, 0), "Exercise")
        items, _ = sg.suggest_activities(NOW, [plan], weekly, 8)
        self.assertNotIn("Exercise", [i["category"] for i in items])

    def test_no_data_gives_helpful_tip(self):
        items, tips = sg.suggest_activities(NOW, [], self.weekly([]), 8)
        self.assertEqual(items, [])
        self.assertTrue(tips)


if __name__ == "__main__":
    unittest.main()
