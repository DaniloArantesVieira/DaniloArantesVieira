"""Offline regression checks for parsing, truthful data and safe SVG output."""

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import requests

import fetch_contributions
from fetch_contributions import parse_contributions
from render_heatmap_svg import render


class ContributionTests(unittest.TestCase):
    HTML = '<td data-date="2026-10-22" data-level="1" data-count="1"/>'

    def test_equivalent_fetches_preserve_persisted_payload_and_svg(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contributions.json"
            response = Mock(text=self.HTML)
            with (patch.object(fetch_contributions, "OUTPUT", output),
                  patch.object(fetch_contributions.requests, "get", return_value=response),
                  patch.object(fetch_contributions, "datetime") as clock):
                clock.now.return_value.isoformat.return_value = "2026-10-22T09:17:00+00:00"
                fetch_contributions.main()
                original = output.read_bytes()
                original_mtime = output.stat().st_mtime_ns
                original_svg = render(json.loads(original))
                # Different HTML, same normalized days; a later run must not write.
                response.text = '<table>' + self.HTML + self.HTML + '</table>'
                clock.now.return_value.isoformat.return_value = "2026-10-23T09:17:00+00:00"
                with (patch.object(Path, "write_text", side_effect=AssertionError("Unexpected rewrite")),
                      patch("builtins.print") as printed):
                    fetch_contributions.main()
                printed.assert_called_once_with("Contribution data unchanged.")
                clock.now.assert_called_once()
                self.assertEqual(output.read_bytes(), original)
                self.assertEqual(output.stat().st_mtime_ns, original_mtime)
                self.assertEqual(render(json.loads(output.read_bytes())), original_svg)

    def test_real_data_or_username_change_refreshes_timestamp(self):
        for username, days in (("other-user", parse_contributions(self.HTML)),
                               (fetch_contributions.USERNAME, [{"date": "2026-10-22", "level": 0}])):
            with self.subTest(username=username, days=days), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "contributions.json"
                output.write_text(json.dumps({"username": username, "days": days, "fetched_at": "old"}))
                with (patch.object(fetch_contributions, "OUTPUT", output),
                      patch.object(fetch_contributions.requests, "get", return_value=Mock(text=self.HTML)),
                      patch.object(fetch_contributions, "datetime") as clock):
                    clock.now.return_value.isoformat.return_value = "new"
                    fetch_contributions.main()
                payload = json.loads(output.read_text())
                self.assertEqual(payload, {"username": fetch_contributions.USERNAME,
                                          "days": parse_contributions(self.HTML), "fetched_at": "new"})

    def test_invalid_existing_json_is_replaced_only_after_valid_fetch(self):
        for content in (b"{broken", b"[]", b"\xff"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "contributions.json"
                output.write_bytes(content)
                with (patch.object(fetch_contributions, "OUTPUT", output),
                      patch.object(fetch_contributions.requests, "get", return_value=Mock(text=self.HTML))):
                    fetch_contributions.main()
                self.assertEqual(json.loads(output.read_text())["days"], parse_contributions(self.HTML))

    def test_oserror_reading_existing_json_does_not_crash_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contributions.json"
            output.write_text("{}")
            with (patch.object(fetch_contributions, "OUTPUT", output),
                  patch.object(fetch_contributions.requests, "get", return_value=Mock(text=self.HTML)),
                  patch.object(Path, "read_text", side_effect=OSError("Read failed"))):
                fetch_contributions.main()
            self.assertEqual(json.loads(output.read_text())["days"], parse_contributions(self.HTML))

    def test_failed_fetch_does_not_replace_existing_file(self):
        for response in (Mock(text="<html>changed markup</html>"),
                         Mock(raise_for_status=Mock(side_effect=requests.HTTPError("HTTP failure")))):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "contributions.json"
                output.write_bytes(b"original data")
                with (patch.object(fetch_contributions, "OUTPUT", output),
                      patch.object(fetch_contributions.requests, "get", return_value=response)):
                    with self.assertRaises((ValueError, requests.HTTPError)):
                        fetch_contributions.main()
                self.assertEqual(output.read_bytes(), b"original data")
                self.assertFalse(output.with_suffix(".json.tmp").exists())

    def test_normalizes_orders_and_deduplicates_without_inventing_counts(self):
        html = '''<td data-date="2026-10-22" data-level="2"></td>
        <rect data-date="2026-10-21" data-level="0" data-count="0"/>
        <td data-date="2026-10-22" data-level="2"/>
        <td data-date="bad" data-level="0"/>
        <td data-date="2026-10-20" data-level="9"/>'''
        self.assertEqual(parse_contributions(html), [
            {"date": "2026-10-21", "level": 0, "count": 0},
            {"date": "2026-10-22", "level": 2},
        ])

    def test_explicit_tooltips_and_unknown_localization(self):
        html = '''<td id="a" data-date="2026-10-20" data-level="4"/>
        <tool-tip for="a">1,234 contributions on October 20th.</tool-tip>
        <td id="b" data-date="2026-10-21" data-level="0"/>
        <tool-tip for="b">No contributions on October 21st.</tool-tip>
        <td data-date="2026-10-22" data-level="1" aria-label="atividade"/>'''
        days = parse_contributions(html)
        self.assertEqual(days[0]["count"], 1234)
        self.assertEqual(days[1]["count"], 0)
        self.assertNotIn("count", days[2])

    def test_empty_or_changed_html_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "No contribution days"):
            parse_contributions("<html>unavailable</html>")

    def test_conflicting_duplicates_fail(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            parse_contributions('''<td data-date="2026-10-22" data-level="1"/>
            <td data-date="2026-10-22" data-level="2"/>''')

    def test_duplicate_preserves_available_count(self):
        days = parse_contributions('''<td data-date="2026-10-22" data-level="1" data-count="3"/>
        <td data-date="2026-10-22" data-level="1"/>''')
        self.assertEqual(days[0]["count"], 3)

    def test_svg_escapes_remote_text_and_does_not_infer_missing_days(self):
        svg = render({"username": '<script>alert("x")</script>', "fetched_at": "<&>",
                      "days": [{"date": "2026-10-22", "level": 2}]})
        root = ET.fromstring(svg)
        self.assertIsNone(root.find("{http://www.w3.org/2000/svg}script"))
        self.assertIn("&lt;script&gt;", svg)
        self.assertIn("activity level 2 of 4", svg)
        self.assertEqual(len([node for node in root.iter() if node.get("class") == "day"]), 1)

    def test_leap_calendar_keeps_all_54_weeks_in_bounds(self):
        start = date(2023, 12, 31)
        days = [{"date": (start + timedelta(days=index)).isoformat(), "level": 0}
                for index in range(372)]
        root = ET.fromstring(render({"username": "test", "fetched_at": "test", "days": days}))
        cells = [node for node in root.iter() if node.get("class") == "day"]
        self.assertEqual(len(cells), 372)
        self.assertTrue(all(float(node.get("x")) + float(node.get("width")) <= 872 for node in cells))

    def test_invalid_data_is_rejected(self):
        for days in ([], [{"date": "2026-10-22", "level": -1}],
                     [{"date": "2026-10-22", "level": 1, "count": -1}]):
            with self.assertRaises(ValueError):
                render({"username": "test", "fetched_at": "test", "days": days})


if __name__ == "__main__":
    unittest.main()
