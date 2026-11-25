import json
import re
from datetime import datetime
from math import isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
GITHUB = "https://github.com"
SOURCE = f"{GITHUB}/trending?since=weekly"
SEOUL = ZoneInfo("Asia/Seoul")
TOP = 10
REPO_NAME = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
SKILL_PATH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9][A-Za-z0-9_.-]*){1,2}")
SKILL_BOARDS = {
    "skill-leaderboard": {
        "label": "Skill Leaderboard",
        "url": "https://www.skillleaderboard.com/",
        "metric": "7일 스타 증가",
        "scope": "Skill Leaderboard 공개 카탈로그의 저장소 중 최근 7일 스타 증가량 순위입니다.",
    },
    "skills-sh": {
        "label": "skills.sh",
        "url": "https://www.skills.sh/trending",
        "metric": "24시간 설치",
        "scope": "매주 수집한 skills.sh Trending의 최근 24시간 설치 수 순위입니다.",
    },
}
HUGGINGFACE = "https://huggingface.co"
HUGGINGFACE_MODELS = "huggingface-models"
MODEL_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)?")
REPORT_BOARDS = {
    **SKILL_BOARDS,
    HUGGINGFACE_MODELS: {
        "label": "Hugging Face 모델",
        "url": f"{HUGGINGFACE}/models?sort=trending",
        "metric": "트렌딩 점수",
        "scope": "매주 수집 시점의 Hugging Face 모델 목록에서 트렌딩 점수가 높은 상위 10개입니다.",
    },
}


def iso_week(timestamp):
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("수집 시각에 시간대가 필요합니다.")
    year, week, _ = timestamp.astimezone(SEOUL).isocalendar()
    return f"{year:04d}-W{week:02d}"


def ranking_key(repo):
    return -repo["weekly_stars"], repo["name"].casefold()


def skill_url(identity):
    prefix = "site/" if identity.count("/") == 1 else ""
    return f"https://www.skills.sh/{prefix}{identity}"


def validate_report(report, week):
    if "board" in report:
        validate_board_report(report, week)
        return
    if report["week"] != week or report["source"] != SOURCE:
        raise ValueError("리포트 주차 또는 출처가 올바르지 않습니다.")
    if iso_week(datetime.fromisoformat(report["collected_at"])) != week:
        raise ValueError("파일 주차와 수집 시각의 한국 시간 ISO 주차가 다릅니다.")

    repos = report["repositories"]
    if len(repos) != TOP:
        raise ValueError(f"리포트에는 저장소가 {TOP}개 있어야 합니다.")
    names = set()
    for rank, repo in enumerate(repos, 1):
        name = repo["name"]
        stars = repo["weekly_stars"]
        if not REPO_NAME.fullmatch(name) or repo["url"] != f"{GITHUB}/{name}":
            raise ValueError(f"저장소 이름 또는 URL이 올바르지 않습니다. ({rank}위)")
        if (
            type(repo["rank"]) is not int
            or repo["rank"] != rank
            or type(stars) is not int
            or stars < 0
            or not isinstance(repo["description"], str)
            or name.casefold() in names
        ):
            raise ValueError(f"중복 저장소 또는 잘못된 순위 데이터입니다. ({name})")
        names.add(name.casefold())
    if repos != sorted(repos, key=ranking_key):
        raise ValueError("리포트 정렬이 올바르지 않습니다.")


def validate_board_report(report, week):
    board = report["board"]
    if board not in REPORT_BOARDS or report["source"] != REPORT_BOARDS[board]["url"]:
        raise ValueError("순위 출처가 올바르지 않습니다.")
    if report["week"] != week or iso_week(datetime.fromisoformat(report["collected_at"])) != week:
        raise ValueError("순위의 수집 주차와 파일 주차가 다릅니다.")
    if board == "skill-leaderboard":
        datetime.strptime(report["snapshot_date"], "%Y-%m-%d")
    entries = report["repositories"]
    if len(entries) != TOP:
        raise ValueError(f"순위 항목은 {TOP}개여야 합니다.")
    ids = set()
    previous = None
    for rank, entry in enumerate(entries, 1):
        identity, name, count = entry["id"], entry["name"], entry["metric_value"]
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError(f"잘못된 순위 이름입니다. ({rank}위)")
        valid_count = type(count) is int
        if board == "skill-leaderboard":
            valid_address = bool(REPO_NAME.fullmatch(name)) and identity == name.casefold()
            expected_url = f"{GITHUB}/{name}"
        elif board == HUGGINGFACE_MODELS:
            valid_address = bool(MODEL_ID.fullmatch(name)) and identity == name
            expected_url = f"{HUGGINGFACE}/{name}"
            valid_count = valid_count or (type(count) is float and isfinite(count))
        else:
            valid_address = bool(SKILL_PATH.fullmatch(identity))
            expected_url = skill_url(identity)
        if (
            not valid_address or entry["url"] != expected_url or identity in ids
            or not isinstance(entry["description"], str)
            or type(entry["rank"]) is not int or entry["rank"] != rank
            or not valid_count or count < 0 or (previous is not None and count > previous)
        ):
            raise ValueError(f"잘못된 순위 항목입니다. ({rank}위)")
        ids.add(identity)
        previous = count


def write_report(report, directory):
    week = report["week"]
    validate_report(report, week)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{week}.json"
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as output:
            temporary = Path(output.name)
            output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
