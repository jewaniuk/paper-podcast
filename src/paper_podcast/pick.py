"""Random picks from the `to-read` list."""

import random


def to_read(items: list[dict]) -> list[dict]:
    """Filters to items tagged `to-read`.

    Args:
        items: Zotero item dicts.

    Returns:
        The items carrying that tag.
    """
    return [i for i in items if any(t["tag"] == "to-read" for t in i["data"].get("tags", []))]


def sample(items: list[dict], n: int, rng: random.Random | None = None) -> tuple[list[dict], list[dict]]:
    """Picks up to n unread papers and n unread articles.

    Args:
        items: Zotero item dicts.
        n: How many of each kind.
        rng: Random source, for repeatable tests.

    Returns:
        `(papers, articles)`; a list is shorter than n if there aren't enough.
    """
    rng = rng or random.Random()
    unread = to_read(items)
    articles = [i for i in unread if i["data"]["itemType"] == "magazineArticle"]
    papers = [i for i in unread if i["data"]["itemType"] != "magazineArticle"]
    return rng.sample(papers, min(n, len(papers))), rng.sample(articles, min(n, len(articles)))


def link(item: dict) -> str:
    """The url to open an item from.

    Args:
        item: A Zotero item dict.

    Returns:
        The DOI link if there is a DOI, else the stored url.
    """
    data = item["data"]
    return f"https://doi.org/{data['DOI']}" if data.get("DOI") else data.get("url", "")
