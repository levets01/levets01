import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_github_data import calendar_snapshot, refresh, repository_snapshot
from generate_cards import (
    STACK,
    activity_summary,
    contributions,
    hero,
    project,
    replace_sections,
    stats,
    technology,
)
from generate_portrait import (
    create_portrait,
    portrait_svg,
    sample_portrait,
    source_image,
)
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
            portrait = sample_portrait(path, 90, 110, focus=(.5, .38))
            sparse = sample_portrait(path, 90, 110, density=.5)
            self.assertLess(sparse.markup.count("h0"), portrait.markup.count("h0"))
            self.assertEqual(portrait, sample_portrait(path, 90, 110))
            self.assertEqual(path.read_bytes(), original)
            svg = directory / "portrait.svg"
            svg.write_text(portrait_svg(portrait), encoding="utf-8")
            validate(svg)
            self.assertIn("prefers-reduced-motion", svg.read_text(encoding="utf-8"))
            self.assertNotIn("@keyframes", portrait_svg(portrait, static=True))
            create_portrait(path, svg, 90, 110, palette=("#000000", "#852963", "#468741", "#FB78BC", "#EEF0FF"), static=True)
            self.assertIn('viewBox="0 0 90 110"', svg.read_text(encoding="utf-8"))
            self.assertIn("#852963", svg.read_text(encoding="utf-8"))
            for mobile in (False, True):
                svg.write_text(hero(portrait, mobile, False), encoding="utf-8")
                validate(svg)

    def test_project_escapes_xml(self):
        svg = project({"name": "A&B", "description": "<example>", "stack": "Python", "stars": 0})
        ET.fromstring(svg)
        self.assertIn("A&amp;B", svg)
        self.assertIn("0 GitHub stars", svg)

    def test_portrait_cli_accepts_both_path_syntaxes(self):
        script = Path(__file__).resolve().parents[1] / "scripts/generate_portrait.py"
        with TemporaryDirectory() as folder:
            photo, svg = Path(folder) / "source.png", Path(folder) / "portrait.svg"
            Image.linear_gradient("L").save(photo)
            options = ["--width", "96", "--height", "108", "--focus", ".45", ".3",
                       "--density", ".75", "--palette", "hologram", "--static"]
            subprocess.run([sys.executable, script, photo, svg, *options], check=True)
            positional = svg.read_bytes()
            subprocess.run([sys.executable, script, "--source", photo, "--output", svg, *options], check=True)
            self.assertEqual(svg.read_bytes(), positional)
            self.assertEqual(ET.parse(svg).getroot().get("viewBox"), "0 0 96 108")
            self.assertNotIn(b"@keyframes", positional)

    def test_language_shares_follow_snapshot(self):
        counts = {"repositories": {"languages": {"Python": 3, "TypeScript": 1}}}
        self.assertIn("75.0%", technology(counts))
        counts["repositories"]["languages"]["TypeScript"] = 3
        self.assertIn("50.0%", technology(counts))
        self.assertNotIn("75.0%", technology(counts))

    def test_technology_labels_have_embedded_logos_in_both_sizes(self):
        names = [tech for _, stack in STACK for tech in stack.split(" · ")]
        for mobile in (False, True):
            card = ET.fromstring(technology({}, mobile))
            paths = card.findall(".//{*}path[@aria-hidden='true']")
            self.assertEqual(len({node.get("d") for node in paths}), len(names))
            self.assertTrue(set(names) <= {node.text for node in card.findall(".//{*}text")})

    def test_staggered_calendar_has_a_static_final_frame(self):
        calendar = {"calendar": {"days": {"2026-11-18": 3, "2026-11-19": 0}, "total": 2}}
        self.assertIn('class="entry"', contributions(calendar))
        still = contributions(calendar, static=True)
        self.assertNotIn("@keyframes", still)
        self.assertIn("2 contribuciones", still)

    def test_four_metrics_use_snapshot_including_zero(self):
        snapshot = {"repositories": {"public_repos": 19, "followers": 0, "stars": 23},
                    "calendar": {"total": 117}}
        for mobile in (False, True):
            markup = stats(snapshot, mobile)
            for value in (19, 0, 23, 117):
                self.assertIn(f">{value}</text>", markup)
            self.assertIn(">—</text>", stats({}, mobile))

    def test_project_metadata_uses_github(self):
        repo = {"name": "Turno_Office", "fork": False, "language": "Rust",
                "description": "Descripción actualizada", "stargazers_count": 12,
                "html_url": "https://github.com/levets01/Turno_Office"}
        item, = repository_snapshot({"public_repos": 1, "followers": 0}, [repo])["projects"]
        self.assertEqual(item["description"], repo["description"])
        self.assertEqual(item["language"], repo["language"])
        self.assertEqual(item["stars"], 12)
        self.assertIn("Lenguaje principal · Rust", project(item))

    def test_active_days_and_longest_streak(self):
        days = {"2026-11-19": 1, "2026-11-15": 1, "2026-11-14": 4,
                "2026-11-16": 0, "2026-11-17": 2}
        self.assertEqual(activity_summary(days), (4, 2))
        self.assertEqual(activity_summary({}), (0, 0))

    def test_regeneration_preserves_authored_markdown(self):
        markdown = "# Mi perfil\n<!-- activity:start -->anterior<!-- activity:end -->\nMi contacto\n"
        updated = replace_sections(markdown, {"activity": "nuevo"})
        self.assertEqual(updated, "# Mi perfil\n<!-- activity:start -->\n\nnuevo\n\n<!-- activity:end -->\nMi contacto\n")
        self.assertEqual(replace_sections(updated, {"activity": "nuevo"}), updated)
        with self.assertRaises(ValueError):
            replace_sections(markdown, {"projects": "incompleto"})


if __name__ == "__main__":
    unittest.main()
