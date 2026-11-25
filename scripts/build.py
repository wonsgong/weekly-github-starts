import argparse
import json
import shutil
from datetime import datetime
from email.utils import format_datetime
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree as ET

if __package__:
    from .reports import REPORTS, ROOT, SEOUL, SOURCE, validate_report
else:
    from reports import REPORTS, ROOT, SEOUL, SOURCE, validate_report

TITLE = "GitHub 주간 Trending TOP 10"
SCOPE = "GitHub 주간 Trending에 오른 저장소 중"
PREVIEW_URL = "http://localhost:8000"


def load_reports(report_dir):
    reports = []
    for path in sorted(report_dir.glob("*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            validate_report(report, path.stem)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path.name} — {error}") from error
        reports.append(report)
    return reports


def page(title, body, prefix=""):
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="{prefix}style.css">
  <link rel="alternate" type="application/rss+xml" title="{TITLE}" href="{prefix}feed.xml">
  <script defer src="{prefix}copy.js"></script>
</head>
<body>
  <header class="site-header">
    <a class="brand" href="{prefix}index.html">Weekly GitHub Stars</a>
    <nav aria-label="사이트 메뉴">
      <a href="{prefix}index.html#archive">지난 리포트</a>
      <a href="{prefix}feed.xml">RSS</a>
    </nav>
  </header>
  <main>{body}</main>
</body>
</html>
"""


def report_body(report, public_url):
    week = report["week"]
    timestamp = datetime.fromisoformat(report["collected_at"]).astimezone(SEOUL)
    items = []
    share = [f"{week} {TITLE}", f"{SCOPE} 주간 스타 수 순위"]
    for repo in report["repositories"]:
        name = escape(repo["name"])
        description = escape(repo["description"])
        summary = f'<p class="description">{description}</p>' if description else ""
        stars = f'{repo["weekly_stars"]:,}'
        items.append(f"""<li>
          <div><a class="repo" href="{escape(repo["url"])}">{name}</a>{summary}</div>
          <span class="stars">+{stars}<small>주간 스타</small></span>
        </li>""")
        share.append(f'{repo["rank"]}. {repo["name"]} (+{stars})')
    share.append(public_url)
    share_text = escape("\n".join(share))
    return f"""
    <section class="ranking" aria-labelledby="ranking">
      <div class="eyebrow">{escape(week)}</div>
      <h1 id="ranking">{TITLE}</h1>
      <p class="scope">{SCOPE} 주간 스타 수로 집계한 순위입니다.</p>
      <div class="report-meta">
        <p><time datetime="{timestamp.isoformat()}">{timestamp:%Y-%m-%d %H:%M:%S} KST</time>
          <a href="{escape(report["source"])}">출처 · GitHub</a></p>
        <button type="button" id="copy" hidden>공유 문구 복사</button>
      </div>
      <p id="copy-status" role="status" aria-live="polite"></p>
      <textarea id="share-text" aria-label="공유 문구" readonly hidden>{share_text}</textarea>
      <ol class="ranking-list">{''.join(items)}</ol>
    </section>
"""


def write_feed(path, reports, base_url):
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = TITLE
    ET.SubElement(channel, "link").text = f"{base_url}/"
    ET.SubElement(channel, "description").text = f"{SCOPE} 주간 스타 수로 집계한 순위"
    ET.SubElement(channel, "language").text = "ko"
    for report in reports:
        week = report["week"]
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"{week} {TITLE}"
        ET.SubElement(item, "link").text = f"{base_url}/weeks/{week}.html"
        item_id = uuid5(NAMESPACE_URL, f"github.com/wonsgong/weekly-github-starts/{week}")
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = item_id.urn
        timestamp = datetime.fromisoformat(report["collected_at"])
        ET.SubElement(item, "pubDate").text = format_datetime(timestamp)
        rows = "".join(
            f'<li><a href="{escape(repo["url"])}">{escape(repo["name"])}</a> '
            f'(+{repo["weekly_stars"]:,})</li>'
            for repo in report["repositories"]
        )
        ET.SubElement(item, "description").text = (
            f"<p>{SCOPE} 주간 스타 수로 집계한 순위</p><ol>{rows}</ol>"
        )
    ET.indent(rss)
    ET.ElementTree(rss).write(path, encoding="utf-8", xml_declaration=True)


def build(report_dir, destination, base_url):
    base_url = base_url.rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("사이트 URL은 쿼리나 프래그먼트 없는 HTTP(S) 주소여야 합니다.")
    reports = load_reports(report_dir)
    weeks = destination / "weeks"
    weeks.mkdir(parents=True, exist_ok=True)

    if reports:
        latest = reports[0]
        body = report_body(latest, f'{base_url}/weeks/{latest["week"]}.html')
    else:
        body = f"""<h1>{TITLE}</h1>
        <p class="scope">{SCOPE} 주간 스타 수로 집계한 순위입니다.</p>
        <p>첫 리포트를 기다리는 중입니다. <a href="{SOURCE}">GitHub에서 원본 보기</a></p>"""

    archive = []
    for index, report in enumerate(reports):
        week = report["week"]
        if index:
            archive.append(f'<li><a href="weeks/{week}.html">{week}</a></li>')
        url = f"{base_url}/weeks/{week}.html"
        (weeks / f"{week}.html").write_text(
            page(f"{week} · {TITLE}", report_body(report, url), "../"),
            encoding="utf-8",
        )
    archive_body = f"<ul>{''.join(archive)}</ul>" if archive else "<p>지난 주차 리포트가 없습니다.</p>"
    body += f'<section id="archive" aria-labelledby="archive-title"><h2 id="archive-title">지난 리포트</h2>{archive_body}</section>'
    (destination / "index.html").write_text(page(TITLE, body), encoding="utf-8")
    write_feed(destination / "feed.xml", reports, base_url)
    for asset in ("style.css", "copy.js"):
        shutil.copyfile(ROOT / "site" / asset, destination / asset)

    current = {report["week"] for report in reports}
    for path in weeks.glob("[0-9][0-9][0-9][0-9]-W[0-9][0-9].html"):
        if path.stem not in current:
            path.unlink()


def main():
    parser = argparse.ArgumentParser(description="주간 리포트 정적 사이트 빌드")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--base-url", default=PREVIEW_URL)
    options = parser.parse_args()
    try:
        build(options.reports_dir, options.output_dir, options.base_url)
    except (OSError, ValueError) as error:
        parser.exit(1, f"빌드 실패 — {error}\n")
    print(options.output_dir)


if __name__ == "__main__":
    main()
