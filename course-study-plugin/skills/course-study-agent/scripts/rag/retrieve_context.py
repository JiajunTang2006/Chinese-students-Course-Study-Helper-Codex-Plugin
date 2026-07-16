#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

import rag_core


TASKS = ["query", "weekly-note", "chapter-note", "tutorial", "mock-exam", "final-review", "midterm-review", "assignment"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare sourced offline context for an Agent or LLM.")
    parser.add_argument("--query", help="Specific user question or topic.")
    parser.add_argument("--task", default="query", choices=TASKS)
    parser.add_argument("--course", help="Course code, name, or folder substring.")
    parser.add_argument("--vault", default=".", help="Course project root.")
    parser.add_argument("--index-path", help="Optional SQLite index path.")
    parser.add_argument("--scope", default="", help="Free-text scope.")
    parser.add_argument("--doc-type", help="Filter by document type.")
    parser.add_argument("--week", help="Filter by week number.")
    parser.add_argument("--top-k", type=rag_core.positive_int, default=8)
    parser.add_argument("--neighbors", type=int, choices=range(0, 4))
    parser.add_argument("--include-practice", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rag_core.configure(args.vault, args.index_path)
    if not rag_core.index_exists(rag_core.INDEX_PATH):
        print(f"RAG index not found: {rag_core.INDEX_PATH}", file=sys.stderr)
        print("Run index_vault.py --vault <project> first.", file=sys.stderr)
        raise SystemExit(2)

    retrieval_query = args.query or rag_core.default_query_for_task(args.task, args.scope)
    include_practice = args.include_practice or args.task == "mock-exam"
    status = rag_core.get_index_status(rag_core.INDEX_PATH)
    results = rag_core.search_chunks(
        query=retrieval_query,
        course=args.course,
        doc_type=args.doc_type,
        week=args.week,
        task=args.task,
        include_practice=include_practice,
        top_k=args.top_k,
        index_path=rag_core.INDEX_PATH,
        neighbor_window=args.neighbors,
    )
    stats = rag_core.get_stats(rag_core.INDEX_PATH)
    sources = list(dict.fromkeys(str(item["source_path"]) for item in results))

    print("# Retrieved Course Context")
    print()
    print("## Retrieval Request")
    print(f"- Task: {args.task}")
    print(f"- Query: {retrieval_query}")
    print(f"- Course filter: {args.course or 'N/A'}")
    print(f"- Scope: {args.scope or 'N/A'}")
    print(f"- Index built at: {stats.get('built_at', 'unknown')}")
    print(f"- Index stale: {status['stale']}")
    print()
    print("## How The AI Should Use This")
    print("- Use the evidence below as the main source of course knowledge.")
    print("- Label additional model knowledge as Model Supplement.")
    print("- Say when local evidence is insufficient or the index is stale.")
    print("- Keep source paths in study outputs and exam questions.")
    print()
    if status["stale"]:
        print("> Retrieval warning: local notes changed after the last index update.")
        print()
    print("## Evidence Chunks")
    print()
    if not results:
        print("No matching chunks found. Rebuild the index or provide a narrower course/topic.")
        return
    for rank, item in enumerate(results, start=1):
        print(rag_core.format_result_markdown(item, rank, retrieval_query, full_text=True))
        print()
    print("## Sources Used")
    for source in sources:
        print(f"- `{source}`")


if __name__ == "__main__":
    main()
