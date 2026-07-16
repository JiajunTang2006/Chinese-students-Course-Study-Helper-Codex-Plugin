#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_CONFIG = {
    "rag": {
        "include_dirs": [],
        "exclude_globs": [],
        "include_extracted": False,
        "chunk_chars": 2400,
        "chunk_overlap": 180,
        "candidate_limit": 80,
        "per_source_limit": 2,
        "diversity": 0.22,
        "dedupe_threshold": 0.92,
        "minimum_should_match": 0.18,
        "neighbor_window": 1,
        "index_navigation": True,
        "stopwords": [],
        "synonyms": {},
    }
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a project-local course-study.json configuration.")
    parser.add_argument("--vault", default=".", help="Course project root.")
    parser.add_argument("--force", action="store_true", help="Replace an existing configuration.")
    parser.add_argument(
        "--include-extracted",
        action="store_true",
        help="Index locally extracted PPTX/PDF/DOCX text under .course-study/extracted.",
    )
    args = parser.parse_args()
    root = Path(args.vault).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    target = root / "course-study.json"
    if target.exists() and not args.force:
        print(f"Configuration already exists: {target}")
        print("No changes made. Use --force only when replacement is intended.")
        return
    payload = json.loads(json.dumps(DEFAULT_CONFIG))
    payload["rag"]["include_extracted"] = bool(args.include_extracted)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created configuration: {target}")


if __name__ == "__main__":
    main()
