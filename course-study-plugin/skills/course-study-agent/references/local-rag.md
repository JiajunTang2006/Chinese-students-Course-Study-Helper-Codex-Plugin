# Local Offline RAG

Use the bundled local retrieval when a project contains more notes than should be opened at once. It does not call an LLM, an embedding API, or any cloud service.

## How It Works

1. Discover eligible local Markdown files.
2. Split them by headings and logical blocks, with overlap for long sections.
3. Store metadata and text in a project-local SQLite database.
4. Search with weighted SQLite FTS5/BM25 fields, English tokens, and Chinese 2/3-character n-grams.
5. Rerank with normalized raw BM25 strength, exact phrases, token coverage, configurable synonyms, task type, placeholders, navigation pages, practice sections, and source diversity.
6. Return the matching chunk plus configurable neighboring chunks and source paths.

The current Agent may pass retrieved text to its active model when generating an answer. The indexing and retrieval stages themselves remain offline.

## Commands

Scripts live under `scripts/rag/`. Run them from the target project root.

```bash
python3 <skill-dir>/scripts/rag/index_vault.py --vault .
python3 <skill-dir>/scripts/rag/index_vault.py --vault . --status
python3 <skill-dir>/scripts/rag/query_vault.py --vault . "关键词或问题" --course <course>
python3 <skill-dir>/scripts/rag/retrieve_context.py --vault . --task final-review --course <course> --scope <scope>
```

Normal indexing is incremental. Use `--force` only for a deliberate full rebuild. The index defaults to `.course-study/rag_index.sqlite`; treat it as a disposable local cache and exclude it from version control.

Before relying on retrieval, check status. If the index is missing, stale, has an old schema, or its configuration changed, rebuild it.

## Optional Configuration

Create a conservative project config:

```bash
python3 <skill-dir>/scripts/rag/init_config.py --vault .
```

The root-level `course-study.json` supports:

- `rag.include_dirs`: explicit Markdown files or folders to index; an empty list uses automatic discovery.
- `rag.exclude_globs`: project-relative exclusion patterns.
- `rag.include_extracted`: include local raw-source text under `.course-study/extracted/`.
- `rag.chunk_chars` and `rag.chunk_overlap`: chunk size and overlap.
- `rag.candidate_limit`: number of BM25 candidates considered.
- `rag.per_source_limit`: maximum selected chunks per source.
- `rag.diversity`: strength of duplicate-result suppression.
- `rag.dedupe_threshold`: Jaccard threshold for removing near-identical chunks.
- `rag.minimum_should_match`: minimum fraction of meaningful query tokens required in a lexical result.
- `rag.neighbor_window`: surrounding chunks included as context.
- `rag.index_navigation`: whether project/course index pages are indexed with automatic downranking.
- `rag.stopwords`: project-specific filler words to remove from queries.
- `rag.synonyms`: mappings such as `"人工智能": ["AI", "artificial intelligence"]` for bilingual terminology.

Changing retrieval configuration makes the old index stale and requires rebuilding.

## Offline Raw-Source Extraction

Structured notes remain the preferred retrieval source. When immediate raw-text retrieval is useful, extract a local PPTX, PDF, DOCX, Markdown, or text file:

```bash
python3 <skill-dir>/scripts/rag/extract_source.py <project-relative-source> --vault .
python3 <skill-dir>/scripts/rag/init_config.py --vault . --include-extracted
python3 <skill-dir>/scripts/rag/index_vault.py --vault .
```

PPTX and DOCX use built-in ZIP/XML parsing. PDF uses an already-installed local `pdftotext` or `pypdf`; no dependency is downloaded automatically. Legacy `.ppt`, images, scans, diagrams, formulas, and layout require a suitable local conversion/OCR workflow and visual verification. Never treat extracted text as a substitute for checking the original when layout carries meaning.

## Offline Evaluation

Create a JSONL file with one case per line:

```json
{"query":"需求曲线为什么向下倾斜","expected_sources":["Week 01 Supply and Demand.md"]}
```

Then run:

```bash
python3 <skill-dir>/scripts/rag/evaluate_rag.py evaluation.jsonl --vault . --top-k 5 --min-hit-rate 0.8
```

The report includes top-k hit rate, top-1 accuracy, hit@3, mean reciprocal rank, nDCG@k, and returned source paths. Keep evaluation cases free of answer text so the test measures retrieval rather than memorized output.

## Retrieval Guidance

- Narrow by course, week, document type, task, or original English terminology when results are broad.
- Prefer structured notes and semantic summaries over extracted raw text.
- Keep source paths in any generated context or answer.
- If retrieved evidence is insufficient, say so and inspect the specific source material required next.
- Do not index private files, logs, answer keys, or unrelated folders unless project rules explicitly allow it.
