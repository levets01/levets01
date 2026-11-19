from datetime import date, timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import URLError
import xml.etree.ElementTree as ET

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_github_data import calendar_snapshot, refresh, repository_snapshot
from generate_cards import contributions, hero, project, technology
from generate_portrait import GRID, make_rows, portrait_svg, source_image
from validate_profile import validate


class ProfileTests(unittest.TestCase):
    def test_calendar_uses_real_levels_and_total(self):
        start = date(2025, 1, 1)
        html = '<h2 id="js-contribution-activity-description">\n1,234\n contributions in the last year</h2>'
        html += "".join(f'<td data-date="{start + timedelta(days=i)}" data-level="{i % 5}"></td>'
                        for i in range(365))
        calendar = calendar_snapshot(html)
        self.assertEqual(calendar["total"], 1234)
        self.assertEqual(calendar["days"]["2025-01-02"], 1)
        ET.fromstring(contributions({"calendar": calendar}))

    def test_calendar_rejects_partial_response(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            calendar_snapshot('<td data-date="2025-01-01" data-level="0"></td>')

    def test_preserves_last_snapshot_on_network_error(self):
        snapshot = {"repositories": {"public_repos": 5}, "activity": [], "calendar": {}}
        with patch("fetch_github_data.download", side_effect=URLError("test failure")):
            self.assertEqual(refresh(snapshot.copy()), snapshot)

    def test_repository_metrics_exclude_forks(self):
        user = {"public_repos": 2, "followers": 0}
        repos = [{"name": "original", "fork": False, "language": "Python", "stargazers_count": 2},
                 {"name": "fork", "fork": True, "language": "Go", "stargazers_count": 8}]
        result = repository_snapshot(user, repos)
        self.assertEqual(result["stars"], 2)
        self.assertEqual(result["languages"], {"Python": 1})

    def test_portrait_pipeline_and_svg_validation(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            assets = directory / "asset"
            assets.mkdir()
            path = assets / "IMG_2087.png"
            Image.linear_gradient("L").save(path)
            original = path.read_bytes()
            self.assertEqual(source_image(directory), path)
            rows = make_rows(path, (.5, .38))
            self.assertEqual(len(rows), GRID[1])
            self.assertTrue(all(len(row) == GRID[0] for row in rows))
            self.assertEqual(path.read_bytes(), original)
            svg = directory / "portrait.svg"
            svg.write_text(portrait_svg(rows), encoding="utf-8")
            validate(svg)
            self.assertIn("prefers-reduced-motion", svg.read_text(encoding="utf-8"))
            self.assertNotIn("@keyframes", portrait_svg(rows, static=True))
            for mobile in (False, True):
                svg.write_text(hero(rows, mobile, False), encoding="utf-8")
                validate(svg)

    def test_project_escapes_xml(self):
        svg = project({"name": "A&B", "description": "<example>", "stack": "Python", "stars": 0})
        ET.fromstring(svg)
        self.assertIn("A&amp;B", svg)
        self.assertIn("0 GitHub stars", svg)

    def test_language_shares_follow_snapshot(self):
        counts = {"repositories": {"languages": {"Python": 3, "TypeScript": 1}}}
        self.assertIn("75.0%", technology(counts))
        counts["repositories"]["languages"]["TypeScript"] = 3
        self.assertIn("50.0%", technology(counts))
        self.assertNotIn("75.0%", technology(counts))

    def test_static_calendar_contains_all_data_without_smil(self):
        calendar = {"calendar": {"days": {"2026-11-18": 3, "2026-11-19": 0}, "total": 2}}
        self.assertIn("<animate ", contributions(calendar))
        still = contributions(calendar, static=True)
        self.assertNotIn("<animate ", still)
        self.assertIn("2 contribuciones", still)


if __name__ == "__main__":
    unittest.main()
