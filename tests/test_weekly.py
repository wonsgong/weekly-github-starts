import json
import struct
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree import ElementTree as ET

from scripts import build, collect, generate_cards, teams_payload
from scripts.cards import CARD_IMAGES
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

    def test_publishes_matching_cards_and_removes_stale_copy(self):
        time = datetime(2025, 1, 1, 6, 40, tzinfo=SEOUL)
        report_path = self.collect_at(trending(), time)
        root = Path(self.temp.name)
        card_root = root / "card-news"
        deck = card_root / report_path.stem
        deck.mkdir(parents=True)
        (deck / "cards.json").write_bytes(report_path.read_bytes())
        (deck / "index.html").write_text("card gallery", encoding="utf-8")
        png_header = b"\x89PNG\r\n\x1a\n\0\0\0\x0dIHDR" + struct.pack(">II", 1080, 1350)
        for name in CARD_IMAGES:
            (deck / name).write_bytes(png_header)
        destination = root / "dist"

        build.build(self.directory, destination, "https://example.com", card_root)
        index = destination / "index.html"
        week = destination / "weeks" / "2025-W01.html"
        published = destination / "card-news" / "2025-W01"
        self.assertIn('href="card-news/2025-W01/index.html"', index.read_text(encoding="utf-8"))
        self.assertIn('href="../card-news/2025-W01/index.html"', week.read_text(encoding="utf-8"))
        self.assertEqual({"index.html", *CARD_IMAGES}, {path.name for path in published.iterdir()})
        report = json.loads(report_path.read_bytes())
        with patch.object(teams_payload, "make_teams_images") as resize:
            payload = teams_payload.teams_payload(report, "https://example.com", destination, card_root)
            resize.assert_called_once_with(published)
        card = payload["attachments"][0]["content"]
        gallery = "https://example.com/card-news/2025-W01"
        self.assertEqual([f"{gallery}/teams/{name}" for name in CARD_IMAGES],
                         [image["url"] for image in card["body"]])
        self.assertTrue(all(image["type"] == "Image" and image["size"] == "Stretch" for image in card["body"]))
        self.assertEqual([f"{gallery}/{name}" for name in CARD_IMAGES],
                         [image["selectAction"]["url"] for image in card["body"]])
        self.assertEqual([{"type": "Action.OpenUrl", "title": "주간 리포트 보기",
                           "url": "https://example.com/weeks/2025-W01.html"}], card["actions"])
        with patch.object(generate_cards, "summarize_report") as gemini:
            self.assertIn("기존", generate_cards.generate(report_path, card_root))
            gemini.assert_not_called()

        self.collect_at(trending(first_stars="100"), time)
        with patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test-key"}):
            with patch.object(generate_cards, "summarize_report", side_effect=RuntimeError("offline")):
                with self.assertRaises(RuntimeError):
                    generate_cards.generate(report_path, card_root)
        self.assertTrue((deck / "index.html").exists())

        build.build(self.directory, destination, "https://example.com", card_root)
        self.assertNotIn("카드뉴스 보기", index.read_text(encoding="utf-8"))
        self.assertFalse(published.exists())
        updated = json.loads(report_path.read_bytes())
        payload = teams_payload.teams_payload(updated, "https://example.com", destination, card_root)
        fallback = payload["attachments"][0]["content"]
        self.assertEqual([], fallback["body"])
        self.assertEqual(card["actions"], fallback["actions"])
