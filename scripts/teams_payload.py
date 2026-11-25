import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

if __package__:
    from .build import load_reports
    from .cards import CARD_IMAGES, CARD_ROOT, complete_card_set
    from .reports import REPORTS, ROOT
else:
    from build import load_reports
    from cards import CARD_IMAGES, CARD_ROOT, complete_card_set
    from reports import REPORTS, ROOT


def make_teams_images(published):
    # Keep the original 4:5 framing and fit within Teams' 1024 px limit.
    with TemporaryDirectory(prefix=".teams-", dir=published) as temporary:
        stage = Path(temporary)
        for name in CARD_IMAGES:
            subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(published / name), "-vf", "scale=816:1020",
                    "-frames:v", "1", "-update", "1", str(stage / name),
                ],
                check=True, timeout=25,
            )
        display = published / "teams"
        display.mkdir(exist_ok=True)
        for name in CARD_IMAGES:
            (stage / name).replace(display / name)


def image_grid(images, columns, column_width, target_width):
    rows = []
    for offset in range(0, len(images), columns):
        row = [{"type": "Column", "width": column_width, "items": [image]}
               for image in images[offset:offset + columns]]
        row.extend({"type": "Column", "width": column_width, "items": []}
                   for _ in range(columns - len(row)))
        rows.append({"type": "ColumnSet", "spacing": "Small", "columns": row})
    return {"type": "Container", "targetWidth": target_width, "items": rows}


def teams_payload(report, base_url, dist, card_root=CARD_ROOT):
    base_url = base_url.rstrip("/")
    site = urlsplit(base_url)
    if site.scheme != "https" or not site.hostname or site.query or site.fragment:
        raise ValueError("Teams 알림에는 공개 HTTPS Pages 주소가 필요합니다.")

    week = report["week"]
    body = []
    relative_cards = Path("card-news") / week
    published = dist / relative_cards
    if (published / "index.html").is_file() and complete_card_set(card_root / week, report):
        make_teams_images(published)
        gallery_url = f"{base_url}/{relative_cards.as_posix()}"
        labels = [f"{week} 카드뉴스 표지"] + [
            f'{repo["rank"]}위 {repo["name"]}' for repo in report["repositories"]
        ]
        images = [
            {
                "type": "Image",
                "size": "Stretch",
                "url": f"{gallery_url}/teams/{name}",
                "altText": label,
                "msTeams": {"allowExpand": True},
            }
            for name, label in zip(CARD_IMAGES, labels)
        ]
        body = [
            image_grid(images, 3, "188px", "wide"),
            image_grid(images, 2, "stretch", "atMost:standard"),
        ]

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.5",
                "msteams": {"width": "Full"},
                "body": body,
                "actions": [{
                    "type": "Action.OpenUrl", "title": "자세히 보기",
                    "url": f"{base_url}/weeks/{week}.html",
                }],
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

    try:
        payload = teams_payload(reports[0], args.base_url, args.dist)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Teams 알림 생성 실패 — {error}\n")
    json.dump(payload, sys.stdout, ensure_ascii=True, separators=(",", ":"))
    print()


if __name__ == "__main__":
    main()
