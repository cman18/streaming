import unittest
from pathlib import Path

from monitor import FeedResult, confirm_recovery, parse_watchlist, restore_feed


class MonitorTests(unittest.TestCase):
    def test_parse_watchlist_preserves_labels_and_urls(self):
        path = Path(self.id().replace(".", "_") + ".md")
        try:
            path.write_text("| Previous name | Stream URL |\n|---|---|\n| USA 2 576p | https://example.test/a.m3u8 |\n", encoding="utf-8")
            self.assertEqual(parse_watchlist(path), [("USA 2 576p", "https://example.test/a.m3u8")])
        finally:
            path.unlink(missing_ok=True)

    def test_confirm_recovery_requires_consecutive_successes(self):
        history = {"successes": 1, "failures": 0, "last_status": "ok"}
        self.assertFalse(confirm_recovery(history, FeedResult(ok=True), required=2))
        history["successes"] = 2
        self.assertTrue(confirm_recovery(history, FeedResult(ok=True), required=2))

    def test_restore_feed_replaces_archived_number_without_duplicates(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            playlist = Path(directory) / "playlist.m3u"
            playlist.write_text('#EXTM3U\n#EXTINF:-1 tvg-chno="1" channel-number="1",USA 1 1080p\nhttps://active.test/a.m3u8\n', encoding="utf-8")
            self.assertTrue(restore_feed(playlist, "USA 2 576p", "https://example.test/a.m3u8", 2))
            text = playlist.read_text(encoding="utf-8")
            self.assertIn('tvg-chno="2" channel-number="2",USA 2 576p', text)
            self.assertEqual(text.count("https://example.test/a.m3u8"), 1)
            self.assertFalse(restore_feed(playlist, "USA 2 576p", "https://example.test/a.m3u8", 2))
