import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ["ENABLED_CHANNELS"] = "sms,voice,email"  # tests must not depend on your .env

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

# Text that only appears when that panel is open.
PANEL_MARKERS = {
    "overview": "Today's Time Tracker",
    "analytics": "Advanced Analytics",
    "records": "Activity Records",
    "balance": "Balance Score & Smart Suggestions",
    "planner": "Activity Planner",
}


class TestHighlightCardsOpenPanels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_path = os.environ.get("WLB_DB_PATH")
        os.environ["WLB_DB_PATH"] = str(Path(cls.temp.name) / "panels.db")
        import database as db
        db.DB_PATH = Path(os.environ["WLB_DB_PATH"])
        db.initialize_database()
        db.save_activity(date.today(), "Work", 8, "")
        db.save_activity(date.today(), "Sleep", 7, "")

    @classmethod
    def tearDownClass(cls):
        if cls.old_path is None:
            os.environ.pop("WLB_DB_PATH", None)
        else:
            os.environ["WLB_DB_PATH"] = cls.old_path
        cls.temp.cleanup()

    def open_app(self):
        return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()

    def headings(self, at):
        texts = [h.value for h in at.header] + [h.value for h in at.subheader]
        return " | ".join(texts)

    def test_five_cards_each_with_an_open_button(self):
        at = self.open_app()
        self.assertFalse(at.exception)
        for key in PANEL_MARKERS:
            self.assertTrue([b for b in at.button if b.key == f"open_{key}"], key)

    def test_overview_is_open_by_default_and_only_one_panel_shows(self):
        at = self.open_app()
        shown = [k for k, marker in PANEL_MARKERS.items() if marker in self.headings(at)]
        self.assertEqual(shown, ["overview"])

    def test_clicking_each_card_opens_only_its_panel(self):
        for key, marker in PANEL_MARKERS.items():
            at = self.open_app()
            [b for b in at.button if b.key == f"open_{key}"][0].click().run()
            self.assertFalse(at.exception, key)
            shown = [k for k, m in PANEL_MARKERS.items() if m in self.headings(at)]
            self.assertEqual(shown, [key], f"after opening {key}")
            self.assertEqual(at.session_state["panel"], key)


if __name__ == "__main__":
    unittest.main()
