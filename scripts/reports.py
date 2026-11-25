import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
GITHUB = "https://github.com"
SOURCE = f"{GITHUB}/trending?since=weekly"
SEOUL = ZoneInfo("Asia/Seoul")
TOP = 10
REPO_NAME = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")


def iso_week(timestamp):
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("수집 시각에 시간대가 필요합니다.")
    year, week, _ = timestamp.astimezone(SEOUL).isocalendar()
    return f"{year:04d}-W{week:02d}"


def ranking_key(repo):
    return -repo["weekly_stars"], repo["name"].casefold()


def validate_report(report, week):
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
