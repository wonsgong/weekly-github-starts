import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from shutil import which
from urllib.parse import urlsplit

if __package__:
    from .build import SCOPE, TITLE, load_reports
    from .cards import CARD_ROOT, complete_card_set
    from .reports import REPORTS, ROOT
else:
    from build import SCOPE, TITLE, load_reports
    from cards import CARD_ROOT, complete_card_set
    from reports import REPORTS, ROOT


def text(value, **properties):
    return {"type": "TextBlock", "text": value, "wrap": True, **properties}


def markdown(value):
    return re.sub(r"([\\`*_{}\[\]()#!~|<>])", r"\\\1", value)


def make_preview(cover, preview):
    preview.unlink(missing_ok=True)
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        subprocess.run(
            [
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(cover), "-vf", "scale=800:1000",
                "-frames:v", "1", "-update", "1", str(preview),
            ],
            check=True, stdout=subprocess.DEVNULL, timeout=25,
        )
    except (OSError, subprocess.SubprocessError):
        preview.unlink(missing_ok=True)
        return False
    return preview.is_file()


def teams_payload(report, base_url, dist, card_root=CARD_ROOT):
    base_url = base_url.rstrip("/")
    site = urlsplit(base_url)
    if site.scheme != "https" or not site.hostname or site.query or site.fragment:
        raise ValueError("Teams 알림에는 공개 HTTPS Pages 주소가 필요합니다.")

    week = report["week"]
    title = f"{week} {TITLE}"
    body = [text(title, weight="Bolder", size="Large"), text(f"{SCOPE} 주간 스타 수 순위")]
    actions = [{"type": "Action.OpenUrl", "title": "주간 리포트 보기", "url": f"{base_url}/weeks/{week}.html"}]
    summaries = {}

    relative_cards = f"card-news/{week}"
    published = dist / relative_cards
    source = card_root / week
    if (published / "index.html").is_file() and complete_card_set(source, report):
        deck = json.loads((source / "cards.json").read_text(encoding="utf-8"))
        summaries = {repo["name"]: repo.get("summary", "") for repo in deck["repositories"]}
        actions.append({
            "type": "Action.OpenUrl", "title": "카드뉴스 전체 보기",
            "url": f"{base_url}/{relative_cards}/index.html",
        })
        preview = published / "teams-cover.png"
        if make_preview(published / "00-cover.png", preview):
            body.append({
                "type": "Image", "size": "Medium", "altText": f"{title} 카드뉴스 표지",
                "url": f"{base_url}/{relative_cards}/{preview.name}",
            })

    for repo in report["repositories"]:
        label = markdown(repo["name"])
        body.append(text(
            f'{repo["rank"]}위 [{label}]({repo["url"]}) · +{repo["weekly_stars"]:,} 스타',
            spacing="Medium",
        ))
        summary = summaries.get(repo["name"])
        if isinstance(summary, str) and summary.strip():
            body.append(text(markdown(" ".join(summary.split())[:180]), spacing="None", isSubtle=True))

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.2",
                "body": body,
                "actions": actions,
            },
        }],
    }


def main():
    parser = argparse.ArgumentParser(description="최신 주간 리포트의 Teams 웹훅 메시지 생성")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    reports = load_reports(REPORTS)
    if not reports:
        parser.exit(1, "Teams 알림에 사용할 리포트가 없습니다.\n")

    payload = teams_payload(reports[0], args.base_url, args.dist)
    json.dump(payload, sys.stdout, ensure_ascii=True, separators=(",", ":"))
    print()


if __name__ == "__main__":
    main()
