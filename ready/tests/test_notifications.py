import sys
import tempfile
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import database as db
import notifications as n
import scheduler


class TestPhoneNormalisation(unittest.TestCase):
    def test_accepted_formats(self):
        for raw in ["+919876543210", "919876543210", "9876543210", "98765 43210", " +91 98765-43210 "]:
            self.assertEqual(n.normalize_phone(raw), "+919876543210", raw)

    def test_rejected_values(self):
        for raw in [None, "", "abc", "123", "+1234567890123456789"]:
            self.assertIsNone(n.normalize_phone(raw), raw)

    def test_other_country_keeps_its_code(self):
        self.assertEqual(n.normalize_phone("+14155552671"), "+14155552671")

    def test_sms_rejects_invalid_number_without_calling_twilio(self):
        ok, message = n.send_sms("not-a-number", "hi")
        self.assertFalse(ok)


class TestMissedReminder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "t.db"
        db.initialize_database()

    def tearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()

    def test_reminder_after_activity_start_is_not_sent(self):
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO planned_activities (activity_date, activity_type, start_time, end_time, notes, status, created_at) "
                "VALUES (?, 'Study', '00:00', '23:59', '', 'Planned', '')", (today,))
            plan_id = conn.execute("SELECT id FROM planned_activities").fetchone()[0]
            conn.execute(
                "INSERT INTO reminders (planned_activity_id, reminder_at, channel, status, created_at) "
                "VALUES (?, '2000-01-01T00:00:00+05:30', 'sms', 'Pending', '')", (plan_id,))
            conn.commit()

        calls = []
        senders = {k: (lambda *a, **kw: calls.append(a) or (True, "sent")) for k in ("sms", "voice", "email")}
        results = scheduler.process_due_reminders(dry_run=False, sender_functions=senders)

        self.assertEqual(calls, [])  # nothing was sent
        self.assertEqual(results[0]["status"], "Failed")
        self.assertIn("Missed", results[0]["response"])


if __name__ == "__main__":
    unittest.main()


class TestEnabledChannelsAndTelegram(unittest.TestCase):
    def setUp(self):
        import os
        self.os = os
        self.old = os.environ.get("ENABLED_CHANNELS")
        self.temp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "t.db"
        db.initialize_database()

    def tearDown(self):
        if self.old is None:
            self.os.environ.pop("ENABLED_CHANNELS", None)
        else:
            self.os.environ["ENABLED_CHANNELS"] = self.old
        db.DB_PATH = self.original
        self.temp.cleanup()

    def test_default_channels_unchanged(self):
        self.os.environ.pop("ENABLED_CHANNELS", None)
        self.assertEqual(db.get_enabled_channels(), ("sms", "voice", "email"))

    def test_only_enabled_channels_get_reminders(self):
        from datetime import date, timedelta
        self.os.environ["ENABLED_CHANNELS"] = "email, Telegram"
        day = date.today() + timedelta(days=2)
        db.save_planned_activity(day, "Study", "10:00", "11:00", "")
        with db.get_connection() as conn:
            channels = sorted(r[0] for r in conn.execute("SELECT channel FROM reminders"))
        self.assertEqual(channels, ["email", "telegram"])

    def test_scheduler_skips_disabled_channel_instead_of_failing(self):
        self.os.environ["ENABLED_CHANNELS"] = "email"
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO planned_activities (activity_date, activity_type, start_time, end_time, notes, status, created_at) "
                "VALUES (?, 'Study', '23:00', '23:59', '', 'Planned', '')", (today,))
            pid = conn.execute("SELECT id FROM planned_activities").fetchone()[0]
            conn.execute("INSERT INTO reminders (planned_activity_id, reminder_at, channel, status, created_at) "
                         "VALUES (?, '2000-01-01T00:00:00+05:30', 'sms', 'Pending', '')", (pid,))
            conn.commit()
        calls = []
        senders = {k: (lambda *a, **kw: calls.append(a) or (True, "ok")) for k in ("sms", "voice", "email", "telegram")}
        results = scheduler.process_due_reminders(dry_run=False, sender_functions=senders)
        self.assertEqual(calls, [])
        self.assertEqual(results[0]["status"], "Skipped")
        with db.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT status FROM reminders").fetchone()[0], "Skipped")

    def test_telegram_incomplete_config(self):
        with unittest.mock.patch.dict(self.os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            ok, msg = n.send_telegram("hi")
        self.assertFalse(ok)
        self.assertIn("incomplete", msg)

    def test_telegram_success(self):
        fake = unittest.mock.Mock(status_code=200)
        fake.json.return_value = {"ok": True}
        env = {"TELEGRAM_BOT_TOKEN": "123:ABC", "TELEGRAM_CHAT_ID": "42"}
        with unittest.mock.patch.dict(self.os.environ, env), \
             unittest.mock.patch("notifications.requests.post", return_value=fake) as post:
            ok, _ = n.send_telegram("hello")
        self.assertTrue(ok)
        self.assertEqual(post.call_args.kwargs["json"], {"chat_id": "42", "text": "hello"})

    def test_telegram_error_never_leaks_token(self):
        env = {"TELEGRAM_BOT_TOKEN": "123:SECRET", "TELEGRAM_CHAT_ID": "42"}
        boom = RuntimeError("failed for https://api.telegram.org/bot123:SECRET/sendMessage")
        with unittest.mock.patch.dict(self.os.environ, env), \
             unittest.mock.patch("notifications.requests.post", side_effect=boom):
            ok, msg = n.send_telegram("hello")
        self.assertFalse(ok)
        self.assertNotIn("SECRET", msg)
