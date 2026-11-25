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
    from .cards import CARD_ASSETS, CARD_ROOT, complete_card_set
    from .reports import REPORTS, REPORT_BOARDS, ROOT, SEOUL, SOURCE, validate_report
else:
    from cards import CARD_ASSETS, CARD_ROOT, complete_card_set
    from reports import REPORTS, REPORT_BOARDS, ROOT, SEOUL, SOURCE, validate_report

TITLE = "GitHub 주간 Trending TOP 10"
SCOPE = "GitHub 주간 Trending에 오른 저장소 중"
PREVIEW_URL = "http://localhost:8000"


def load_reports(report_dir, board=None):
    reports = []
    for path in sorted(report_dir.glob("*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if report.get("board") != board:
                raise ValueError("리포트가 다른 출처 폴더에 저장되어 있습니다.")
            validate_report(report, path.stem)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path.name} — {error}") from error
        reports.append(report)
    return reports


def page(title, body, prefix="", board=None):
    paths = {None: ("GitHub Trending", "index.html"), **{
        name: (meta["label"], f"{name}/index.html") for name, meta in REPORT_BOARDS.items()
    }}
    current = ' aria-current="true"'
    tabs = "".join(
        f'<a href="{prefix}{path}"{current if name == board else ""}>{label}</a>'
        for name, (label, path) in paths.items()
    )
    archive_path = paths[board][1]
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
      <a href="{prefix}{archive_path}#archive">지난 리포트</a>
      <a href="{prefix}feed.xml">RSS</a>
    </nav>
  </header>
  <nav class="source-tabs" aria-label="순위 출처">{tabs}</nav>
  <main>{body}</main>
</body>
</html>
"""


def report_body(report, public_url, card_url=None):
    week = report["week"]
    timestamp = datetime.fromisoformat(report["collected_at"]).astimezone(SEOUL)
    board = report.get("board")
    meta = REPORT_BOARDS.get(board)
    title = f'{meta["label"]} TOP 10' if meta else TITLE
    scope = meta["scope"] if meta else f"{SCOPE} 주간 스타 수로 집계한 순위입니다."
    metric = meta["metric"] if meta else "주간 스타"
    metric_key = "metric_value" if meta else "weekly_stars"
    source_label = meta["label"] if meta else "GitHub"
    snapshot = f' · 원본 집계 {escape(report["snapshot_date"])}' if "snapshot_date" in report else ""
    items = []
    share = [f"{week} {title}", scope]
    for repo in report["repositories"]:
        name = escape(repo["name"])
        description = escape(repo["description"])
        summary = f'<p class="description">{description}</p>' if description else ""
        count = f'{repo[metric_key]:,}'
        if board in {None, "skill-leaderboard"}:
            count = f"+{count}"
        items.append(f"""<li>
          <div><a class="repo" href="{escape(repo["url"])}">{name}</a>{summary}</div>
          <span class="stars">{count}<small>{metric}</small></span>
        </li>""")
        share.append(f'{repo["rank"]}. {repo["name"]} ({count})')
    share.append(public_url)
    share_text = escape("\n".join(share))
    card_link = f'<a href="{escape(card_url)}">카드뉴스 보기</a>' if card_url else ""
    return f"""
    <section class="ranking" aria-labelledby="ranking">
      <div class="eyebrow">{escape(week)}</div>
      <h1 id="ranking">{title}</h1>
      <p class="scope">{scope}</p>
      <div class="report-meta">
        <p><time datetime="{timestamp.isoformat()}">{timestamp:%Y-%m-%d %H:%M:%S} KST</time>{snapshot}
          <a href="{escape(report["source"])}">출처 · {source_label}</a>{card_link}</p>
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


def publish_board(reports, destination, base_url, card_root, board=None):
    meta = REPORT_BOARDS.get(board)
    title = f'{meta["label"]} TOP 10' if meta else TITLE
    section = Path(board) if board else Path(".")
    directory = destination / section
    archive_dir = directory / "weeks"
    archive_dir.mkdir(parents=True, exist_ok=True)
    root_prefix = "../" if board else ""
    card_section = Path("card-news") / section
    published_cards = destination / card_section
    card_urls = {}
    for report in reports:
        week = report["week"]
        source = card_root / section / week
        if complete_card_set(source, report):
            output = published_cards / week
            output.mkdir(parents=True, exist_ok=True)
            for name in CARD_ASSETS:
                shutil.copyfile(source / name, output / name)
            card_urls[week] = (card_section / week / "index.html").as_posix()
    for path in published_cards.glob("[0-9][0-9][0-9][0-9]-W[0-9][0-9]"):
        if path.is_dir() and path.name not in card_urls:
            shutil.rmtree(path)

    public_directory = f"{base_url}/{board}" if board else base_url
    if reports:
        latest = reports[0]
        week = latest["week"]
        card_url = f"{root_prefix}{card_urls[week]}" if week in card_urls else None
        body = report_body(latest, f"{public_directory}/weeks/{week}.html", card_url)
    else:
        scope = meta["scope"] if meta else f"{SCOPE} 주간 스타 수로 집계한 순위입니다."
        source = meta["url"] if meta else SOURCE
        body = f"""<h1>{title}</h1>
        <p class="scope">{scope}</p>
        <p>첫 리포트를 기다리는 중입니다. <a href="{escape(source)}">원본 순위 보기</a></p>"""

    archive = []
    week_prefix = f"../{root_prefix}"
    for index, report in enumerate(reports):
        week = report["week"]
        if index:
            archive.append(f'<li><a href="weeks/{week}.html">{week}</a></li>')
        url = f"{public_directory}/weeks/{week}.html"
        card_url = f"{week_prefix}{card_urls[week]}" if week in card_urls else None
        (archive_dir / f"{week}.html").write_text(
            page(f"{week} · {title}", report_body(report, url, card_url), week_prefix, board),
            encoding="utf-8",
        )
    archive_body = f"<ul>{''.join(archive)}</ul>" if archive else "<p>지난 주차 리포트가 없습니다.</p>"
    body += f'<section id="archive" aria-labelledby="archive-title"><h2 id="archive-title">지난 리포트</h2>{archive_body}</section>'
    (directory / "index.html").write_text(page(title, body, root_prefix, board), encoding="utf-8")

    current = {report["week"] for report in reports}
    for path in archive_dir.glob("[0-9][0-9][0-9][0-9]-W[0-9][0-9].html"):
        if path.stem not in current:
            path.unlink()


def build(report_dir, destination, base_url, card_root=CARD_ROOT):
    base_url = base_url.rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("사이트 URL은 쿼리나 프래그먼트 없는 HTTP(S) 주소여야 합니다.")
    reports = load_reports(report_dir)
    publish_board(reports, destination, base_url, card_root)
    for board in REPORT_BOARDS:
        publish_board(load_reports(report_dir / board, board), destination, base_url, card_root, board)
    write_feed(destination / "feed.xml", reports, base_url)
    for asset in ("style.css", "copy.js"):
        shutil.copyfile(ROOT / "site" / asset, destination / asset)


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
