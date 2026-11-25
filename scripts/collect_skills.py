import argparse
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

if __package__:
    from .reports import GITHUB, REPORTS, SEOUL, SKILL_BOARDS, SKILL_PATH, TOP, iso_week, skill_url, write_report
else:
    from reports import GITHUB, REPORTS, SEOUL, SKILL_BOARDS, SKILL_PATH, TOP, iso_week, skill_url, write_report

CATALOG = "https://www.skillleaderboard.com/api/catalog"
FLIGHT = re.compile(r'self\.__next_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)')


def read_public(url):
    request = Request(url, headers={"User-Agent": "weekly-github-starts", "Accept-Language": "en"})
    with urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8")


def from_catalog(data):
    catalog = data["catalog"]
    snapshot = data["metrics"]["snapshotDate"]
    if len(catalog) != data["metrics"]["publishedRepos"]:
        raise ValueError("Skill Leaderboard 카탈로그가 일부만 수신되었습니다.")
    entries = [
        {
            "id": row["repo"].casefold(),
            "name": row["repo"],
            "url": f'{GITHUB}/{row["repo"]}',
            "description": " ".join(filter(None, (row.get("tagline"), row.get("summary")))),
            "metric_value": row["stars7d"],
        }
        for row in catalog
        if type(row["stars7d"]) is int and row["stars7d"] >= 0
    ]
    return sorted(entries, key=lambda row: (-row["metric_value"], row["id"])), snapshot


def from_trending(html):
    if not re.search(r"Trending\s*\(24h\)", html):
        raise ValueError("skills.sh의 24시간 Trending 페이지를 확인할 수 없습니다.")
    candidates = None
    for match in FLIGHT.finditer(html):
        data = json.loads(match[1])
        pointer = data.find('"initialSkills":')
        if pointer != -1:
            candidates, _ = json.JSONDecoder().raw_decode(data[pointer + len('"initialSkills":'):].lstrip())
            break
    if not isinstance(candidates, list):
        raise ValueError("skills.sh 순위 데이터가 없습니다.")
    entries = []
    for row in candidates:
        identity = f'{row["source"]}/{row["skillId"]}'
        if not SKILL_PATH.fullmatch(identity):
            raise ValueError("skills.sh 스킬 식별자가 올바르지 않습니다.")
        entries.append({
            "id": identity,
            "name": row["name"],
            "url": skill_url(identity),
            "description": row["source"],
            "metric_value": row["installs"],
        })
    return entries


class PageDescription(HTMLParser):
    text = ""

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name") == "description":
            self.text = (attributes.get("content") or "").strip()


def skill_description(url):
    parser = PageDescription()
    parser.feed(read_public(url))
    parser.close()
    return parser.text


def collect(board, directory=REPORTS):
    source = SKILL_BOARDS[board]["url"]
    if board == "skill-leaderboard":
        candidates, snapshot = from_catalog(json.loads(read_public(CATALOG)))
        extra = {"snapshot_date": snapshot}
    else:
        candidates = from_trending(read_public(source))
        extra = {}
    now = datetime.now(SEOUL)
    report = {
        "board": board, "source": source, "week": iso_week(now),
        "collected_at": now.isoformat(timespec="seconds"), **extra,
        "repositories": [
            {"rank": rank, **row} for rank, row in enumerate(candidates[:TOP], 1)
        ],
    }
    return write_report(report, directory / board)


def main():
    parser = argparse.ArgumentParser(description="스킬 공개 순위 TOP 10 수집")
    parser.add_argument("board", choices=SKILL_BOARDS)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS)
    args = parser.parse_args()
    try:
        print(collect(args.board, args.reports_dir))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"스킬 순위 수집 실패 — {error}\n")


if __name__ == "__main__":
    main()
