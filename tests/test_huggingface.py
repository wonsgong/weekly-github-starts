import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import build, collect_huggingface
from scripts.reports import HUGGINGFACE_MODELS


class HuggingFaceTests(unittest.TestCase):
    def test_model_tab_keeps_decimal_scores_and_preserves_previous_snapshot_on_failure(self):
        models = [{"id": "legacy-model", "trendingScore": 1200.5, "pipeline_tag": "text-generation"}]
        models.extend({"id": f"fixture/model-{number}", "trendingScore": 100 - number}
                      for number in range(1, 10))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            with patch.object(collect_huggingface, "fetch_models", return_value=models):
                path = collect_huggingface.collect(reports)
            report = json.loads(path.read_bytes())
            self.assertEqual(HUGGINGFACE_MODELS, path.parent.name)
            self.assertEqual(1200.5, report["repositories"][0]["metric_value"])
            self.assertEqual("https://huggingface.co/legacy-model", report["repositories"][0]["url"])

            dist = root / "dist"
            build.build(reports, dist, "https://example.com/project", root / "card-news")
            index = (dist / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="huggingface-models/index.html"', index)
            tab = (dist / "huggingface-models" / "index.html").read_text(encoding="utf-8")
            self.assertEqual(10, tab.count('class="repo"'))
            self.assertIn("1,200.5<small>트렌딩 점수", tab)

            before = path.read_bytes()
            bad_models = [
                models[:9],
                [{**models[0], "trendingScore": float("nan")}, *models[1:]],
                [models[1], models[0], *models[2:]],
            ]
            for rows in bad_models:
                with patch.object(collect_huggingface, "fetch_models", return_value=rows):
                    with self.assertRaises(ValueError):
                        collect_huggingface.collect(reports)
                self.assertEqual(before, path.read_bytes())
