import random
import sys
from datetime import date

import pytest

from paper_podcast import cli, enrich, pick, podcast
from paper_podcast.identifiers import arxiv_id, clean_url, doi_from_url


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://arxiv.org/abs/2510.09251v1", "2510.09251"),
        ("https://www.arxiv.org/pdf/2404.16106", "2404.16106"),
        ("https://arxiv.org/abs/quant-ph/0512345", "quant-ph/0512345"),
        ("https://www.nature.com/articles/s41586-024-07357-5", None),
    ],
)
def test_arxiv_id(url, expected):
    assert arxiv_id(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.nature.com/articles/s41586-024-07357-5?WT.ec_id=X", "10.1038/s41586-024-07357-5"),
        ("https://www-nature-com.proxy.queensu.ca/articles/s41567-023-02319-6", "10.1038/s41567-023-02319-6"),
        ("https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.86.5188", "10.1103/PhysRevLett.86.5188"),
        ("https://www.science.org/doi/full/10.1126/science.adh5315?utm_source=x", "10.1126/science.adh5315"),
        ("https://www.science.org/doi/pdf/10.1126/science.adh5315.pdf", "10.1126/science.adh5315"),
        ("https://onlinelibrary.wiley.com/doi/10.1002/qute.202300195", "10.1002/qute.202300195"),
        ("https://doi.org/10.1098/rsta.2023.0346", "10.1098/rsta.2023.0346"),
        ("https://opg.optica.org/ol/abstract.cfm?uri=ol-48-4-1024", None),
        ("https://www.nature.com/articles/d41586-025-04108-y", None),
    ],
)
def test_doi_from_url(url, expected):
    assert doi_from_url(url) == expected


def test_clean_url_drops_tracking_keeps_real_params():
    url = "https://opg.optica.org/prj/fulltext.cfm?uri=prj-1-3-110&id=260842&utm_source=a&WT.ec_id=b"
    assert clean_url(url) == "https://opg.optica.org/prj/fulltext.cfm?uri=prj-1-3-110&id=260842"
    assert clean_url("https://www-science-org.proxy.queensu.ca/doi/10.1126/x") == "https://www.science.org/doi/10.1126/x"


def _item(kind, title, tags=()):
    return {"key": "K", "data": {"itemType": kind, "title": title, "tags": [{"tag": t} for t in tags]}}


def test_sample_only_unread_by_kind():
    items = [_item("journalArticle", f"p{i}", ["to-read"]) for i in range(5)]
    items += [_item("magazineArticle", "a0", ["to-read"]), _item("journalArticle", "read")]
    papers, articles = (pick.sample(pool, 3, random.Random(0)) for pool in pick.split_kinds(pick.to_read(items)))
    assert len(papers) == 3 and all("to-read" in [t["tag"] for t in p["data"]["tags"]] for p in papers)
    assert [a["data"]["title"] for a in articles] == ["a0"]


def test_progress():
    items = [_item("journalArticle", "a", ["to-read"]), _item("journalArticle", "b"), _item("journalArticle", "c")]
    assert pick.progress("papers", items) == "papers    2 / 3 read (66.7%)"
    assert pick.progress("articles", []) == "articles  0 / 0 read (0.0%)"


@pytest.mark.parametrize(
    "data, expected",
    [
        ({"itemType": "journalArticle", "creators": [{"firstName": "Hao", "lastName": "Tang"}, {"lastName": "Li"}],
          "publicationTitle": "Physical Review Applied", "date": "2024-03-01"}, "Hao Tang et al. · Physical Review Applied · 2024"),
        ({"itemType": "journalArticle", "creators": [{"firstName": "Hao", "lastName": "Tang"}],
          "publicationTitle": "Optica", "date": "2023"}, "Hao Tang · Optica · 2023"),
        ({"itemType": "preprint", "creators": [{"name": "QNL Collaboration"}], "date": "2025-01"}, "QNL Collaboration · arXiv · 2025"),
        ({"itemType": "magazineArticle", "publicationTitle": "Quanta Magazine", "date": "2025"}, "Quanta Magazine · 2025"),
    ],
)
def test_byline(data, expected):
    assert pick.byline({"data": data}) == expected


def test_tag_line_group_then_three_keywords():
    tags = [{"tag": "to-read"}, {"tag": "podcasted"}] + [{"tag": f"k{i}", "type": 1} for i in range(5)]
    tags.append({"tag": "group/shastri", "type": 1})
    assert pick.tag_line({"data": {"tags": tags}}) == "group/shastri · k0, k1, k2"
    assert pick.tag_line({"data": {"tags": [{"tag": "to-read"}]}}) == ""


def test_pick_main_plain_when_piped(monkeypatch, capsys):
    item = {"key": "K", "data": {"itemType": "journalArticle", "title": "T", "DOI": "10.1/x", "date": "2024",
                                 "creators": [{"firstName": "A", "lastName": "B"}], "tags": [{"tag": "to-read"}]}}
    monkeypatch.setattr(cli, "Zotero", lambda: type("Z", (), {"items": lambda self: [item]})())
    monkeypatch.setattr(sys, "argv", ["paper-pick"])
    cli.pick_main()
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "papers  (1 of 1 to-read)\n\n  T\n  A B · arXiv · 2024\n" in out
    assert "articles  (0 of 0 to-read)" in out


def test_eligible_skips_podcasted_and_no_pdf():
    items = [_item("journalArticle", "ok", ["to-read"]), _item("journalArticle", "done", ["to-read", "podcasted"]),
             _item("journalArticle", "nopdf", ["to-read", "no-pdf"]), _item("journalArticle", "unmarked")]
    assert [i["data"]["title"] for i in podcast.eligible(items)] == ["ok"]


def test_file_name():
    item = {"data": {"title": 'A: b/c "d"', "date": "2024-05-01", "creators": [{"lastName": "Thomas"}]}}
    assert podcast.file_name(item, date(2026, 11, 14)) == "2026-11-14 Thomas 2024 - A bc d.mp3"
    article = {"data": {"title": "News", "date": "2025", "publicationTitle": "Nature"}}
    assert podcast.file_name(article, date(2026, 11, 14)) == "2026-11-14 Nature 2025 - News.mp3"


def test_pause_and_resume(tmp_path):
    assert not podcast.is_paused(tmp_path)
    podcast.set_paused(True, tmp_path)
    assert podcast.is_paused(tmp_path)
    podcast.set_paused(False, tmp_path)
    assert not podcast.is_paused(tmp_path)


def test_run_does_nothing_when_paused(tmp_path, capsys):
    podcast.set_paused(True, tmp_path)
    podcast.run(tmp_path)
    assert "paused" in capsys.readouterr().out


def test_upgrade_preprint_swaps_in_journal_version(monkeypatch):
    journal = {"itemType": "journalArticle", "title": "T", "DOI": "10.1/x", "creators": []}
    monkeypatch.setattr(podcast.sources, "published_doi", lambda aid: "10.1/x")
    monkeypatch.setattr(podcast.sources, "crossref", lambda doi: dict(journal))

    class FakeZotero:
        def write(self, items):
            self.sent = items
            return [{"key": "K", "version": 9, "data": items[0]}]

    item = {"key": "K", "version": 3, "data": {"itemType": "preprint", "url": "https://arxiv.org/abs/2510.09251",
                                               "tags": [{"tag": "to-read"}]}}
    zotero = FakeZotero()
    new = podcast.upgrade_preprint(zotero, item)
    assert zotero.sent[0]["itemType"] == "journalArticle" and zotero.sent[0]["tags"] == [{"tag": "to-read"}]
    assert new["version"] == 9


def test_upgrade_preprint_leaves_unpublished_alone(monkeypatch):
    monkeypatch.setattr(podcast.sources, "published_doi", lambda aid: None)
    item = {"key": "K", "version": 3, "data": {"itemType": "preprint", "url": "https://arxiv.org/abs/2510.09251"}}
    assert podcast.upgrade_preprint(None, item) is item


def test_with_retry_retries_server_errors_then_gives_up(monkeypatch):
    sleeps = []
    monkeypatch.setattr(podcast.time, "sleep", sleeps.append)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise podcast.errors.ServerError(503, {"error": {"message": "high demand"}})
        return "ok"

    assert podcast.with_retry(flaky, waits=(1, 2, 3)) == "ok"
    assert sleeps == [1, 2]

    def always():
        raise podcast.errors.ServerError(503, {"error": {"message": "high demand"}})

    with pytest.raises(podcast.errors.ServerError):
        podcast.with_retry(always, waits=(1, 2))


def _tagged(key, *tags, item_type="journalArticle"):
    return {"key": key, "version": 1, "data": {"itemType": item_type, "tags": [{"tag": t} for t in tags]}}


def test_status_tags_only_for_items_with_neither():
    assert enrich.status_tags(set(), "journalArticle") == ["to-read"]
    assert enrich.status_tags({"to-read"}, "journalArticle") == []
    assert enrich.status_tags({"read"}, "journalArticle") == []
    assert enrich.status_tags(set(), "note") == []


class _FakeZotero:
    def __init__(self, items):
        self._items, self.written = items, []

    def items(self):
        return self._items

    def write(self, items):
        self.written += items


def test_backfill_read_dry_run_changes_nothing(capsys):
    zotero = _FakeZotero([_tagged("A"), _tagged("B", "to-read"), _tagged("C", "read"), _tagged("D", item_type="note")])
    assert enrich.backfill_read(zotero) == 1
    assert zotero.written == []
    assert "would tag 1 items" in capsys.readouterr().out


def test_backfill_read_apply_tags_only_the_untagged():
    zotero = _FakeZotero([_tagged("A", "keyword"), _tagged("B", "to-read"), _tagged("C", "read")])
    enrich.backfill_read(zotero, apply=True)
    assert [u["key"] for u in zotero.written] == ["A"]
    assert zotero.written[0]["tags"] == [{"tag": "keyword"}, {"tag": "read"}]


def test_run_uses_given_pdf_instead_of_source_chain(monkeypatch, tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"pdf bytes")
    item = {"key": "K", "version": 1, "data": {"itemType": "journalArticle", "title": "T", "tags": []}}
    zotero = type("Z", (), {"items": lambda self: [item], "add_tags": lambda self, i, t: None})()
    seen = {}
    monkeypatch.setattr(podcast, "Zotero", lambda: zotero)
    monkeypatch.setattr(podcast, "upgrade_preprint", lambda z, i: i)
    monkeypatch.setattr(podcast, "pdf_text", lambda b: seen.setdefault("pdf", b) and "text")
    monkeypatch.setattr(podcast, "get_text", lambda d: pytest.fail("source chain used"))
    monkeypatch.setattr(podcast, "env", lambda name: "x")
    monkeypatch.setattr(podcast.genai, "Client", lambda **k: None)
    monkeypatch.setattr(podcast, "SCRIPTS_DIR", tmp_path / "scripts")
    monkeypatch.setattr(podcast, "write_script", lambda c, d, t: "Alex: hi")
    monkeypatch.setattr(podcast, "synthesize", lambda c, s: b"mp3")
    monkeypatch.setattr(podcast, "tag_mp3", lambda p, i: None)
    podcast.run(tmp_path / "out", only_key="K", pdf=pdf)
    assert seen["pdf"] == b"pdf bytes"
    assert len(list((tmp_path / "out").glob("*.mp3"))) == 1
