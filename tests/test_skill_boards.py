import json
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import build, collect_skills, generate_cards, teams_payload
from scripts.cards import CARD_IMAGES
from scripts.reports import SKILL_BOARDS, skill_url, write_report

PNG_HEADER = b"\x89PNG\r\n\x1a\n\0\0\0\x0dIHDR" + struct.pack(">II", 1080, 1350)


def snapshot(week, date, names):
    return {
        "board": "skills-sh",
        "source": SKILL_BOARDS["skills-sh"]["url"],
        "week": week,
        "collected_at": f"{date}T06:40:00+09:00",
        "repositories": [
            {
                "rank": rank, "id": f"demo/repo/{name}", "name": name,
                "url": skill_url(f"demo/repo/{name}"), "description": "demo/repo",
                "metric_value": 200 - rank,
            }
            for rank, name in enumerate(names, 1)
        ],
    }


class SkillBoardsTests(unittest.TestCase):
    def test_sources_use_distinct_metrics_and_well_known_urls(self):
        catalog = {
            "metrics": {"snapshotDate": "2025-01-01", "publishedRepos": 2},
            "catalog": [
                {"repo": "one/popular", "stars": 90000, "stars7d": 70},
                {"repo": "two/growing", "stars": 100, "stars7d": 80},
            ],
        }
        rows, date = collect_skills.from_catalog(catalog)
        self.assertEqual("2025-01-01", date)
        self.assertEqual([("two/growing", 80), ("one/popular", 70)],
                         [(row["name"], row["metric_value"]) for row in rows])
        chunk = json.dumps({"initialSkills": [
            {"source": "demo.example", "skillId": "review", "name": "review", "installs": 350},
        ]})
        html = f'<a>Trending (24h)</a><script>self.__next_f.push([1,{json.dumps(chunk)}])</script>'
        row, = collect_skills.from_trending(html)
        self.assertEqual("https://www.skills.sh/site/demo.example/review", row["url"])
        self.assertEqual(350, row["metric_value"])
        with self.assertRaises(ValueError):
            collect_skills.from_trending(html.replace("24h", "7d"))

    def test_reuses_images_after_their_rank_changes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            cards = root / "card-news"
            names = [f"skill-{index}" for index in range(1, 11)]
            first = snapshot("2025-W01", "2025-01-01", names)
            next_week = snapshot("2025-W02", "2025-01-08", names[::-1])
            write_report(first, reports / "skills-sh")
            next_report = write_report(next_week, reports / "skills-sh")
            old = cards / "skills-sh" / "2025-W01"
            old.mkdir(parents=True)
            old_deck = {
                **first, "image_layout": "reusable-skill-v1",
                "repositories": [
                    {**entry, "headline": entry["name"], "summary": "요약",
                     "use_case": "", "readme_url": entry["url"]}
                    for entry in first["repositories"]
                ],
            }
            (old / "cards.json").write_text(json.dumps(old_deck), encoding="utf-8")
            (old / "index.html").write_text("gallery", encoding="utf-8")
            for index, name in enumerate(CARD_IMAGES):
                (old / name).write_bytes(PNG_HEADER + bytes([index]))

            def capture(command, **kwargs):
                stage = Path(command[-1])
                self.assertEqual(["00-cover.html"], [path.name for path in (stage / "slides").iterdir()])
                (stage / "package" / "00-cover.png").write_bytes(PNG_HEADER)

            with patch.object(generate_cards, "summarize_report") as gemini:
                with patch.object(generate_cards.subprocess, "run", side_effect=capture):
                    self.assertIn("10장 재사용", generate_cards.generate(next_report, cards))
                gemini.assert_not_called()
            new = cards / "skills-sh" / "2025-W02"
            self.assertEqual((old / "10.png").read_bytes(), (new / "01.png").read_bytes())
            self.assertEqual((old / "01.png").read_bytes(), (new / "10.png").read_bytes())

            dist = root / "dist"
            build.build(reports, dist, "https://example.com/demo", cards)
            tab = (dist / "skills-sh" / "index.html").read_text(encoding="utf-8")
            self.assertIn("24시간 설치", tab)
            self.assertIn("../card-news/skills-sh/2025-W02/index.html", tab)
            self.assertIn("weeks/2025-W01.html", tab)
            with patch.object(teams_payload, "make_teams_images"):
                payload = teams_payload.teams_payload(next_week, "https://example.com/demo", dist, cards)
            content = payload["attachments"][0]["content"]
            self.assertIn("skills.sh", content["body"][0]["items"][0]["columns"][0]["items"][0]["altText"])
            self.assertEqual("https://example.com/demo/skills-sh/weeks/2025-W02.html", content["actions"][0]["url"])
