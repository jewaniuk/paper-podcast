"""Random picks from the `to-read` list, and how they are shown."""

import random


def to_read(items: list[dict]) -> list[dict]:
    """Filters to items tagged `to-read`.

    Args:
        items: Zotero item dicts.

    Returns:
        The items carrying that tag.
    """
    return [i for i in items if any(t["tag"] == "to-read" for t in i["data"].get("tags", []))]


def split_kinds(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Splits items into papers and articles.

    Args:
        items: Zotero item dicts.

    Returns:
        `(papers, articles)`; articles are the magazine articles, papers everything else.
    """
    articles = [i for i in items if i["data"]["itemType"] == "magazineArticle"]
    papers = [i for i in items if i["data"]["itemType"] != "magazineArticle"]
    return papers, articles


def sample(pool: list[dict], n: int, rng: random.Random | None = None) -> list[dict]:
    """Picks up to n items at random.

    Args:
        pool: Zotero item dicts to pick from.
        n: How many to pick.
        rng: Random source, for repeatable tests.

    Returns:
        The picked items; fewer than n if the pool is smaller.
    """
    return (rng or random.Random()).sample(pool, min(n, len(pool)))


def progress(heading: str, items: list[dict]) -> str:
    """Counts how many items are read, with the share as a percentage.

    Args:
        heading: The kind of item, printed first (e.g. `papers`).
        items: Zotero item dicts of that kind.

    Returns:
        A line such as `papers    108 / 520 read (20.8%)`; read means not tagged `to-read`.
    """
    read = len(items) - len(to_read(items))
    share = 100 * read / len(items) if items else 0.0
    return f"{heading:<10}{read} / {len(items)} read ({share:.1f}%)"


def link(item: dict) -> str:
    """The url to open an item from.

    Args:
        item: A Zotero item dict.

    Returns:
        The DOI link if there is a DOI, else the stored url.
    """
    data = item["data"]
    return f"https://doi.org/{data['DOI']}" if data.get("DOI") else data.get("url", "")


def byline(item: dict) -> str:
    """Builds the `author · journal · year` line shown under a title.

    Args:
        item: A Zotero item dict.

    Returns:
        The first author's full name (plus `et al.` if there are more), the
        journal (`arXiv` for a paper without one) and the year, joined by
        ` · `; missing parts are left out, so articles usually show only
        their publication and year.
    """
    data = item["data"]
    creators = data.get("creators") or []
    author = ""
    if creators:
        first = creators[0]
        author = first.get("name") or f"{first.get('firstName', '')} {first.get('lastName', '')}".strip()
        author += " et al." if len(creators) > 1 else ""
    journal = data.get("publicationTitle") or ("arXiv" if data["itemType"] != "magazineArticle" else "")
    return " · ".join(p for p in [author, journal, (data.get("date") or "")[:4]] if p)


def tag_line(item: dict) -> str:
    """Builds the tags line shown under the byline.

    Args:
        item: A Zotero item dict.

    Returns:
        The `group/<surname>` tag, then the first 3 OpenAlex keywords (the
        other automatic tags), joined by ` · `; empty if there are neither.
    """
    tags = item["data"].get("tags", [])
    group = [t["tag"] for t in tags if t["tag"].startswith("group/")]
    keywords = [t["tag"] for t in tags if t.get("type") == 1 and not t["tag"].startswith("group/")][:3]
    return " · ".join(p for p in [", ".join(group), ", ".join(keywords)] if p)
