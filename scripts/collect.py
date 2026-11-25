import argparse
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from http.client import HTTPException
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen

if __package__:
    from . import reports
else:
    import reports

WEEKLY_STARS = re.compile(r"([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+) stars? this week")


class TrendingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.candidates = []
        self.row = None
        self.in_heading = False
        self.captures = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "article" and "Box-row" in classes:
            if self.row is not None:
                raise ValueError("Trending 후보 카드가 닫히지 않았습니다.")
            self.row = {"links": [], "description": "", "weekly_labels": []}
        if self.row is None:
            return

        if tag == "h2":
            self.in_heading = True
        elif tag == "a" and self.in_heading:
            self.row["links"].append(attributes.get("href") or "")
        if tag in self.captures:
            self.captures[tag].append(None)
        elif (tag == "p" and "col-9" in classes) or (
            tag == "span" and "float-sm-right" in classes
        ):
            self.captures[tag] = [[]]

    def handle_data(self, data):
        for capture in self.captures.values():
            capture[0].append(data)

    def handle_endtag(self, tag):
        if self.row is None:
            return
        if tag == "h2":
            self.in_heading = False
        if tag in self.captures:
            captured = self.captures[tag].pop()
            if captured is not None:
                value = " ".join("".join(captured).split())
                del self.captures[tag]
                if tag == "p":
                    self.row["description"] = value
                else:
                    self.row["weekly_labels"].append(value)
        if tag == "article":
            self.finish_row()

    def finish_row(self):
        row = self.row
        position = len(self.candidates) + 1
        links = row["links"]
        if self.captures or self.in_heading or len(links) != 1:
            raise ValueError(f"Trending 후보 {position}의 마크업이 올바르지 않습니다.")

        href = links[0]
        name = href[1:]
        if not href.startswith("/") or not reports.REPO_NAME.fullmatch(name):
            raise ValueError(f"Trending 후보 {position}의 저장소 링크가 올바르지 않습니다.")

        labels = row["weekly_labels"]
        match = WEEKLY_STARS.fullmatch(labels[0]) if len(labels) == 1 else None
        if match is None:
            raise ValueError(f"{name}의 주간 스타 수를 확인할 수 없습니다.")

        self.candidates.append({
            "name": name,
            "url": f"{reports.GITHUB}{href}",
            "description": row["description"],
            "weekly_stars": int(match[1].replace(",", "")),
        })
        self.row = None


def parse_trending(html):
    parser = TrendingParser()
    parser.feed(html)
    parser.close()
    if parser.row is not None:
        raise ValueError("Trending 후보 카드가 닫히지 않았습니다.")
    candidates = parser.candidates
    if len({repo["name"].casefold() for repo in candidates}) != len(candidates):
        raise ValueError("Trending에 중복 저장소가 있습니다.")
    if len(candidates) < reports.TOP:
        raise ValueError(f"검증된 Trending 후보가 {len(candidates)}개입니다. (최소 {reports.TOP}개)")
    return sorted(candidates, key=reports.ranking_key)


def fetch_trending():
    request = Request(reports.SOURCE, headers={
        "Accept": "text/html",
        "Accept-Language": "en",
        "User-Agent": "weekly-github-starts",
    })
    with urlopen(request, timeout=30) as response:
        if response.geturl() != reports.SOURCE or response.headers.get_content_type() != "text/html":
            raise ValueError("GitHub 주간 Trending HTML 응답을 확인할 수 없습니다.")
        return response.read().decode("utf-8")


def collect(report_dir=reports.REPORTS):
    html = fetch_trending()
    collected_at = datetime.now(reports.SEOUL)
    candidates = parse_trending(html)
    week = reports.iso_week(collected_at)
    report = {
        "week": week,
        "collected_at": collected_at.isoformat(timespec="seconds"),
        "source": reports.SOURCE,
        "repositories": [
            {"rank": rank, **repo} for rank, repo in enumerate(candidates[:reports.TOP], 1)
        ],
    }
    reports.validate_report(report, week)

    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{week}.json"
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=report_dir, delete=False) as output:
            temporary_path = Path(output.name)
            output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return path


def main():
    parser = argparse.ArgumentParser(description="GitHub 주간 Trending TOP 10 수집")
    parser.add_argument("--reports-dir", type=Path, default=reports.REPORTS)
    options = parser.parse_args()
    try:
        path = collect(options.reports_dir)
    except (HTTPException, OSError, ValueError) as error:
        parser.exit(1, f"수집 실패 — {error}\n")
    print(path)


if __name__ == "__main__":
    main()
