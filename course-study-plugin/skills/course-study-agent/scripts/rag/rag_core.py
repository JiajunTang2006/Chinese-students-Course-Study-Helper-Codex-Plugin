from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = "3"
VAULT_ROOT = Path(os.environ.get("COURSE_STUDY_VAULT", Path.cwd())).expanduser().resolve()
INDEX_PATH = Path(
    os.environ.get("COURSE_STUDY_INDEX", VAULT_ROOT / ".course-study" / "rag_index.sqlite")
).expanduser().resolve()

DEFAULT_INDEXABLE_COURSE_DIRS = (
    "02wiki/notes",
    "02wiki/tutorials",
    "02wiki/assignments",
    "02wiki/questions",
    "02wiki/misc",
    "03outputs/notes",
    "03outputs/review-sheets",
)
DEFAULT_EXCLUDED_PARTS = {
    ".git",
    ".obsidian",
    ".course-study",
    "01raw",
    "raw",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "__pycache__",
}
DEFAULT_EXCLUDED_NAMES = {
    "agents.md",
    "log.md",
    "_log.md",
    "_log_archive.md",
    "_raw_manifest.md",
}
PLACEHOLDER_RE = re.compile(
    r"^(?:to be added|tbd|todo|n/?a|none|暂无|待添加|尚未添加|无内容)[.!。\s-]*$",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
WEEK_RE = re.compile(r"\b(?:week|w|lecture|l)\s*0?(\d{1,2})\b", re.IGNORECASE)
EN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#./-]*|\d+")
CJK_SEQUENCE_RE = re.compile(r"[\u3400-\u9fff]+")

EN_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "could",
    "explain",
    "for",
    "how",
    "is",
    "of",
    "please",
    "the",
    "to",
    "what",
    "which",
    "why",
}
CJK_QUERY_FILLERS = (
    "请你帮我",
    "请帮我",
    "请解释一下",
    "解释一下",
    "为什么",
    "什么是",
    "是什么",
    "怎么样",
    "有哪些",
    "请解释",
    "如何",
    "怎么",
    "请问",
    "一下",
)

TASK_QUERY_TERMS = {
    "mock-exam": "模拟考试 练习题 答案 解析 exam practice questions answers",
    "final-review": "期末复习 重点 总结 公式 模型 checklist final review",
    "midterm-review": "期中复习 重点 总结 公式 模型 checklist midterm review",
    "assignment": "作业 要求 交付物 评分标准 assignment deliverables rubric",
    "weekly-note": "前置知识 核心概念 章节总结 previous concepts weekly note",
    "chapter-note": "前置知识 核心概念 章节总结 previous concepts chapter note",
    "tutorial": "教程 方法 例题 常见错误 tutorial methods examples",
}


@dataclass(frozen=True)
class RAGConfig:
    include_dirs: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    include_extracted: bool = False
    chunk_chars: int = 2400
    chunk_overlap: int = 180
    candidate_limit: int = 80
    per_source_limit: int = 2
    diversity: float = 0.22
    dedupe_threshold: float = 0.92
    minimum_should_match: float = 0.18
    neighbor_window: int = 1
    index_navigation: bool = True
    stopwords: tuple[str, ...] = ()
    synonyms: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    area: str
    folder: str

    @property
    def path(self) -> Path:
        return VAULT_ROOT / self.folder

    @property
    def display_name(self) -> str:
        return f"{self.code} {self.name}".strip()


@dataclass(frozen=True)
class IndexableFile:
    path: Path
    course: Course | None


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_path: str
    course_code: str
    course_name: str
    course_folder: str
    doc_type: str
    week: str
    week_number: int | None
    topic: str
    heading: str
    heading_path: str
    section_kind: str
    ordinal: int
    text: str
    modified: float
    size: int


def configure(vault: str | Path = ".", index_path: str | Path | None = None) -> None:
    """Configure one project-local retrieval session."""
    global VAULT_ROOT, INDEX_PATH
    VAULT_ROOT = Path(vault).expanduser().resolve()
    INDEX_PATH = (
        Path(index_path).expanduser().resolve()
        if index_path
        else VAULT_ROOT / ".course-study" / "rag_index.sqlite"
    )
    if not VAULT_ROOT.is_dir():
        raise FileNotFoundError(f"Project root does not exist: {VAULT_ROOT}")


def clamp_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, parsed))


def clamp_float(value: object, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, parsed))


def load_config(root: Path | None = None) -> RAGConfig:
    root = root or VAULT_ROOT
    path = root / "course-study.json"
    if not path.is_file():
        return RAGConfig()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid course-study.json: {exc}") from exc
    rag = payload.get("rag", {}) if isinstance(payload, dict) else {}
    if not isinstance(rag, dict):
        raise ValueError("course-study.json field 'rag' must be an object")
    include_dirs = rag.get("include_dirs", [])
    exclude_globs = rag.get("exclude_globs", [])
    stopwords = rag.get("stopwords", [])
    synonyms = rag.get("synonyms", {})
    if not isinstance(include_dirs, list) or not all(isinstance(item, str) for item in include_dirs):
        raise ValueError("rag.include_dirs must be a list of paths")
    if not isinstance(exclude_globs, list) or not all(isinstance(item, str) for item in exclude_globs):
        raise ValueError("rag.exclude_globs must be a list of glob patterns")
    if not isinstance(stopwords, list) or not all(isinstance(item, str) for item in stopwords):
        raise ValueError("rag.stopwords must be a list of strings")
    if not isinstance(synonyms, dict) or not all(
        isinstance(key, str)
        and isinstance(values, list)
        and all(isinstance(value, str) for value in values)
        for key, values in synonyms.items()
    ):
        raise ValueError("rag.synonyms must map each string to a list of strings")
    return RAGConfig(
        include_dirs=tuple(item.strip().strip("/") for item in include_dirs if item.strip()),
        exclude_globs=tuple(item.strip() for item in exclude_globs if item.strip()),
        include_extracted=bool(rag.get("include_extracted", False)),
        chunk_chars=clamp_int(rag.get("chunk_chars"), 2400, 600, 8000),
        chunk_overlap=clamp_int(rag.get("chunk_overlap"), 180, 0, 1000),
        candidate_limit=clamp_int(rag.get("candidate_limit"), 80, 10, 500),
        per_source_limit=clamp_int(rag.get("per_source_limit"), 2, 1, 10),
        diversity=clamp_float(rag.get("diversity"), 0.22, 0.0, 0.8),
        dedupe_threshold=clamp_float(rag.get("dedupe_threshold"), 0.92, 0.70, 1.0),
        minimum_should_match=clamp_float(rag.get("minimum_should_match"), 0.18, 0.0, 1.0),
        neighbor_window=clamp_int(rag.get("neighbor_window"), 1, 0, 3),
        index_navigation=bool(rag.get("index_navigation", True)),
        stopwords=tuple(item.strip().casefold() for item in stopwords if item.strip()),
        synonyms=tuple(
            (
                key.strip(),
                tuple(value.strip() for value in values if value.strip()),
            )
            for key, values in sorted(synonyms.items())
            if key.strip()
        ),
    )


def config_hash(config: RAGConfig) -> str:
    return hashlib.sha256(json.dumps(config.__dict__, sort_keys=True).encode()).hexdigest()


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(VAULT_ROOT).as_posix()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def load_courses() -> list[Course]:
    index_path = VAULT_ROOT / "index.md"
    courses: list[Course] = []
    if index_path.exists():
        for line in read_text(index_path).splitlines():
            if not line.strip().startswith("|"):
                continue
            parts = [part.strip() for part in line.strip().strip("|").split("|")]
            if len(parts) < 4 or parts[0] in {"Code", "---"} or set(parts[0]) == {"-"}:
                continue
            folder_match = re.search(r"`([^`]*courses/[^`]+/)`", parts[3])
            if not folder_match:
                continue
            courses.append(
                Course(
                    code=parts[0],
                    name=parts[1],
                    area=parts[2],
                    folder=folder_match.group(1).rstrip("/"),
                )
            )
    if courses:
        return courses

    courses_dir = VAULT_ROOT / "courses"
    if courses_dir.is_dir():
        for path in sorted(courses_dir.iterdir()):
            if not path.is_dir() or path.name.startswith("."):
                continue
            parts = path.name.split(maxsplit=1)
            courses.append(
                Course(
                    code=parts[0] if len(parts) > 1 else "",
                    name=parts[1] if len(parts) > 1 else parts[0],
                    area="",
                    folder=path.relative_to(VAULT_ROOT).as_posix(),
                )
            )
    if not courses:
        courses.append(Course(code="", name=VAULT_ROOT.name, area="", folder="."))
    return courses


def course_for_path(path: Path, courses: list[Course]) -> Course | None:
    resolved = path.resolve()
    matches: list[tuple[int, Course]] = []
    for course in courses:
        try:
            resolved.relative_to(course.path.resolve())
            matches.append((len(course.path.parts), course))
        except ValueError:
            continue
    return max(matches, default=(0, None), key=lambda item: item[0])[1]


def infer_doc_type(path: Path, course: Course | None) -> str:
    rel = relative_path(path)
    lowered = f"/{rel.lower()}/"
    if rel == "index.md":
        return "root-index"
    if course and rel == f"{course.folder}/_index.md":
        return "course-index"
    if "/.course-study/extracted/" in lowered:
        return "raw-source"
    if "/02wiki/notes/" in rel:
        return "weekly-note"
    if "/02wiki/tutorials/" in rel:
        return "tutorial"
    if "/02wiki/assignments/" in rel:
        return "assignment"
    if "/02wiki/questions/" in rel:
        return "question"
    if "/02wiki/misc/" in rel:
        return "wiki-misc"
    if "/03outputs/review-sheets/" in rel:
        return "review-sheet"
    if "/03outputs/notes/" in rel:
        return "output-note"
    if "/assignments/" in lowered or "/assignment/" in lowered:
        return "assignment"
    if "/questions/" in lowered or "/question-bank/" in lowered:
        return "question"
    if "/review/" in lowered or "/reviews/" in lowered or "/exam/" in lowered:
        return "review-sheet"
    if "/tutorial/" in lowered or "/tutorials/" in lowered:
        return "tutorial"
    if "/notes/" in lowered or "/wiki/" in lowered:
        return "study-note"
    return "markdown"


def infer_week(path: Path, text: str) -> str:
    for value in (path.stem, text[:700]):
        match = WEEK_RE.search(value)
        if match:
            return f"Week {int(match.group(1)):02d}"
    chinese = re.search(r"第\s*([0-9一二三四五六七八九十]+)\s*(?:周|讲)", text[:700])
    return chinese.group(0).replace(" ", "") if chinese else ""


def infer_topic(path: Path, week: str) -> str:
    topic = path.stem.replace("_", " ").strip()
    topic = re.sub(r"\b(?:note|tutorial|guidance)\b", "", topic, flags=re.IGNORECASE).strip()
    topic = WEEK_RE.sub("", topic).strip(" -_")
    topic = re.sub(r"\s+", " ", topic)
    return topic or week or path.stem


def classify_section(heading_path: str) -> str:
    lowered = heading_path.lower()
    if "semantic summary" in lowered or "语义摘要" in heading_path:
        return "semantic-summary"
    if "answers and explanations" in lowered or re.search(r"\banswers\b", lowered) or "答案" in heading_path:
        return "practice-answers"
    if "questions" in lowered or "in-class practice" in lowered or "练习题" in heading_path:
        return "practice-questions"
    if "source" in lowered or "来源" in heading_path:
        return "source"
    if "my understanding" in lowered or "我的理解" in heading_path:
        return "student-understanding"
    if "open questions" in lowered or "待确认" in heading_path:
        return "open-questions"
    return "content"


def logical_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    current: list[str] = []
    fenced = False
    fence_marker = ""

    def flush() -> None:
        if current:
            value = "\n".join(current).strip()
            if value:
                blocks.append(value)
            current.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not fenced:
                flush()
                fenced = True
                fence_marker = marker
            current.append(line)
            if fenced and stripped == fence_marker and len(current) > 1:
                fenced = False
                flush()
            continue
        if fenced:
            current.append(line)
            continue
        if not stripped:
            flush()
            continue
        if stripped.startswith("|"):
            if current and not current[-1].lstrip().startswith("|"):
                flush()
            current.append(line)
            continue
        if current and current[-1].lstrip().startswith("|"):
            flush()
        current.append(line)
    flush()
    return blocks


def hard_split(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind("。", start, end), text.rfind(". ", start, end))
            if boundary > start + max_chars // 2:
                end = boundary + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [part for part in parts if part]


def split_long_text(text: str, max_chars: int = 2400, overlap: int = 180) -> list[str]:
    blocks = logical_blocks(text)
    if not blocks:
        return []
    parts: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > max_chars:
            if current:
                parts.append(current.strip())
                current = ""
            parts.extend(hard_split(block, max_chars, overlap))
            continue
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            parts.append(current.strip())
            tail = current[-overlap:].strip() if overlap else ""
            current = f"{tail}\n\n{block}".strip() if tail else block
    if current:
        parts.append(current.strip())
    return parts


def markdown_sections(text: str) -> list[tuple[str, str, str]]:
    sections: list[tuple[str, str, str]] = []
    stack: list[str] = []
    current_heading = "Document"
    current_path = "Document"
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            sections.append((current_heading, current_path, content))

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            stack[:] = stack[: level - 1]
            stack.append(title)
            current_heading = title
            current_path = " > ".join(stack)
            buffer = [line]
        else:
            buffer.append(line)
    flush()
    return sections


def path_matches_globs(rel: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(Path(rel).name, pattern) for pattern in patterns)


def is_excluded_markdown(path: Path, config: RAGConfig, allow_extracted: bool = False) -> bool:
    rel_path = path.resolve().relative_to(VAULT_ROOT)
    rel = rel_path.as_posix()
    if allow_extracted and rel.startswith(".course-study/extracted/"):
        return False
    if is_hidden(rel_path):
        return True
    lowered_parts = {part.casefold() for part in rel_path.parts}
    if lowered_parts & DEFAULT_EXCLUDED_PARTS:
        return True
    if path.name.casefold() in DEFAULT_EXCLUDED_NAMES:
        return True
    return path_matches_globs(rel, config.exclude_globs)


def iter_directory_markdown(folder: Path, courses: list[Course], config: RAGConfig) -> Iterable[IndexableFile]:
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob("*.md")):
        if not is_excluded_markdown(path, config):
            yield IndexableFile(path=path, course=course_for_path(path, courses))


def iter_indexable_files(config: RAGConfig | None = None) -> Iterable[IndexableFile]:
    config = config or load_config()
    courses = load_courses()
    yielded: set[Path] = set()

    def emit(item: IndexableFile) -> IndexableFile | None:
        resolved = item.path.resolve()
        if resolved in yielded:
            return None
        yielded.add(resolved)
        return item

    root_index = VAULT_ROOT / "index.md"
    if config.index_navigation and root_index.is_file():
        item = emit(IndexableFile(root_index, None))
        if item:
            yield item

    if config.include_dirs:
        for relative in config.include_dirs:
            target = (VAULT_ROOT / relative).resolve()
            try:
                target.relative_to(VAULT_ROOT)
            except ValueError as exc:
                raise ValueError(f"Configured include path escapes project root: {relative}") from exc
            if target.is_file() and target.suffix.casefold() == ".md":
                candidates = [IndexableFile(target, course_for_path(target, courses))]
            else:
                candidates = iter_directory_markdown(target, courses, config)
            for candidate in candidates:
                item = emit(candidate)
                if item:
                    yield item
    else:
        found_structured = False
        for course in courses:
            course_index = course.path / "_index.md"
            if config.index_navigation and course_index.is_file():
                item = emit(IndexableFile(course_index, course))
                if item:
                    yield item
            course_found = False
            for rel_dir in DEFAULT_INDEXABLE_COURSE_DIRS:
                folder = course.path / rel_dir
                if not folder.is_dir():
                    continue
                found_structured = course_found = True
                for candidate in iter_directory_markdown(folder, courses, config):
                    item = emit(candidate)
                    if item:
                        yield item
            if not course_found and course.folder != ".":
                for candidate in iter_directory_markdown(course.path, courses, config):
                    item = emit(candidate)
                    if item:
                        yield item
        if not found_structured and len(courses) == 1 and courses[0].folder == ".":
            for candidate in iter_directory_markdown(VAULT_ROOT, courses, config):
                item = emit(candidate)
                if item:
                    yield item

    if config.include_extracted:
        extracted = VAULT_ROOT / ".course-study" / "extracted"
        if extracted.is_dir():
            for path in sorted(extracted.rglob("*.md")):
                if is_excluded_markdown(path, config, allow_extracted=True):
                    continue
                course = course_for_path(path, courses)
                if course is None:
                    header = read_text(path)[:1500]
                    match = re.search(r"Original source:\s*`([^`]+)`", header, re.IGNORECASE)
                    if match:
                        original = (VAULT_ROOT / match.group(1)).resolve()
                        try:
                            original.relative_to(VAULT_ROOT)
                        except ValueError:
                            original = path
                        course = course_for_path(original, courses)
                item = emit(IndexableFile(path, course))
                if item:
                    yield item


def chunks_for_file(item: IndexableFile, config: RAGConfig) -> list[Chunk]:
    path, course = item.path, item.course
    text = read_text(path)
    stat = path.stat()
    rel = relative_path(path)
    doc_type = infer_doc_type(path, course)
    week = infer_week(path, text)
    topic = infer_topic(path, week)
    chunks: list[Chunk] = []
    ordinal = 0

    for heading, heading_path, section_text in markdown_sections(text):
        for part in split_long_text(section_text, config.chunk_chars, config.chunk_overlap):
            ordinal += 1
            key = f"{rel}:{heading_path}:{ordinal}:{hashlib.sha1(part.encode('utf-8')).hexdigest()}"
            chunk_id = hashlib.sha1(key.encode("utf-8")).hexdigest()
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    source_path=rel,
                    course_code=course.code if course else "",
                    course_name=course.name if course else "Vault",
                    course_folder=course.folder if course else "",
                    doc_type=doc_type,
                    week=week,
                    week_number=resolve_week_number(week),
                    topic=topic,
                    heading=heading,
                    heading_path=heading_path,
                    section_kind=classify_section(heading_path),
                    ordinal=ordinal,
                    text=part,
                    modified=stat.st_mtime,
                    size=stat.st_size,
                )
            )
    return chunks


def connect(index_path: Path | None = None) -> sqlite3.Connection:
    path = index_path or INDEX_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            course_code TEXT,
            course_name TEXT,
            course_folder TEXT,
            doc_type TEXT,
            week TEXT,
            week_number INTEGER,
            topic TEXT,
            heading TEXT,
            heading_path TEXT,
            section_kind TEXT,
            ordinal INTEGER,
            text TEXT NOT NULL,
            modified REAL,
            size INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_path, ordinal);
        CREATE INDEX IF NOT EXISTS idx_chunks_course ON chunks(course_code, course_name);
        CREATE INDEX IF NOT EXISTS idx_chunks_type_week ON chunks(doc_type, week_number);

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED,
            course_text,
            title_text,
            body_text,
            token_text,
            tokenize = 'unicode61 remove_diacritics 2'
        );

        CREATE TABLE IF NOT EXISTS files (
            source_path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            modified_ns INTEGER NOT NULL,
            size INTEGER NOT NULL,
            indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def get_meta(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {str(row["key"]): str(row["value"]) for row in rows}


def cjk_ngrams(text: str, sizes: tuple[int, ...] = (2, 3)) -> list[str]:
    grams: list[str] = []
    for sequence in CJK_SEQUENCE_RE.findall(text):
        if len(sequence) == 1:
            grams.append(sequence)
            continue
        for size in sizes:
            if len(sequence) < size:
                continue
            grams.extend(sequence[index : index + size] for index in range(len(sequence) - size + 1))
    return grams


def english_tokens(text: str) -> list[str]:
    return [token.casefold() for token in EN_TOKEN_RE.findall(text)]


def lexical_tokens(text: str, limit: int | None = None) -> list[str]:
    tokens = english_tokens(text) + cjk_ngrams(text)
    deduped = list(dict.fromkeys(token for token in tokens if token.strip()))
    return deduped[:limit] if limit else deduped


def clean_query_text(query: str, config: RAGConfig) -> str:
    cleaned = query.casefold()
    for phrase in (*CJK_QUERY_FILLERS, *config.stopwords):
        if phrase:
            cleaned = cleaned.replace(phrase.casefold(), " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def base_query_tokens(query: str, config: RAGConfig, limit: int | None = None) -> list[str]:
    cleaned = clean_query_text(query, config)
    custom_stop_tokens = set(lexical_tokens(" ".join(config.stopwords)))
    tokens = [
        token
        for token in lexical_tokens(cleaned)
        if token not in EN_QUERY_STOPWORDS and token not in custom_stop_tokens
    ]
    deduped = list(dict.fromkeys(tokens))
    return deduped[:limit] if limit else deduped


def synonym_expansions(query: str, config: RAGConfig) -> list[str]:
    query_l = query.casefold()
    expansions: list[str] = []
    for canonical, aliases in config.synonyms:
        group = (canonical, *aliases)
        if any(term.casefold() in query_l for term in group):
            expansions.extend(group)
    return list(dict.fromkeys(expansions))


def query_tokens(query: str, config: RAGConfig, limit: int | None = None) -> list[str]:
    tokens = base_query_tokens(query, config)
    for expansion in synonym_expansions(query, config):
        tokens.extend(lexical_tokens(expansion))
    deduped = list(dict.fromkeys(token for token in tokens if token.strip()))
    return deduped[:limit] if limit else deduped


def synonym_hit(query: str, haystack: str, config: RAGConfig) -> bool:
    query_l = query.casefold()
    haystack_l = haystack.casefold()
    for canonical, aliases in config.synonyms:
        group = (canonical, *aliases)
        queried = [term for term in group if term.casefold() in query_l]
        if queried and any(term.casefold() in haystack_l for term in group if term not in queried):
            return True
    return False


def fts_payload(chunk: Chunk) -> tuple[str, str, str, str]:
    course_text = "\n".join([chunk.course_code, chunk.course_name, chunk.doc_type, chunk.week])
    title_text = "\n".join([chunk.topic, chunk.heading_path])
    body_text = chunk.text
    token_text = " ".join(lexical_tokens("\n".join([course_text, title_text, body_text])))
    return course_text, title_text, body_text, token_text


def delete_source(conn: sqlite3.Connection, source_path: str) -> None:
    ids = [row[0] for row in conn.execute("SELECT chunk_id FROM chunks WHERE source_path = ?", (source_path,))]
    if ids:
        conn.executemany("DELETE FROM chunks_fts WHERE chunk_id = ?", ((chunk_id,) for chunk_id in ids))
    conn.execute("DELETE FROM chunks WHERE source_path = ?", (source_path,))
    conn.execute("DELETE FROM files WHERE source_path = ?", (source_path,))


def insert_file(conn: sqlite3.Connection, item: IndexableFile, config: RAGConfig, digest: str) -> int:
    rel = relative_path(item.path)
    stat = item.path.stat()
    chunks = chunks_for_file(item, config)
    for chunk in chunks:
        conn.execute(
            """
            INSERT INTO chunks VALUES (
                :chunk_id, :source_path, :course_code, :course_name,
                :course_folder, :doc_type, :week, :week_number, :topic, :heading,
                :heading_path, :section_kind, :ordinal, :text, :modified, :size
            )
            """,
            chunk.__dict__,
        )
        course_text, title_text, body_text, token_text = fts_payload(chunk)
        conn.execute(
            "INSERT INTO chunks_fts(chunk_id, course_text, title_text, body_text, token_text) VALUES (?, ?, ?, ?, ?)",
            (chunk.chunk_id, course_text, title_text, body_text, token_text),
        )
    conn.execute(
        "INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, ?)",
        (rel, digest, stat.st_mtime_ns, stat.st_size, datetime.now().isoformat(timespec="seconds")),
    )
    return len(chunks)


def create_fresh_index(index_path: Path, config: RAGConfig) -> dict[str, object]:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="rag-index-", suffix=".sqlite", dir=index_path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
    temp_path.unlink(missing_ok=True)
    file_count = 0
    chunk_count = 0
    try:
        conn = connect(temp_path)
        init_db(conn)
        with conn:
            for item in iter_indexable_files(config):
                digest = content_hash(item.path)
                chunk_count += insert_file(conn, item, config, digest)
                file_count += 1
            meta = {
                "schema_version": SCHEMA_VERSION,
                "built_at": datetime.now().isoformat(timespec="seconds"),
                "vault_root": str(VAULT_ROOT),
                "file_count": str(file_count),
                "chunk_count": str(chunk_count),
                "config_hash": config_hash(config),
            }
            conn.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", meta.items())
        conn.close()
        os.replace(temp_path, index_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return {
        "index_path": str(index_path),
        "mode": "full",
        "file_count": file_count,
        "chunk_count": chunk_count,
        "added": file_count,
        "updated": 0,
        "removed": 0,
        "unchanged": 0,
    }


def build_index(index_path: Path | None = None, force: bool = False) -> dict[str, object]:
    path = index_path or INDEX_PATH
    config = load_config()
    if force or not path.exists():
        return create_fresh_index(path, config)

    conn = connect(path)
    meta = get_meta(conn)
    expected_config_hash = config_hash(config)
    if meta.get("schema_version") != SCHEMA_VERSION or meta.get("config_hash") != expected_config_hash:
        conn.close()
        return create_fresh_index(path, config)

    existing = {
        str(row["source_path"]): row
        for row in conn.execute("SELECT source_path, content_hash, modified_ns, size FROM files")
    }
    current = {relative_path(item.path): item for item in iter_indexable_files(config)}
    added = updated = removed = unchanged = 0
    chunk_delta = 0

    with conn:
        for rel in sorted(set(existing) - set(current)):
            old_count = conn.execute("SELECT COUNT(*) FROM chunks WHERE source_path = ?", (rel,)).fetchone()[0]
            delete_source(conn, rel)
            chunk_delta -= int(old_count)
            removed += 1

        for rel, item in current.items():
            stat = item.path.stat()
            old = existing.get(rel)
            if old and int(old["modified_ns"]) == stat.st_mtime_ns and int(old["size"]) == stat.st_size:
                unchanged += 1
                continue
            digest = content_hash(item.path)
            if old and str(old["content_hash"]) == digest:
                conn.execute(
                    "UPDATE files SET modified_ns = ?, size = ? WHERE source_path = ?",
                    (stat.st_mtime_ns, stat.st_size, rel),
                )
                unchanged += 1
                continue
            if old:
                old_count = conn.execute("SELECT COUNT(*) FROM chunks WHERE source_path = ?", (rel,)).fetchone()[0]
                delete_source(conn, rel)
                chunk_delta -= int(old_count)
                updated += 1
            else:
                added += 1
            chunk_delta += insert_file(conn, item, config, digest)

        file_count = int(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])
        chunk_count = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        new_meta = {
            "schema_version": SCHEMA_VERSION,
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "vault_root": str(VAULT_ROOT),
            "file_count": str(file_count),
            "chunk_count": str(chunk_count),
            "config_hash": expected_config_hash,
        }
        conn.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", new_meta.items())
    conn.close()
    return {
        "index_path": str(path),
        "mode": "incremental",
        "file_count": file_count,
        "chunk_count": chunk_count,
        "added": added,
        "updated": updated,
        "removed": removed,
        "unchanged": unchanged,
        "chunk_delta": chunk_delta,
    }


def index_exists(index_path: Path | None = None) -> bool:
    return (index_path or INDEX_PATH).exists()


def get_stats(index_path: Path | None = None) -> dict[str, str]:
    path = index_path or INDEX_PATH
    if not path.exists():
        return {}
    conn = connect(path)
    rows = conn.execute("SELECT key, value FROM meta ORDER BY key").fetchall()
    conn.close()
    return {str(row["key"]): str(row["value"]) for row in rows}


def get_index_status(index_path: Path | None = None) -> dict[str, object]:
    path = index_path or INDEX_PATH
    if not path.exists():
        return {"exists": False, "stale": True, "reason": "missing", "new": [], "updated": [], "removed": []}
    config = load_config()
    conn = connect(path)
    meta = get_meta(conn)
    if meta.get("schema_version") != SCHEMA_VERSION:
        conn.close()
        return {"exists": True, "stale": True, "reason": "schema", "new": [], "updated": [], "removed": []}
    if meta.get("config_hash") != config_hash(config):
        conn.close()
        return {"exists": True, "stale": True, "reason": "config", "new": [], "updated": [], "removed": []}
    indexed = {
        str(row["source_path"]): (int(row["modified_ns"]), int(row["size"]))
        for row in conn.execute("SELECT source_path, modified_ns, size FROM files")
    }
    conn.close()
    current = {relative_path(item.path): item.path.stat() for item in iter_indexable_files(config)}
    new = sorted(set(current) - set(indexed))
    removed = sorted(set(indexed) - set(current))
    updated = sorted(
        rel for rel in set(indexed) & set(current) if indexed[rel] != (current[rel].st_mtime_ns, current[rel].st_size)
    )
    return {
        "exists": True,
        "stale": bool(new or updated or removed),
        "reason": "files" if new or updated or removed else "current",
        "new": new,
        "updated": updated,
        "removed": removed,
        "stats": meta,
    }


def resolve_week_number(value: str) -> int | None:
    match = WEEK_RE.search(value)
    if match:
        return int(match.group(1))
    if value.isdigit():
        return int(value)
    chinese = re.search(r"第\s*([一二三四五六七八九十]+)\s*(?:周|讲)", value)
    if not chinese:
        return None
    number = chinese.group(1)
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if number == "十":
        return 10
    if "十" in number:
        tens, ones = number.split("十", 1)
        return (digits.get(tens, 1) * 10) + digits.get(ones, 0)
    return digits.get(number)


def fts_query(query: str, config: RAGConfig) -> str:
    tokens = query_tokens(query, config, limit=64)
    safe = [token.replace('"', '""') for token in tokens if len(token) > 1 or token.isdigit()]
    return " OR ".join(f'"{token}"' for token in safe)


def metadata_sql(
    course: str | None,
    doc_type: str | None,
    week: str | None,
) -> tuple[list[str], list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    if course:
        course_l = course.casefold()
        clauses.append("(lower(c.course_code) = ? OR lower(c.course_name) LIKE ? OR lower(c.course_folder) LIKE ?)")
        params.extend([course_l, f"%{course_l}%", f"%{course_l}%"])
    if doc_type:
        clauses.append("c.doc_type = ?")
        params.append(doc_type)
    if week:
        wanted = resolve_week_number(week)
        if wanted is not None:
            clauses.append("c.week_number = ?")
            params.append(wanted)
    return clauses, params


def fts_candidates(
    conn: sqlite3.Connection,
    query: str,
    course: str | None,
    doc_type: str | None,
    week: str | None,
    limit: int,
    config: RAGConfig,
) -> list[sqlite3.Row]:
    match = fts_query(query, config)
    if not match:
        return []
    clauses, params = metadata_sql(course, doc_type, week)
    where = ["chunks_fts MATCH ?", *clauses]
    sql = f"""
        SELECT c.*, bm25(chunks_fts, 0.0, 1.2, 4.0, 1.5, 0.8) AS bm25_value
        FROM chunks_fts
        JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
        WHERE {' AND '.join(where)}
        ORDER BY bm25_value
        LIMIT ?
    """
    return conn.execute(sql, [match, *params, limit]).fetchall()


def fallback_candidates(
    conn: sqlite3.Connection,
    course: str | None,
    doc_type: str | None,
    week: str | None,
) -> list[sqlite3.Row]:
    clauses, params = metadata_sql(course, doc_type, week)
    sql = f"SELECT c.*, 0.0 AS bm25_value FROM chunks c WHERE {' AND '.join(clauses) if clauses else '1 = 1'}"
    return conn.execute(sql, params).fetchall()


def is_placeholder(text: str) -> bool:
    meaningful = []
    for line in text.splitlines():
        if HEADING_RE.match(line) or re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*", line):
            continue
        stripped = re.sub(r"^[#>*\-\d.\s]+", "", line).strip()
        if stripped:
            meaningful.append(stripped)
    if not meaningful:
        return True
    return all(PLACEHOLDER_RE.match(line) for line in meaningful)


def task_boost(doc_type: str, section_kind: str, task: str) -> float:
    boost = 0.0
    if task in {"final-review", "midterm-review"}:
        boost += 6.0 if doc_type == "review-sheet" else 3.0 if doc_type in {"weekly-note", "study-note"} else 0.0
    elif task == "mock-exam":
        boost += 5.0 if doc_type in {"review-sheet", "question"} else 0.0
        boost += 4.0 if section_kind.startswith("practice") else 0.0
    elif task == "assignment":
        boost += 9.0 if doc_type == "assignment" else 2.0 if doc_type in {"weekly-note", "study-note"} else 0.0
    elif task in {"weekly-note", "chapter-note", "tutorial"}:
        boost += 5.0 if doc_type in {"weekly-note", "study-note", "tutorial"} else 0.0
    return boost


def score_row(
    row: sqlite3.Row,
    query: str,
    fts_rank: int | None,
    bm25_max: float,
    config: RAGConfig,
    task: str = "query",
    include_practice: bool = False,
) -> tuple[float, dict[str, float], float]:
    text = str(row["text"] or "")
    heading = str(row["heading_path"] or "")
    topic = str(row["topic"] or "")
    doc_type = str(row["doc_type"] or "")
    section_kind = str(row["section_kind"] or "")
    haystack = "\n".join([str(row["course_code"] or ""), str(row["course_name"] or ""), topic, heading, text])
    haystack_l = haystack.casefold()
    query_l = query.casefold().strip()
    components: dict[str, float] = {}

    raw_bm25 = max(0.0, -float(row["bm25_value"] or 0.0))
    if fts_rank is not None:
        normalized = raw_bm25 / bm25_max if bm25_max > 0 else 1.0 / (fts_rank + 1)
        components["bm25"] = 18.0 * normalized
        components["bm25_rank_tiebreak"] = 4.0 / math.sqrt(fts_rank + 1)

    cleaned_query = clean_query_text(query, config)
    if query_l and len(query_l) > 2 and (
        query_l in haystack_l or (len(cleaned_query) > 2 and cleaned_query in haystack_l)
    ):
        components["exact_phrase"] = 14.0

    query_terms = query_tokens(query, config, limit=64)
    base_terms = base_query_tokens(query, config, limit=48)
    title_hits = sum(1 for token in query_terms if token.casefold() in f"{topic} {heading}".casefold())
    body_hits = sum(1 for token in query_terms if token.casefold() in haystack_l)
    base_hits = sum(1 for token in base_terms if token.casefold() in haystack_l)
    coverage = base_hits / len(base_terms) if base_terms else 0.0
    has_synonym_hit = synonym_hit(query, haystack, config)
    if has_synonym_hit:
        coverage = max(coverage, 0.5)
        components["synonym"] = 8.0
    navigation_intent = bool(re.search(r"\bindex\b|索引|导航", query, re.IGNORECASE))
    if navigation_intent and doc_type in {"root-index", "course-index"}:
        coverage = max(coverage, 0.5)
        components["navigation_intent"] = 6.0
    components["title_terms"] = min(12.0, title_hits * 2.5)
    components["body_terms"] = min(10.0, body_hits * 0.7)
    components["term_coverage"] = min(8.0, coverage * 8.0)
    if section_kind == "semantic-summary":
        components["semantic_summary"] = 3.0
    components["task"] = task_boost(doc_type, section_kind, task)

    if fts_rank is not None and base_terms and coverage + 1e-9 < config.minimum_should_match:
        return 0.0, {"term_coverage": round(coverage, 4), "final": 0.0}, coverage

    # A database-wide fallback is useful for metadata-only task queries, but it
    # must not turn unrelated chunks into apparent lexical matches.
    if fts_rank is None and not (query_l in haystack_l or title_hits or body_hits or components["task"]):
        return 0.0, {"final": 0.0}, coverage

    score = sum(components.values())
    if is_placeholder(text):
        components["placeholder_multiplier"] = 0.03
        score *= 0.03
    if doc_type in {"root-index", "course-index"} and not navigation_intent:
        components["navigation_multiplier"] = 0.28
        score *= 0.28
    if doc_type == "raw-source":
        components["raw_source_multiplier"] = 0.75
        score *= 0.75
    if not include_practice and section_kind.startswith("practice"):
        components["practice_multiplier"] = 0.30
        score *= 0.30
    components["final"] = round(score, 4)
    return score, components, coverage


def similarity_tokens(item: dict[str, object]) -> set[str]:
    value = f"{item.get('heading_path', '')} {item.get('text', '')}"
    return set(lexical_tokens(value, limit=160))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def select_diverse(
    candidates: list[dict[str, object]],
    top_k: int,
    per_source_limit: int,
    diversity: float,
    dedupe_threshold: float,
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    source_counts: Counter[str] = Counter()
    remaining = list(candidates)
    token_cache = {str(item["chunk_id"]): similarity_tokens(item) for item in remaining}

    while remaining and len(selected) < top_k:
        best_index = -1
        best_adjusted = -1.0
        for index, item in enumerate(remaining):
            source = str(item["source_path"])
            if source_counts[source] >= per_source_limit:
                continue
            tokens = token_cache[str(item["chunk_id"])]
            max_similarity = max(
                (jaccard(tokens, token_cache[str(chosen["chunk_id"])]) for chosen in selected),
                default=0.0,
            )
            if selected and max_similarity >= dedupe_threshold:
                continue
            adjusted = float(item["score"]) * (1.0 - diversity * max_similarity)
            if source_counts[source]:
                adjusted *= 0.88
            if adjusted > best_adjusted:
                best_adjusted = adjusted
                best_index = index
        if best_index < 0:
            break
        chosen = remaining.pop(best_index)
        chosen["diversity_score"] = round(best_adjusted, 3)
        selected.append(chosen)
        source_counts[str(chosen["source_path"])] += 1
    return selected


def expand_neighbors(conn: sqlite3.Connection, item: dict[str, object], window: int) -> None:
    if window <= 0:
        item["context_text"] = item["text"]
        item["context_ordinals"] = [item["ordinal"]]
        return
    ordinal = int(item["ordinal"])
    rows = conn.execute(
        """
        SELECT ordinal, text FROM chunks
        WHERE source_path = ? AND ordinal BETWEEN ? AND ?
        ORDER BY ordinal
        """,
        (item["source_path"], max(1, ordinal - window), ordinal + window),
    ).fetchall()
    item["context_text"] = "\n\n".join(str(row["text"]) for row in rows)
    item["context_ordinals"] = [int(row["ordinal"]) for row in rows]


def search_chunks(
    query: str,
    course: str | None = None,
    doc_type: str | None = None,
    week: str | None = None,
    task: str = "query",
    include_practice: bool = False,
    top_k: int = 8,
    index_path: Path | None = None,
    candidate_limit: int | None = None,
    per_source_limit: int | None = None,
    neighbor_window: int | None = None,
) -> list[dict[str, object]]:
    path = index_path or INDEX_PATH
    if not path.exists():
        raise FileNotFoundError(f"RAG index not found: {path}")
    config = load_config()
    candidate_limit = candidate_limit or config.candidate_limit
    per_source_limit = per_source_limit or config.per_source_limit
    neighbor_window = config.neighbor_window if neighbor_window is None else neighbor_window

    conn = connect(path)
    used_fallback = False
    try:
        rows = fts_candidates(conn, query, course, doc_type, week, candidate_limit, config)
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        rows = fallback_candidates(conn, course, doc_type, week)
        used_fallback = True

    bm25_strengths = [max(0.0, -float(row["bm25_value"] or 0.0)) for row in rows] if not used_fallback else []
    bm25_max = max(bm25_strengths, default=0.0)
    scored: list[dict[str, object]] = []
    for rank, row in enumerate(rows):
        score, components, coverage = score_row(
            row,
            query=query,
            fts_rank=None if used_fallback else rank,
            bm25_max=bm25_max,
            config=config,
            task=task,
            include_practice=include_practice,
        )
        if score <= 0.05:
            continue
        item = dict(row)
        item["bm25_raw"] = round(max(0.0, -float(item.pop("bm25_value", 0.0) or 0.0)), 8)
        item["term_coverage"] = round(coverage, 4)
        item["score"] = round(score, 3)
        item["score_components"] = components
        scored.append(item)
    scored.sort(key=lambda item: (-float(item["score"]), str(item["source_path"]), int(item["ordinal"])))
    selected = select_diverse(
        scored,
        top_k,
        per_source_limit,
        config.diversity,
        config.dedupe_threshold,
    )
    for item in selected:
        expand_neighbors(conn, item, neighbor_window)
    conn.close()
    return selected


def make_snippet(text: str, query: str, max_chars: int = 450) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    lowered = compact.casefold()
    start = 0
    for token in lexical_tokens(query, limit=20):
        position = lowered.find(token.casefold())
        if position >= 0:
            start = max(0, position - 100)
            break
    end = min(len(compact), start + max_chars)
    return f"{'...' if start else ''}{compact[start:end]}{'...' if end < len(compact) else ''}"


def default_query_for_task(task: str, scope: str) -> str:
    base = scope.strip()
    supplement = TASK_QUERY_TERMS.get(task, "")
    return " ".join(part for part in (base, supplement) if part).strip() or task


def format_result_markdown(
    item: dict[str, object],
    rank: int,
    query: str,
    full_text: bool = False,
    explain: bool = False,
) -> str:
    content = str(item.get("context_text") or item["text"]) if full_text else make_snippet(str(item["text"]), query)
    course_label = " ".join(
        str(value).strip() for value in (item["course_code"], item["course_name"]) if str(value).strip()
    )
    lines = [
        f"### {rank}. {item['heading_path']}",
        f"- Score: {item['score']}",
        f"- Course: {course_label or 'Project'}",
        f"- Type: {item['doc_type']}",
        f"- Week: {item['week'] or 'N/A'}",
        f"- Source: `{item['source_path']}`",
        f"- Chunks: {', '.join(str(value) for value in item.get('context_ordinals', [item['ordinal']]))}",
    ]
    if explain:
        lines.append(f"- BM25 raw: {item.get('bm25_raw', 0.0)}")
        lines.append(f"- Term coverage: {item.get('term_coverage', 0.0)}")
        lines.append(f"- Ranking: `{json.dumps(item.get('score_components', {}), ensure_ascii=False)}`")
    lines.extend(["", "```text", content.strip(), "```"])
    return "\n".join(lines)


def print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed
