#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree


def natural_number(path: str) -> int:
    match = re.search(r"(\d+)", Path(path).stem)
    return int(match.group(1)) if match else 0


def xml_text(data: bytes, paragraph_tag: str | None = None) -> list[str]:
    root = ElementTree.fromstring(data)
    if paragraph_tag:
        values = []
        for paragraph in root.findall(f".//{{*}}{paragraph_tag}"):
            text = "".join(node.text or "" for node in paragraph.findall(".//{*}t")).strip()
            if text:
                values.append(text)
        return values
    return [node.text.strip() for node in root.findall(".//{*}t") if node.text and node.text.strip()]


def extract_pptx(path: Path) -> list[tuple[str, str]]:
    sections = []
    with zipfile.ZipFile(path) as archive:
        slides = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=natural_number,
        )
        for index, name in enumerate(slides, start=1):
            sections.append((f"Slide {index}", "\n".join(xml_text(archive.read(name)))))
    return sections


def extract_docx(path: Path) -> list[tuple[str, str]]:
    with zipfile.ZipFile(path) as archive:
        if "word/document.xml" not in archive.namelist():
            raise ValueError("DOCX has no word/document.xml")
        paragraphs = xml_text(archive.read("word/document.xml"), paragraph_tag="p")
    return [("Document", "\n\n".join(paragraphs))]


def extract_pdf(path: Path) -> list[tuple[str, str]]:
    command = shutil.which("pdftotext")
    if command:
        completed = subprocess.run([command, "-layout", str(path), "-"], check=False, capture_output=True)
        if completed.returncode == 0:
            text = completed.stdout.decode("utf-8", errors="replace")
            return [(f"Page {index}", value.strip()) for index, value in enumerate(text.split("\f"), start=1) if value.strip()]
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Offline PDF extraction needs pdftotext or pypdf; neither is available.") from exc
    reader = PdfReader(str(path))
    return [(f"Page {index}", page.extract_text() or "") for index, page in enumerate(reader.pages, start=1)]


def extract(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.casefold()
    if suffix == ".pptx":
        return extract_pptx(path)
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in {".md", ".txt"}:
        return [("Document", path.read_text(encoding="utf-8", errors="replace"))]
    raise ValueError(f"Unsupported offline extraction format: {suffix or '[none]'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract local source text to Markdown without network access.")
    parser.add_argument("source")
    parser.add_argument("--vault", default=".")
    parser.add_argument("--output-dir", help="Defaults to <vault>/.course-study/extracted.")
    args = parser.parse_args()
    root = Path(args.vault).expanduser().resolve()
    source = Path(args.source).expanduser()
    source = source.resolve() if source.is_absolute() else (root / source).resolve()
    try:
        relative = source.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Source must stay inside the course project") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else root / ".course-study" / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._\-\u3400-\u9fff]+", "_", source.stem).strip("_") or "source"
    output = output_dir / f"{safe_name}_{source.suffix.lstrip('.').lower()}.md"
    sections = extract(source)
    lines = [
        f"# Extracted Source - {source.name}",
        "",
        f"- Original source: `{relative}`",
        f"- Format: `{source.suffix.lower()}`",
        "- Generated locally for retrieval; verify diagrams, formulas, scans, and layout against the original.",
        "",
    ]
    for title, text in sections:
        lines.extend([f"## {title}", "", text.strip() or "[No extractable text]", ""])
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Extracted source text: {output}")
    print(f"- Sections: {len(sections)}")
    print("- Enable rag.include_extracted in course-study.json before rebuilding the index.")


if __name__ == "__main__":
    main()
