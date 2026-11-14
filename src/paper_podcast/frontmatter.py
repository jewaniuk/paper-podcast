"""Reading the yaml frontmatter of the Obsidian `Library/` notes."""

from pathlib import Path

import yaml


def parse_note(path: Path) -> dict | None:
    """Reads the frontmatter of one note.

    Args:
        path: Markdown file with a `---` delimited yaml header.

    Returns:
        The frontmatter as a dict plus the note's `title` (the file name
        without `.md`), or None if the note has no frontmatter.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    header = text[4:].split("\n---", 1)[0]
    data = yaml.safe_load(header) or {}
    data["title"] = path.stem
    return data


def read_library(directory: Path) -> list[dict]:
    """Reads every paper and article note in the library directory.

    Args:
        directory: The vault's `Library/` directory.

    Returns:
        Frontmatter dicts for notes whose `type` is `paper` or `article`
        (the `Library.md` navigator note is skipped).
    """
    notes = [parse_note(p) for p in sorted(directory.glob("*.md"))]
    return [n for n in notes if n and n.get("type") in ("paper", "article")]
