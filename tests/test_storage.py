from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storage import MarkdownStorage


class StorageOverwriteSafetyTests(unittest.TestCase):
    def test_save_capture_uses_unique_filenames_when_timestamp_repeats(self) -> None:
        fixed_ts = datetime(2026, 4, 5, 12, 34, 56, 123456, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = MarkdownStorage(tmpdir)

            with patch("storage.datetime") as mock_datetime:
                mock_datetime.now.return_value = fixed_ts

                first = storage.save_capture("first", source="telegram_text", user_id=42)
                second = storage.save_capture("second", source="telegram_text", user_id=42)

            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertIn("20260405_123456_123456_42", first.name)
            self.assertIn("_2.md", second.name)

    def test_create_review_versions_when_same_day_file_exists(self) -> None:
        fixed_ts = datetime(2026, 4, 5, 8, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = MarkdownStorage(tmpdir)

            with patch("storage.datetime") as mock_datetime:
                mock_datetime.now.return_value = fixed_ts

                first = storage.create_review(period="daily", user_id=7)
                second = storage.create_review(period="daily", user_id=7)

            self.assertNotEqual(first, second)
            self.assertEqual(first.name, "daily_20260405_7.md")
            self.assertEqual(second.name, "daily_20260405_7_v2.md")
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())


if __name__ == "__main__":
    unittest.main()
