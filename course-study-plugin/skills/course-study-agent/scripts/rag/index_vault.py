#!/usr/bin/env python3
from __future__ import annotations

import argparse

import rag_core


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect an offline course Markdown index.")
    parser.add_argument("--vault", default=".", help="Course project root.")
    parser.add_argument("--index-path", help="Optional SQLite index path.")
    parser.add_argument("--force", action="store_true", help="Force a full atomic rebuild.")
    parser.add_argument("--status", action="store_true", help="Only report whether the index is stale.")
    parser.add_argument("--json", action="store_true", help="Return JSON.")
    args = parser.parse_args()
    rag_core.configure(args.vault, args.index_path)

    if args.status:
        result = rag_core.get_index_status(rag_core.INDEX_PATH)
        if args.json:
            rag_core.print_json(result)
        else:
            print("# RAG Index Status")
            print(f"- Exists: {result['exists']}")
            print(f"- Stale: {result['stale']}")
            print(f"- Reason: {result['reason']}")
            print(f"- New files: {len(result.get('new', []))}")
            print(f"- Updated files: {len(result.get('updated', []))}")
            print(f"- Removed files: {len(result.get('removed', []))}")
        return

    result = rag_core.build_index(rag_core.INDEX_PATH, force=args.force)
    if args.json:
        rag_core.print_json(result)
        return
    print("Built local RAG index.")
    print(f"- Mode: {result['mode']}")
    print(f"- Files indexed: {result['file_count']}")
    print(f"- Chunks indexed: {result['chunk_count']}")
    print(f"- Added/updated/removed: {result['added']}/{result['updated']}/{result['removed']}")
    print(f"- Unchanged: {result['unchanged']}")
    print(f"- Index path: {result['index_path']}")


if __name__ == "__main__":
    main()
