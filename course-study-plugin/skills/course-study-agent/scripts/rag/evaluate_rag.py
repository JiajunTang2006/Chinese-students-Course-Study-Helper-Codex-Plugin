#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import rag_core


def source_matches(actual: str, expected: list[str]) -> bool:
    actual_cf = actual.casefold()
    return any(value.casefold() in actual_cf for value in expected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate offline RAG retrieval with a JSONL question set.")
    parser.add_argument("dataset", help="JSONL file with query and expected_sources fields.")
    parser.add_argument("--vault", default=".")
    parser.add_argument("--index-path")
    parser.add_argument("--top-k", type=rag_core.positive_int, default=5)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--min-hit-rate", type=float, default=0.0)
    args = parser.parse_args()
    rag_core.configure(args.vault, args.index_path)
    if args.rebuild or not rag_core.index_exists(rag_core.INDEX_PATH):
        rag_core.build_index(rag_core.INDEX_PATH, force=args.rebuild)

    cases = []
    for line_number, line in enumerate(Path(args.dataset).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item.get("query"), str) or not isinstance(item.get("expected_sources"), list):
            raise ValueError(f"Invalid evaluation row at line {line_number}")
        cases.append(item)

    details = []
    hits = 0
    top1_hits = 0
    top3_hits = 0
    reciprocal_sum = 0.0
    ndcg_sum = 0.0
    for case in cases:
        results = rag_core.search_chunks(
            query=case["query"],
            course=case.get("course"),
            doc_type=case.get("doc_type"),
            week=case.get("week"),
            task=case.get("task", "query"),
            include_practice=bool(case.get("include_practice", False)),
            top_k=args.top_k,
            index_path=rag_core.INDEX_PATH,
        )
        returned_sources = list(dict.fromkeys(str(result["source_path"]) for result in results))
        relevant_ranks = [
            index
            for index, source in enumerate(returned_sources, start=1)
            if source_matches(source, case["expected_sources"])
        ]
        rank = next(
            iter(relevant_ranks),
            None,
        )
        if rank:
            hits += 1
            top1_hits += int(rank == 1)
            top3_hits += int(rank <= 3)
            reciprocal_sum += 1.0 / rank
        dcg = sum(1.0 / math.log2(value + 1) for value in relevant_ranks)
        ideal_count = min(len(set(case["expected_sources"])), len(returned_sources), args.top_k)
        idcg = sum(1.0 / math.log2(value + 1) for value in range(1, ideal_count + 1))
        ndcg_sum += dcg / idcg if idcg else 0.0
        details.append(
            {
                "query": case["query"],
                "hit": rank is not None,
                "rank": rank,
                "expected_sources": case["expected_sources"],
                "returned_sources": returned_sources,
            }
        )
    count = len(cases)
    summary = {
        "cases": count,
        "top_k": args.top_k,
        "hit_rate": round(hits / count, 4) if count else 0.0,
        "top1_accuracy": round(top1_hits / count, 4) if count else 0.0,
        "hit_at_3": round(top3_hits / count, 4) if count else 0.0,
        "mrr": round(reciprocal_sum / count, 4) if count else 0.0,
        "ndcg_at_k": round(ndcg_sum / count, 4) if count else 0.0,
        "details": details,
    }
    rag_core.print_json(summary)
    if summary["hit_rate"] < args.min_hit_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
