"""Nightly enrichment: OpenAlex keywords, the research group and `to-read` as automatic tags."""

import json

from paper_podcast import sources
from paper_podcast.config import STATE_FILE
from paper_podcast.zotero import Zotero


NOT_READING = {"note", "attachment"}  # standalone items that aren't something to read


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


def status_tags(have: set[str], item_type: str) -> list[str]:
    """Works out the read-status tag a new item needs.

    Args:
        have: Tag names the item already carries.
        item_type: The item's Zotero type; notes and attachments aren't reading.

    Returns:
        `["to-read"]` if the item has neither `to-read` nor `read`, else an empty list.
    """
    if item_type in NOT_READING or have & {"to-read", "read"}:
        return []
    return ["to-read"]


def backfill_read(zotero: Zotero, apply: bool = False) -> int:
    """Tags `read` on every item lacking `to-read` (and not already `read`).

    One-time fix for the migration, which turned `read: false` into `to-read`
    and left read items untagged.

    Args:
        zotero: Zotero client.
        apply: True to write the tags; False for a dry run that changes nothing.

    Returns:
        How many items needed (or, when applied, got) the tag.
    """
    updates = []
    for item in zotero.items():
        data = item["data"]
        have = {t["tag"] for t in data.get("tags", [])}
        if data["itemType"] not in NOT_READING and not have & {"to-read", "read"}:
            tags = data.get("tags", []) + [{"tag": "read"}]
            updates.append({"key": item["key"], "version": item["version"], "tags": tags})
    if apply:
        zotero.write(updates)
    print(f"{'tagged' if apply else 'would tag'} {len(updates)} items `read`")
    return len(updates)


def run() -> None:
    """Tags every item changed since the last run, then saves the library version.

    Items with neither `to-read` nor `read` also get `to-read`.

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
        new = [t for t in tags_for(item) + status_tags(have, item["data"]["itemType"]) if t not in have]
        if new:
            tags = item["data"].get("tags", []) + [{"tag": t, "type": 1} for t in new]
            updates.append({"key": item["key"], "version": item["version"], "tags": tags})
    zotero.write(updates)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"library_version": seen_version}))
    print(f"enriched {len(updates)} of {len(items)} changed items")
