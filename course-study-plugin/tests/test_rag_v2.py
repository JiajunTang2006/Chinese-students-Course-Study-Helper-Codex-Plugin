from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RAG_DIR = PLUGIN_ROOT / "skills" / "course-study-agent" / "scripts" / "rag"
SPEC = importlib.util.spec_from_file_location("rag_core_v2", RAG_DIR / "rag_core.py")
assert SPEC and SPEC.loader
rag = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rag
SPEC.loader.exec_module(rag)


class OfflineRAGV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        notes = self.root / "notes"
        notes.mkdir()
        (self.root / "index.md").write_text(
            "# 导航\n\n- 供给与需求：待添加\n- 机会成本：待添加\n",
            encoding="utf-8",
        )
        self.supply = notes / "Week 01 Supply and Demand.md"
        self.supply.write_text(
            "# 第一周 供给与需求\n\n## Semantic Summary\n\n价格上升会影响需求量与供给量。\n\n"
            "## 核心概念\n\n需求曲线 Demand curve 通常向右下方倾斜，其他条件不变。\n\n"
            "## 应用\n\n市场均衡由供给和需求共同决定。\n",
            encoding="utf-8",
        )
        self.cost = notes / "Week 02 Opportunity Cost.md"
        self.cost.write_text(
            "# 第二周 机会成本\n\n选择一个方案所放弃的最佳替代方案价值叫作机会成本 Opportunity cost。\n",
            encoding="utf-8",
        )
        rag.configure(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_chinese_fts_prefers_content_over_navigation(self) -> None:
        result = rag.build_index(force=True)
        self.assertEqual(result["mode"], "full")
        rows = rag.search_chunks("需求曲线为什么向右下方倾斜", top_k=3)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["source_path"], "notes/Week 01 Supply and Demand.md")
        self.assertNotEqual(rows[0]["doc_type"], "root-index")
        self.assertIn("需求曲线", rows[0]["context_text"])

    def test_incremental_update_and_stale_detection(self) -> None:
        rag.build_index(force=True)
        self.assertFalse(rag.get_index_status()["stale"])
        time.sleep(0.01)
        self.cost.write_text(self.cost.read_text(encoding="utf-8") + "\n沉没成本不属于未来决策的机会成本。\n", encoding="utf-8")
        stale = rag.get_index_status()
        self.assertTrue(stale["stale"])
        self.assertIn("notes/Week 02 Opportunity Cost.md", stale["updated"])
        result = rag.build_index()
        self.assertEqual(result["mode"], "incremental")
        self.assertEqual(result["updated"], 1)
        self.assertFalse(rag.get_index_status()["stale"])

    def test_config_change_marks_index_stale(self) -> None:
        rag.build_index(force=True)
        (self.root / "course-study.json").write_text(
            json.dumps({"rag": {"neighbor_window": 0}}), encoding="utf-8"
        )
        status = rag.get_index_status()
        self.assertTrue(status["stale"])
        self.assertEqual(status["reason"], "config")

    def test_unknown_query_does_not_return_unrelated_chunks(self) -> None:
        rag.build_index(force=True)
        self.assertEqual(rag.search_chunks("量子纠缠拓扑超导", top_k=5), [])

    def test_evaluation_cli_reports_hit_rate(self) -> None:
        dataset = self.root / "evaluation.jsonl"
        dataset.write_text(
            json.dumps(
                {
                    "query": "机会成本是什么",
                    "expected_sources": ["Week 02 Opportunity Cost.md"],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(RAG_DIR / "evaluate_rag.py"),
                str(dataset),
                "--vault",
                str(self.root),
                "--rebuild",
                "--min-hit-rate",
                "1.0",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["hit_rate"], 1.0)
        self.assertEqual(report["top1_accuracy"], 1.0)
        self.assertEqual(report["hit_at_3"], 1.0)
        self.assertEqual(report["mrr"], 1.0)
        self.assertEqual(report["ndcg_at_k"], 1.0)

    def test_config_initializer_preserves_existing_file(self) -> None:
        command = [sys.executable, str(RAG_DIR / "init_config.py"), "--vault", str(self.root)]
        first = subprocess.run(command, check=False, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        config = self.root / "course-study.json"
        payload = json.loads(config.read_text(encoding="utf-8"))
        self.assertFalse(payload["rag"]["include_extracted"])
        config.write_text('{"rag":{"neighbor_window":0}}\n', encoding="utf-8")
        second = subprocess.run(command, check=False, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(config.read_text(encoding="utf-8"), '{"rag":{"neighbor_window":0}}\n')

    def test_local_pptx_extraction_is_indexable_and_course_aware(self) -> None:
        course = self.root / "courses" / "ECON101 Economics"
        raw = course / "01raw" / "lecture-slides"
        raw.mkdir(parents=True)
        pptx = raw / "Week 03 Elasticity.pptx"
        with zipfile.ZipFile(pptx, "w") as archive:
            archive.writestr(
                "ppt/slides/slide1.xml",
                '<p:sld xmlns:p="p" xmlns:a="a"><a:t>价格弹性 Price elasticity</a:t></p:sld>',
            )
        (self.root / "index.md").write_text(
            "| Code | Course | Main Area | Course Folder |\n"
            "| --- | --- | --- | --- |\n"
            "| ECON101 | Economics | Business | `courses/ECON101 Economics/` |\n",
            encoding="utf-8",
        )
        spec = importlib.util.spec_from_file_location("extract_source_test", RAG_DIR / "extract_source.py")
        assert spec and spec.loader
        extractor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(extractor)
        sections = extractor.extract(pptx)
        self.assertEqual(sections[0][0], "Slide 1")
        self.assertIn("Price elasticity", sections[0][1])

        extracted = self.root / ".course-study" / "extracted" / "elasticity.md"
        extracted.parent.mkdir(parents=True)
        extracted.write_text(
            "# Extracted Source\n\n- Original source: `courses/ECON101 Economics/01raw/lecture-slides/Week 03 Elasticity.pptx`\n\n"
            "## Slide 1\n\n价格弹性 Price elasticity\n",
            encoding="utf-8",
        )
        (self.root / "course-study.json").write_text(
            json.dumps({"rag": {"include_extracted": True}}), encoding="utf-8"
        )
        rag.configure(self.root)
        rag.build_index(force=True)
        rows = rag.search_chunks("价格弹性", course="ECON101", top_k=3)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["course_code"], "ECON101")
        self.assertEqual(rows[0]["doc_type"], "raw-source")

    def test_schema_v3_uses_weighted_fields_and_real_bm25(self) -> None:
        rag.build_index(force=True)
        self.assertEqual(rag.get_stats()["schema_version"], "3")
        rows = rag.search_chunks("机会成本", top_k=3)
        self.assertTrue(rows)
        self.assertGreater(rows[0]["bm25_raw"], 0.0)
        self.assertIn("bm25", rows[0]["score_components"])
        self.assertIn("term_coverage", rows[0]["score_components"])

    def test_weighted_title_beats_repeated_body_only_match(self) -> None:
        notes = self.root / "notes"
        (notes / "Week 03 Routing.md").write_text(
            "# 路由协议 Routing Protocol\n\n用于选择网络路径。\n", encoding="utf-8"
        )
        (notes / "Week 04 Misc.md").write_text(
            "# 其他主题\n\n路由协议 路由协议 路由协议 路由协议。\n", encoding="utf-8"
        )
        rag.build_index(force=True)
        rows = rag.search_chunks("路由协议", top_k=3)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["source_path"], "notes/Week 03 Routing.md")

    def test_week_filter_is_applied_before_candidate_limit(self) -> None:
        notes = self.root / "notes"
        for number in range(20):
            (notes / f"Week 01 Noise {number:02d}.md").write_text(
                f"# Week 01 Noise {number}\n\n拥塞控制 congestion control repeated material.\n",
                encoding="utf-8",
            )
        target = notes / "Week 09 Congestion Control.md"
        target.write_text(
            "# Week 09 Congestion Control\n\n拥塞控制通过调整发送窗口缓解网络拥塞。\n",
            encoding="utf-8",
        )
        rag.build_index(force=True)
        rows = rag.search_chunks("拥塞控制", week="9", candidate_limit=10, top_k=3)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["source_path"], "notes/Week 09 Congestion Control.md")
        self.assertEqual(rows[0]["week_number"], 9)

    def test_project_synonyms_bridge_chinese_and_english(self) -> None:
        (self.root / "notes" / "Week 05 AI Governance.md").write_text(
            "# AI Governance\n\nArtificial intelligence governance requires accountability and transparency.\n",
            encoding="utf-8",
        )
        (self.root / "course-study.json").write_text(
            json.dumps(
                {
                    "rag": {
                        "stopwords": ["请说明"],
                        "synonyms": {"人工智能": ["AI", "artificial intelligence"]},
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        rag.build_index(force=True)
        rows = rag.search_chunks("请说明人工智能", top_k=3)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["source_path"], "notes/Week 05 AI Governance.md")
        self.assertIn("synonym", rows[0]["score_components"])

    def test_minimum_should_match_can_filter_partial_noise(self) -> None:
        (self.root / "notes" / "Week 06 Partial.md").write_text(
            "# 网络拥塞\n\n这里只介绍网络拥塞，不包含其他主题。\n", encoding="utf-8"
        )
        (self.root / "course-study.json").write_text(
            json.dumps({"rag": {"minimum_should_match": 0.75}}), encoding="utf-8"
        )
        rag.build_index(force=True)
        rows = rag.search_chunks("网络拥塞 数据加密", top_k=5)
        self.assertEqual(rows, [])

    def test_heading_plus_placeholder_is_detected(self) -> None:
        self.assertTrue(rag.is_placeholder("# Major Notes\n\nTo be added\n"))

    def test_explicit_navigation_query_can_retrieve_course_index(self) -> None:
        rag.build_index(force=True)
        rows = rag.search_chunks("课程导航 index", top_k=3)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["doc_type"], "root-index")
        self.assertIn("navigation_intent", rows[0]["score_components"])

    def test_near_identical_chunks_are_deduplicated(self) -> None:
        text = "# Shared Topic\n\n网络分层模型将通信功能组织成多个层次。\n"
        (self.root / "notes" / "Week 07 Duplicate A.md").write_text(text, encoding="utf-8")
        (self.root / "notes" / "Week 08 Duplicate B.md").write_text(text, encoding="utf-8")
        rag.build_index(force=True)
        rows = rag.search_chunks("网络分层模型", top_k=8)
        duplicates = [row for row in rows if "Duplicate" in row["source_path"]]
        self.assertEqual(len(duplicates), 1)


if __name__ == "__main__":
    unittest.main()
