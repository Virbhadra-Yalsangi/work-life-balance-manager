
import unittest
from datetime import date

from app import save_activity


class TestWorkLifeBalanceManager(unittest.TestCase):

    def test_save_activity_successfully(self):
        # This basic test checks that saving returns success.
        # Run integration tests against a separate test database.
        result, message = save_activity(
            date.today(),
            "Study",
            1.0,
            "Automated test",
        )

        self.assertTrue(result)
        self.assertEqual(message, "Activity saved successfully!")


if __name__ == "__main__":
    unittest.main()
