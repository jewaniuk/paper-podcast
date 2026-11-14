"""Pulling DOIs and arXiv IDs out of URLs, and cleaning URLs."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/((?:[a-z\-]+(?:\.[A-Z]{2})?/\d{7})|(?:\d{4}\.\d{4,5}))")
DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s?#]+)")
NATURE_RE = re.compile(r"nature[.-]com.*?/articles/(s\d{5}-\d{3}-\d{5}-\w+)")
TRACKING_KEYS = {"wt.ec_id", "sap-outbound-id", "et_rid", "et_cid", "mkt-key"}


def clean_url(url: str) -> str:
    """Removes tracking parameters and un-proxies library-proxy hosts.

    Args:
        url: A url as saved in a note.

    Returns:
        The url without `utm_*` and email-alert parameters. A host like
        `www-nature-com.proxy.queensu.ca` becomes `www.nature.com`.
    """
    parts = urlsplit(url.strip())
    host = parts.netloc
    if host.endswith(".proxy.queensu.ca"):
        host = host.removesuffix(".proxy.queensu.ca").replace("-", ".")
    keep = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS
    ]
    return urlunsplit((parts.scheme, host, parts.path, urlencode(keep), ""))


def arxiv_id(url: str) -> str | None:
    """Extracts an arXiv ID, without the version suffix.

    Args:
        url: A url that may point at arXiv.

    Returns:
        e.g. `2510.09251` for `https://arxiv.org/abs/2510.09251v1`, or None.
    """
    match = ARXIV_RE.search(url)
    return match.group(1) if match else None


def doi_from_url(url: str) -> str | None:
    """Extracts a DOI from a publisher url.

    Handles urls that contain the DOI (APS, Science, Wiley, doi.org) and
    Nature research urls, whose article ID is the DOI suffix. Nature news
    (`d41586-...`) and publishers with opaque urls (Optica) return None.

    Args:
        url: A publisher url.

    Returns:
        The DOI without a trailing `.pdf`, or None.
    """
    nature = NATURE_RE.search(url)
    if nature:
        return f"10.1038/{nature.group(1)}"
    match = DOI_RE.search(url)
    return match.group(1).removesuffix(".pdf") if match else None
