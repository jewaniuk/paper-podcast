"""Metadata and full-text lookups on CrossRef, arXiv, OpenAlex, Unpaywall and publishers."""

import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import httpx

HTTP = httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "paper-podcast/0.1"})
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _creators(names: list[tuple[str, str]]) -> list[dict]:
    return [
        {"creatorType": "author", "firstName": first, "lastName": last} for first, last in names
    ]


def crossref(doi: str) -> dict | None:
    """Fetches a journal article's metadata as Zotero item data.

    Args:
        doi: The article's DOI.

    Returns:
        A `journalArticle` item dict, or None if CrossRef doesn't know the DOI.
    """
    response = HTTP.get(f"https://api.crossref.org/works/{doi}")
    if response.status_code != 200:
        return None
    return _crossref_item(response.json()["message"])


def _crossref_item(work: dict) -> dict:
    parts = (work.get("issued", {}).get("date-parts") or [[None]])[0]
    return {
        "itemType": "journalArticle",
        "title": (work.get("title") or [""])[0],
        "creators": _creators([(a.get("given", ""), a.get("family", "")) for a in work.get("author", [])]),
        "publicationTitle": (work.get("container-title") or [""])[0],
        "date": "-".join(str(p) for p in parts if p),
        "DOI": work["DOI"],
        "url": work.get("URL", ""),
    }


def crossref_search(title: str, year: int | None) -> dict | None:
    """Finds an article by title when its url holds no DOI (e.g. Optica).

    Args:
        title: The note's title.
        year: Publication year, used to reject near-miss titles.

    Returns:
        A `journalArticle` item dict if the best hit's title matches
        exactly (ignoring case and punctuation), otherwise None.
    """
    response = HTTP.get(
        "https://api.crossref.org/works", params={"query.bibliographic": title, "rows": 3}
    )
    if response.status_code != 200:
        return None
    norm = lambda s: re.sub(r"\W+", "", s).lower()
    for work in response.json()["message"]["items"]:
        if norm((work.get("title") or [""])[0]) == norm(title):
            return _crossref_item(work)
    return None


def arxiv(arxiv_id: str) -> dict | None:
    """Fetches a preprint's metadata as Zotero item data.

    Args:
        arxiv_id: ID without version, e.g. `2510.09251`.

    Returns:
        A `preprint` item dict, or None if the ID isn't found.
    """
    for attempt in range(4):  # arxiv rate-limits with empty or 429 replies; wait and retry
        time.sleep(3 + 5 * attempt)
        response = HTTP.get("https://export.arxiv.org/api/query", params={"id_list": arxiv_id})
        if response.status_code == 200 and response.text.strip():
            break
    else:
        return None
    root = ET.fromstring(response.text)
    entry = root.find("a:entry", ATOM)
    if entry is None or entry.find("a:title", ATOM) is None or entry.find("a:author", ATOM) is None:
        return None
    names = []
    for author in entry.findall("a:author/a:name", ATOM):
        first, _, last = author.text.strip().rpartition(" ")
        names.append((first, last))
    return {
        "itemType": "preprint",
        "title": " ".join(entry.find("a:title", ATOM).text.split()),
        "creators": _creators(names),
        "date": entry.find("a:published", ATOM).text[:10],
        "repository": "arXiv",
        "archiveID": f"arXiv:{arxiv_id}",
        "url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def openalex_work(doi: str) -> dict | None:
    """Fetches the raw OpenAlex record for a DOI.

    Args:
        doi: A DOI (arXiv preprints use `10.48550/arXiv.<id>`).

    Returns:
        The record, or None if OpenAlex does not know the DOI.
    """
    response = HTTP.get(f"https://api.openalex.org/works/doi:{doi}")
    return response.json() if response.status_code == 200 else None


def openalex(doi: str) -> dict | None:
    """Fetches keywords and the last author for enrichment.

    Args:
        doi: A DOI (arXiv preprints use `10.48550/arXiv.<id>`).

    Returns:
        `{"keywords": [...], "last_author": "<surname>"}` or None if unknown.
    """
    work = openalex_work(doi)
    if work is None:
        return None
    authors = work.get("authorships") or []
    surname = authors[-1]["author"]["display_name"].split()[-1] if authors else ""
    return {"keywords": [k["display_name"] for k in work.get("keywords", [])], "last_author": surname}


def _is_pdf(response: httpx.Response) -> bool:
    return response.status_code == 200 and response.content[:5] == b"%PDF-"


def publisher_pdf(doi: str) -> bytes | None:
    """Gets the PDF from the publisher through the DOI landing page.

    Works only from a network with a subscription (Queen's WiFi): reads the
    page's `citation_pdf_url` meta tag, which publishers set for indexers.

    Args:
        doi: The article's DOI.

    Returns:
        PDF bytes, or None if the page has no such tag or access is denied.
    """
    page = HTTP.get(f"https://doi.org/{doi}")
    match = re.search(r'<meta[^>]+name="citation_pdf_url"[^>]+content="([^"]+)"', page.text)
    if not match:
        return None
    response = HTTP.get(match.group(1), headers={"Referer": str(page.url)})
    return response.content if _is_pdf(response) else None


def arxiv_pdf(arxiv_id: str) -> bytes | None:
    """Downloads a PDF from arXiv.

    Args:
        arxiv_id: ID without version.

    Returns:
        PDF bytes, or None.
    """
    response = HTTP.get(f"https://arxiv.org/pdf/{arxiv_id}")
    return response.content if _is_pdf(response) else None


def unpaywall_pdf(doi: str, email: str) -> bytes | None:
    """Downloads the open-access copy Unpaywall knows of.

    Args:
        doi: The article's DOI.
        email: Contact address Unpaywall requires on every request.

    Returns:
        PDF bytes, or None.
    """
    info = HTTP.get(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})
    if info.status_code != 200:
        return None
    location = info.json().get("best_oa_location") or {}
    if not location.get("url_for_pdf"):
        return None
    response = HTTP.get(location["url_for_pdf"])
    return response.content if _is_pdf(response) else None


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._skip += tag in self.SKIP

    def handle_endtag(self, tag: str) -> None:
        self._skip -= tag in self.SKIP and self._skip > 0

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def page_text(url: str) -> str:
    """Fetches a web page and returns its visible text.

    Args:
        url: An article url.

    Returns:
        Text with scripts, navigation and footers removed.
    """
    extractor = _TextExtractor()
    extractor.feed(HTTP.get(url).text)
    return "\n".join(extractor.parts)


def published_doi(arxiv_id: str) -> str | None:
    """Finds the journal DOI of a preprint, if it has been published.

    OpenAlex merges a preprint and its published version into one work,
    and that work's `doi` is the journal one once it exists.

    Args:
        arxiv_id: ID without version.

    Returns:
        The journal DOI, or None if the paper is still preprint-only.
    """
    work = openalex_work(f"10.48550/arXiv.{arxiv_id}")
    doi = ((work or {}).get("doi") or "").removeprefix("https://doi.org/")
    return doi if doi and "arxiv" not in doi.lower() else None
