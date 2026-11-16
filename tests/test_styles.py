import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestStyles(unittest.TestCase):
    def setUp(self):
        self.css = (ROOT / "styles.css").read_text(encoding="utf-8")

    def test_css_braces_are_balanced(self):
        self.assertEqual(self.css.count("{"), self.css.count("}"))

    def test_motion_respects_reduced_motion_setting(self):
        self.assertIn("prefers-reduced-motion", self.css)

    def test_app_loads_the_stylesheet(self):
        self.assertIn("styles.css", (ROOT / "app.py").read_text(encoding="utf-8"))

    def test_theme_file_exists(self):
        self.assertIn('base = "dark"', (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
