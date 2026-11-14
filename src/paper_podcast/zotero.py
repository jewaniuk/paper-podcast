"""A small client for the Zotero Web API (https://www.zotero.org/support/dev/web_api/v3/start)."""

import httpx

from paper_podcast.config import env

API = "https://api.zotero.org"
BATCH = 50  # most items the API accepts in one write


class Zotero:
    """Reads and writes the user's Zotero library.

    Attributes:
        version: Library version after the most recent response; it grows
            with every change, so it marks "everything up to here is seen".
    """

    def __init__(self) -> None:
        self._base = f"/users/{env('ZOTERO_USER_ID')}"
        self._http = httpx.Client(
            base_url=API,
            headers={"Zotero-API-Key": env("ZOTERO_API_KEY"), "Zotero-API-Version": "3"},
            timeout=60,
        )
        self.version = 0

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = self._http.request(method, self._base + path, **kwargs)
        response.raise_for_status()
        self.version = int(response.headers.get("Last-Modified-Version", self.version))
        return response

    def items(self, since: int = 0) -> list[dict]:
        """Lists top-level items, optionally only those changed after a version.

        Args:
            since: Library version from a previous run, or 0 for everything.

        Returns:
            Item dicts with their `key`, `version` and `data`.
        """
        found: list[dict] = []
        start = 0
        while True:
            page = self._request(
                "GET", "/items/top", params={"since": since, "limit": 100, "start": start}
            ).json()
            found += page
            if len(page) < 100:
                return found
            start += 100

    def write(self, items: list[dict]) -> list[dict]:
        """Creates items (no `key`) or updates them (with `key` and `version`).

        Args:
            items: Item data dicts, any number; sent in batches of 50.

        Returns:
            One dict per input item holding either the saved `data` or a
            `failed` message, in input order.
        """
        results: list[dict] = []
        for i in range(0, len(items), BATCH):
            chunk = items[i : i + BATCH]
            body = self._request("POST", "/items", json=chunk).json()
            for n in range(len(chunk)):
                if str(n) in body["successful"]:
                    results.append(body["successful"][str(n)])
                elif str(n) in body.get("unchanged", {}):
                    results.append(chunk[n])
                else:
                    results.append({"failed": body["failed"][str(n)]["message"]})
        return results

    def add_tags(self, item: dict, tags: list[str]) -> None:
        """Adds manual tags to one existing item, keeping its other tags.

        Args:
            item: An item dict as returned by `items`.
            tags: Tag names to add.
        """
        data = item["data"]
        have = {t["tag"] for t in data.get("tags", [])}
        new = [{"tag": t} for t in tags if t not in have]
        if new:
            self.write([{"key": item["key"], "version": item["version"], "tags": data.get("tags", []) + new}])
