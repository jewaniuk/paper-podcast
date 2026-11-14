"""Nightly enrichment: OpenAlex keywords and the research group as automatic tags."""

import json

from paper_podcast import sources
from paper_podcast.config import STATE_FILE
from paper_podcast.zotero import Zotero


def tags_for(item: dict) -> list[str]:
    """Works out the automatic tags an item should get.

    Args:
        item: A Zotero item dict.

    Returns:
        OpenAlex keywords plus `group/<last-author surname>`, or an empty
        list for magazine articles and items with no DOI or arXiv ID.
    """
    data = item["data"]
    if data["itemType"] == "magazineArticle":
        return []
    doi = data.get("DOI") or (
        f"10.48550/arXiv.{data['archiveID'].removeprefix('arXiv:')}" if data.get("archiveID") else ""
    )
    info = sources.openalex(doi) if doi else None
    if info is None:
        return []
    tags = list(info["keywords"])
    if info["last_author"]:
        tags.append(f"group/{info['last_author']}")
    return tags


def run() -> None:
    """Tags every item changed since the last run, then saves the library version.

    The saved version is the one seen when the items were read, so the
    tag writes made here show up again next run; items that already hold
    every tag are skipped, so that second look writes nothing.
    """
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    zotero = Zotero()
    items = zotero.items(since=state.get("library_version", 0))
    seen_version = zotero.version
    updates = []
    for item in items:
        have = {t["tag"] for t in item["data"].get("tags", [])}
        new = [t for t in tags_for(item) if t not in have]
        if new:
            tags = item["data"].get("tags", []) + [{"tag": t, "type": 1} for t in new]
            updates.append({"key": item["key"], "version": item["version"], "tags": tags})
    zotero.write(updates)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"library_version": seen_version}))
    print(f"enriched {len(updates)} of {len(items)} changed items")
