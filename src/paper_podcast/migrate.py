"""One-off move of the Obsidian `Library/` notes into Zotero."""

from pathlib import Path

import httpx

from paper_podcast import sources
from paper_podcast.frontmatter import read_library
from paper_podcast.identifiers import arxiv_id, clean_url, doi_from_url
from paper_podcast.zotero import Zotero


def note_to_item(note: dict) -> dict | None:
    """Builds the Zotero item for one note.

    Articles come straight from the frontmatter. Papers are looked up by
    DOI (from the url, or the journal DOI of an arXiv preprint), then
    arXiv ID, then CrossRef title search. The `read: false`
    flag becomes the tag `to-read`; the note's own tags are dropped.

    Args:
        note: Frontmatter dict from `read_library`.

    Returns:
        Item data ready to send to Zotero, or None if a paper can't be
        identified.
    """
    url = clean_url(note.get("url", ""))
    if note["type"] == "article":
        item = {
            "itemType": "magazineArticle",
            "title": note["title"],
            "publicationTitle": note.get("source", ""),
            "date": str(note.get("year", "")),
            "url": url,
        }
    else:
        aid = arxiv_id(url)
        doi = doi_from_url(url) or (aid and sources.published_doi(aid))
        item = sources.crossref(doi) if doi else None
        if item is None and aid:
            item = sources.arxiv(aid)
        elif item is None:
            item = sources.crossref_search(note["title"], note.get("year"))
        if item is None:
            return None
    item["tags"] = [] if note.get("read") else [{"tag": "to-read"}]
    return item


def identity(item: dict) -> set[str]:
    """Keys that say two items are the same work.

    Args:
        item: Item data (from Zotero or from `note_to_item`).

    Returns:
        The lowercase DOI, arXiv ID and url that are present.
    """
    keys = (item.get("DOI"), item.get("archiveID"), item.get("url"))
    return {k.lower() for k in keys if k}


def run(library: Path, dry_run: bool, failures_file: Path = Path("migrate-failures.txt")) -> None:
    """Migrates every note, skipping works already in Zotero.

    Args:
        library: The vault's `Library/` directory.
        dry_run: Look everything up and report, but write nothing.
        failures_file: Where to list notes that could not be identified.
    """
    zotero = None if dry_run else Zotero()
    seen: set[str] = set().union(*(identity(i["data"]) for i in zotero.items())) if zotero else set()
    items, failed = [], []
    for note in read_library(library):
        try:
            item = note_to_item(note)
        except (httpx.HTTPError, ValueError):  # a bad response fails that note, not the whole run
            item = None
        if item is None:
            failed.append(f"{note['title']}\t{note.get('url', '')}")
        elif not identity(item) & seen:
            items.append(item)
            seen |= identity(item)
    created = 0
    if zotero:
        for item, result in zip(items, zotero.write(items)):
            if "failed" in result:
                failed.append(f"{item['title']}\t{result['failed']}")
            else:
                created += 1
    failures_file.write_text("\n".join(failed) + "\n" if failed else "")
    verb = "would create" if dry_run else "created"
    print(f"{verb} {len(items) if dry_run else created}, failed {len(failed)} (see {failures_file})")
