import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree import ElementTree as ET

from scripts import build, collect
from scripts.reports import SEOUL, SOURCE, iso_week


def candidate(name, weekly, total="999,999", label="stars this week"):
    metric = f'<span class="d-inline-block float-sm-right"><svg></svg>{weekly} {label}</span>'
    return f"""
    <article class="Box-row">
      <h2><a href="/{name}">{name}</a></h2>
      <p class="col-9">A &amp; B &lt;img src=x&gt;</p>
      <a href="/{name}/stargazers">{total}</a>
      {metric if weekly is not None else ""}
    </article>"""


def trending(count=10, first_stars="20"):
    return "".join(
        candidate(f"fixture/repo-{index:02}", first_stars if index == 0 else str(index))
        for index in range(count)
    )


class RankingTests(unittest.TestCase):
    def test_uses_weekly_stars_instead_of_stargazers(self):
        html = candidate("fixture/weekly-leader", "1,200", "1,201") + trending()
        repos = collect.parse_trending(html)
        self.assertEqual("fixture/weekly-leader", repos[0]["name"])
        self.assertEqual(1200, repos[0]["weekly_stars"])
        self.assertEqual("https://github.com/fixture/weekly-leader", repos[0]["url"])
        self.assertEqual("A & B <img src=x>", repos[0]["description"])

    def test_sorts_all_candidates_numerically_and_breaks_ties_by_name(self):
        html = trending(first_stars="999") + candidate("fixture/zeta", "10,000")
        html += candidate("Fixture/Alpha", "10,000")
        repos = collect.parse_trending(html)
        self.assertEqual(["Fixture/Alpha", "fixture/zeta", "fixture/repo-00"],
                         [repo["name"] for repo in repos[:3]])
        self.assertEqual([10000, 10000, 999, 9, 8, 7, 6, 5, 4, 3],
                         [repo["weekly_stars"] for repo in repos[:10]])

    def test_iso_week_uses_seoul_date_and_iso_year(self):
        moment = datetime(2024, 12, 29, 15, 0, tzinfo=timezone.utc)
        self.assertEqual("2025-W01", iso_week(moment))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "reports"

    def collect_at(self, html, moment):
        with patch.object(collect, "fetch_trending", return_value=html):
            with patch.object(collect, "datetime") as clock:
                clock.now.return_value = moment
                return collect.collect(self.directory)

    def test_rerun_replaces_only_one_file_for_the_week(self):
        path = self.collect_at(trending(first_stars="200"), datetime(2025, 1, 1, 6, 40, tzinfo=SEOUL))
        rerun = datetime(2025, 1, 2, 8, 0, tzinfo=SEOUL)
        self.assertEqual(path, self.collect_at(trending(11, first_stars="300"), rerun))
        self.assertEqual(["2025-W01.json"], [file.name for file in self.directory.iterdir()])
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(rerun.isoformat(), report["collected_at"])
        self.assertEqual(SOURCE, report["source"])
        self.assertEqual(300, report["repositories"][0]["weekly_stars"])
        self.assertEqual(list(range(1, 11)), [repo["rank"] for repo in report["repositories"]])

    def test_failed_parse_preserves_previous_report_and_creates_no_file(self):
        moment = datetime(2025, 1, 1, 6, 40, tzinfo=SEOUL)
        path = self.collect_at(trending(), moment)
        before = path.read_bytes()

        invalid_candidates = [
            "",
            trending(9),
            trending() + candidate("fixture/missing", None),
            trending() + candidate("fixture/total-only", "100", "500", "stars today"),
            trending() + candidate("fixture/malformed", "9,99"),
            trending() + candidate("fixture/repo-00", "30"),
            trending() + candidate("fixture/truncated", "100").replace("</article>", ""),
        ]
        for html in invalid_candidates:
            with self.subTest(html=html[-200:]):
                with self.assertRaises(ValueError):
                    self.collect_at(html, moment)
                self.assertEqual(before, path.read_bytes())
                self.assertEqual([path], list(self.directory.iterdir()))

    def test_build_escapes_html_and_keeps_weekly_rss_ids_stable(self):
        self.collect_at(trending(), datetime(2025, 1, 1, 6, 40, tzinfo=SEOUL))
        self.collect_at(trending(), datetime(2025, 1, 8, 6, 40, tzinfo=SEOUL))
        destination = Path(self.temp.name) / "dist"
        base_url = "https://example.com/project"
        build.build(self.directory, destination, base_url)
        index = (destination / "index.html").read_text(encoding="utf-8")
        self.assertIn("GitHub 주간 Trending에 오른 저장소 중", index)
        self.assertIn("A &amp; B &lt;img src=x&gt;", index)
        self.assertNotIn("<img src=x>", index)
        self.assertIn('id="copy"', index)
        self.assertIn('href="weeks/2025-W01.html"', index)
        self.assertTrue((destination / "weeks/2025-W01.html").is_file())
        feed_path = destination / "feed.xml"
        items = ET.parse(feed_path).findall("channel/item")
        original_ids = [item.findtext("guid") for item in items]
        self.assertEqual(2, len(set(original_ids)))
        self.assertEqual(f"{base_url}/weeks/2025-W02.html", items[0].findtext("link"))

        self.collect_at(trending(first_stars="100"), datetime(2025, 1, 9, 6, 40, tzinfo=SEOUL))
        build.build(self.directory, destination, "https://other.example.com")
        items = ET.parse(feed_path).findall("channel/item")
        self.assertEqual(original_ids, [item.findtext("guid") for item in items])
