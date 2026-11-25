import argparse
import json
from datetime import datetime
from http.client import HTTPException
from pathlib import Path
from urllib.request import Request, urlopen

if __package__:
    from .reports import HUGGINGFACE, HUGGINGFACE_MODELS, REPORT_BOARDS, REPORTS, SEOUL, TOP, iso_week, write_report
else:
    from reports import HUGGINGFACE, HUGGINGFACE_MODELS, REPORT_BOARDS, REPORTS, SEOUL, TOP, iso_week, write_report

MODELS_API = (
    f"{HUGGINGFACE}/api/models?sort=trendingScore&direction=-1&limit={TOP}"
    "&expand=trendingScore&expand=pipeline_tag"
)


def fetch_models():
    request = Request(MODELS_API, headers={"Accept": "application/json", "User-Agent": "weekly-github-starts"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def collect(directory=REPORTS):
    models = fetch_models()
    if not isinstance(models, list) or len(models) != TOP:
        raise ValueError(f"Hugging Face 모델을 정확히 {TOP}개 수신해야 합니다.")

    entries = []
    for rank, model in enumerate(models, 1):
        name = model["id"]
        entries.append({
            "rank": rank,
            "id": name,
            "name": name,
            "url": f"{HUGGINGFACE}/{name}",
            "description": model.get("pipeline_tag") or "",
            "metric_value": model["trendingScore"],
        })
    collected = datetime.now(SEOUL)
    report = {
        "board": HUGGINGFACE_MODELS,
        "week": iso_week(collected),
        "collected_at": collected.isoformat(timespec="seconds"),
        "source": REPORT_BOARDS[HUGGINGFACE_MODELS]["url"],
        "repositories": entries,
    }
    return write_report(report, directory / HUGGINGFACE_MODELS)


def main():
    parser = argparse.ArgumentParser(description="Hugging Face 트렌딩 모델 TOP 10 수집")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS)
    args = parser.parse_args()
    try:
        print(collect(args.reports_dir))
    except (HTTPException, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.exit(1, f"Hugging Face 모델 순위 수집 실패 — {error}\n")


if __name__ == "__main__":
    main()
