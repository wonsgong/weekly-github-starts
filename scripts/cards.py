import json
import struct

if __package__:
    from .reports import ROOT, TOP
else:
    from reports import ROOT, TOP

CARD_ROOT = ROOT / "card-news"
CARD_IMAGES = ("00-cover.png", *(f"{rank:02d}.png" for rank in range(1, TOP + 1)))
CARD_ASSETS = ("index.html", *CARD_IMAGES)


def matches_report(deck, report):
    fields = ("rank", "id", "name", "url", "metric_value") if "board" in report else (
        "rank", "name", "url", "weekly_stars",
    )
    return deck.get("board") == report.get("board") and deck["week"] == report["week"] and [
        tuple(repo[field] for field in fields) for repo in deck["repositories"]
    ] == [tuple(repo[field] for field in fields) for repo in report["repositories"]]


def valid_card_image(path):
    with path.open("rb") as image:
        header = image.read(24)
    return (
        len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n"
        and header[12:16] == b"IHDR" and struct.unpack(">II", header[16:24]) == (1080, 1350)
    )


def complete_card_set(directory, report):
    try:
        deck = json.loads((directory / "cards.json").read_text(encoding="utf-8"))
        if not matches_report(deck, report) or not (directory / "index.html").is_file():
            return False
        return all(valid_card_image(directory / name) for name in CARD_IMAGES)
    except (OSError, ValueError, KeyError, TypeError):
        return False
