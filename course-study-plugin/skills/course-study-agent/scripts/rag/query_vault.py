#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

import rag_core


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search an offline university course index.")
    parser.add_argument("query", help="Question or keywords to search for.")
    parser.add_argument("--vault", default=".", help="Course project root.")
    parser.add_argument("--index-path", help="Optional SQLite index path.")
    parser.add_argument("--course", help="Course code, name, or folder substring.")
    parser.add_argument("--doc-type", help="Filter by document type.")
    parser.add_argument("--week", help="Filter by week number.")
    parser.add_argument("--task", default="query", help="Retrieval task profile.")
    parser.add_argument("--top-k", type=rag_core.positive_int, default=8)
    parser.add_argument("--candidate-limit", type=rag_core.positive_int)
    parser.add_argument("--per-source-limit", type=rag_core.positive_int)
    parser.add_argument("--neighbors", type=int, choices=range(0, 4))
    parser.add_argument("--include-practice", action="store_true")
    parser.add_argument("--explain", action="store_true", help="Show ranking components.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rag_core.configure(args.vault, args.index_path)
    if not rag_core.index_exists(rag_core.INDEX_PATH):
        print(f"RAG index not found: {rag_core.INDEX_PATH}", file=sys.stderr)
        print("Run index_vault.py --vault <project> first.", file=sys.stderr)
        raise SystemExit(2)

    status = rag_core.get_index_status(rag_core.INDEX_PATH)
    results = rag_core.search_chunks(
        query=args.query,
        course=args.course,
        doc_type=args.doc_type,
        week=args.week,
        task=args.task,
        include_practice=args.include_practice,
        top_k=args.top_k,
        index_path=rag_core.INDEX_PATH,
        candidate_limit=args.candidate_limit,
        per_source_limit=args.per_source_limit,
        neighbor_window=args.neighbors,
    )

    if args.json:
        rag_core.print_json(
            {
                "query": args.query,
                "index_status": status,
                "stats": rag_core.get_stats(rag_core.INDEX_PATH),
                "results": results,
            }
        )
        return

    print("# RAG Search Results")
    print()
    print(f"- Query: {args.query}")
    print(f"- Index stale: {status['stale']}")
    if args.course:
        print(f"- Course filter: {args.course}")
    if args.week:
        print(f"- Week filter: {args.week}")
    print(f"- Results: {len(results)}")
    print()
    if status["stale"]:
        print("> Warning: notes changed after indexing; rebuild the index for complete results.")
        print()
    if not results:
        print("No matching chunks found. Try original technical terms, a narrower course, or rebuild the index.")
        return
    for rank, item in enumerate(results, start=1):
        print(rag_core.format_result_markdown(item, rank, args.query, explain=args.explain))
        print()


if __name__ == "__main__":
    main()
