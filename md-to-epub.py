#!/usr/bin/env python3
"""
md_to_epub.py — Convert a folder of .md files into an .epub file

Usage:
    python md_to_epub.py <folder> [options]

Options:
    --output, -o   Output file path     (default: folder name + .epub)
    --title,  -t   Book title           (default: folder name)
    --author, -a   Author name          (default: "Unknown Author")
    --cover,  -c   Cover image (png/jpg), overrides auto-detection

Dependencies:
    pip install markdown ebooklib
"""

import argparse
import re
import uuid
from pathlib import Path

import markdown
from ebooklib import epub


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "chapter"


def md_to_html(text: str) -> str:
    """Convert Markdown to HTML (common extensions enabled)."""
    return markdown.markdown(
        text,
        extensions=["extra", "smarty", "nl2br"],
    )


def first_heading(md_text: str) -> str | None:
    """Return the text of the first ## heading in the file, or None.
    # is skipped — it typically mirrors the book title and is redundant in the TOC.
    """
    for line in md_text.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            return m.group(1).strip()
    return None


def chapter_sort_key(path: Path):
    """
    Natural sort for .md files:
    01-intro.md, 02-..., chapter-3.md, etc.
    Numbers are extracted for correct numeric ordering.
    """
    parts = re.split(r"(\d+)", path.stem)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


# ── Core ─────────────────────────────────────────────────────────────────────

def find_cover(folder: Path) -> Path | None:
    """Return cover.png or cover.jpg if present, otherwise None."""
    for name in ("cover.png", "cover.jpg", "cover.jpeg"):
        p = folder / name
        if p.exists():
            return p
    return None


def build_epub(folder: Path, output: Path, title: str, author: str, cover_override: Path | None = None) -> None:
    md_files = sorted(folder.glob("*.md"), key=chapter_sort_key)
    if not md_files:
        raise FileNotFoundError(f"No .md files found in: {folder}")

    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    # Cover
    cover_path = cover_override or find_cover(folder)
    if cover_path:
        media_type = "image/jpeg" if cover_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        book.set_cover(cover_path.name, cover_path.read_bytes(), create_page=True)
        print(f"  [cover] {cover_path.name}  ({media_type})")
    else:
        print("  [cover] none (no cover.png/jpg found)")

    # Minimal CSS
    css = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=b"""
body { font-family: Georgia, serif; line-height: 1.6; margin: 2em; }
h1, h2, h3 { font-family: sans-serif; }
h1 { font-size: 1.8em; margin-top: 2em; }
code, pre { font-family: monospace; background: #f4f4f4; padding: 0.2em 0.4em; }
pre { padding: 1em; overflow-x: auto; }
blockquote { border-left: 3px solid #ccc; margin-left: 0; padding-left: 1em; color: #555; }
""",
    )
    book.add_item(css)

    chapters: list[epub.EpubHtml] = []
    toc: list[epub.Link] = []

    for i, md_path in enumerate(md_files, start=1):
        md_text = md_path.read_text(encoding="utf-8")
        html_body = md_to_html(md_text)

        chapter_title = first_heading(md_text) or md_path.stem
        file_name = f"chapter_{i:03d}_{slugify(md_path.stem)}.xhtml"

        chapter = epub.EpubHtml(
            title=chapter_title,
            file_name=file_name,
            lang="en",
        )
        chapter.content = (
            f'<?xml version="1.0" encoding="utf-8"?>'
            f"<!DOCTYPE html>"
            f'<html xmlns="http://www.w3.org/1999/xhtml">'
            f"<head>"
            f'<meta charset="utf-8"/>'
            f"<title>{chapter_title}</title>"
            f'<link rel="stylesheet" type="text/css" href="style/main.css"/>'
            f"</head>"
            f"<body>{html_body}</body>"
            f"</html>"
        ).encode("utf-8")
        chapter.add_item(css)

        book.add_item(chapter)
        chapters.append(chapter)
        toc.append(epub.Link(file_name, chapter_title, slugify(chapter_title)))
        print(f"  [{i:>3}] {md_path.name}  →  {chapter_title}")

    book.toc = toc
    book.spine = (["cover"] if cover_path else []) + ["nav"] + chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(output), book)
    print(f"\n✓ EPUB written: {output}  ({len(chapters)} chapter(s))")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a folder of .md files into an .epub file"
    )
    parser.add_argument("folder", help="Folder containing the .md files")
    parser.add_argument("-o", "--output", help="Output .epub file path")
    parser.add_argument("-t", "--title",  help="Book title")
    parser.add_argument("-a", "--author", default="Unknown Author", help="Author name")
    parser.add_argument("-c", "--cover",  help="Cover image (png/jpg), overrides auto-detection")
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        parser.error(f"Folder not found: {folder}")

    cover_override = None
    if args.cover:
        cover_override = Path(args.cover).resolve()
        if not cover_override.is_file():
            parser.error(f"Cover image not found: {cover_override}")

    title  = args.title  or folder.name
    output = Path(args.output) if args.output else folder.parent / f"{folder.name}.epub"

    print(f"Title   : {title}")
    print(f"Author  : {args.author}")
    print(f"Source  : {folder}")
    print(f"Output  : {output}\n")

    build_epub(folder, output, title, args.author, cover_override)


if __name__ == "__main__":
    main()
