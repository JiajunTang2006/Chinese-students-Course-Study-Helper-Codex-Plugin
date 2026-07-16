---
name: course-study-agent
description: Process university course materials for Chinese undergraduate study workflows. Use when Codex needs to read PPT/PPTX, PDF, Word/DOCX, or Markdown course materials; create Chinese chapter or weekly notes; analyze assignment requirements and plan work; prepare midterm or final review materials; derive mock exams from past papers; retrieve local course-note context with offline RAG; or discover, fingerprint, deduplicate, and track course source files across computing, business, science, engineering, humanities, and other disciplines.
---

# Course Study Agent

Provide reusable course-processing capabilities while treating the current project's `AGENTS.md` and user request as the source of project-specific behavior.

## Resolve Project Rules

1. Locate the project root and read its applicable `AGENTS.md` files before changing files.
2. Read the project's course index, configuration, and target-course control files when present.
3. Apply this precedence: current user request, project rules, project configuration, then this skill's defaults.
4. Do not impose a course folder layout, naming convention, question count, bilingual format, manifest schema, or logging policy when the project already defines one.
5. Treat source materials as read-only unless the user explicitly requests source-file editing.

Read [references/project-contract.md](references/project-contract.md) when onboarding a new project or when its structure is unclear.

## Route the Task

- For PPT/PPTX, PDF, DOCX, or Markdown ingestion, read [references/material-processing.md](references/material-processing.md).
- For weekly or chapter notes, also read [references/study-notes.md](references/study-notes.md).
- For assignment analysis and planning, read [references/assignments.md](references/assignments.md).
- For midterm/final review or past-paper-based mock exams, read [references/review-and-mock-exams.md](references/review-and-mock-exams.md).
- For local retrieval, read [references/local-rag.md](references/local-rag.md). Check index freshness before querying; rebuild incrementally when stale. Prefer structured notes, and use offline raw-source extraction only when the project permits it and the original layout will still be verified.
- When a project provides local discovery, manifest, duplicate, or validation tools, use them only as directed by that project's `AGENTS.md`; do not treat their schema as a universal Plugin rule.

## Use General Defaults

Use these only when the project and user provide no more specific rule:

- Explain primarily in Simplified Chinese.
- Preserve necessary original-language terminology, symbols, formulas, citations, and code.
- Reorganize material for learning; do not translate slides page by page.
- Separate source-grounded content from model-supplied explanation.
- Prefer a chapter or week structure when the source provides a clear sequence.
- For assignments, analyze requirements, deliverables, constraints, grading signals, dependencies, and a completion plan before drafting content.
- For reviews, integrate existing notes before rereading every raw source.
- Use past papers to approximate style and coverage, never to claim prediction of the real exam.
- Adapt examples and question types to the discipline instead of assuming a computing course.
- Mark unclear scans, handwriting, formulas, or source conflicts as uncertain.

## Verify Before Updating Status

1. Create or update the real study artifact first.
2. Verify the artifact exists and follows project rules.
3. Update indexes, manifests, or logs only when the project requires them.
4. Mark a source processed only after the intended artifact exists.
5. Inspect the relevant diff and preserve unrelated user changes.

Do not automatically commit, push, delete, move, or overwrite ambiguous files unless the user explicitly requests that action.

## Report

Lead with the outcome. Include the course or subject, sources used, files created or updated, validation status, inferred chapter/week with its evidence, and unresolved source uncertainty. Treat generated study material as a draft for student review.
