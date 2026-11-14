import random
from datetime import date

import pytest

from paper_podcast import podcast
from paper_podcast.frontmatter import parse_note, read_library
from paper_podcast.identifiers import arxiv_id, clean_url, doi_from_url
from paper_podcast.migrate import note_to_item
from paper_podcast.pick import sample


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


def test_parse_note(tmp_path):
    (tmp_path / "A title.md").write_text("---\ntype: paper\nread: false\nyear: 2024\n---\nbody")
    (tmp_path / "Library.md").write_text("---\ntype: navigator\n---\n")
    (tmp_path / "plain.md").write_text("no frontmatter")
    assert parse_note(tmp_path / "A title.md") == {"type": "paper", "read": False, "year": 2024, "title": "A title"}
    assert parse_note(tmp_path / "plain.md") is None
    assert [n["title"] for n in read_library(tmp_path)] == ["A title"]


def test_article_item_from_note():
    note = {"type": "article", "title": "t", "source": "Nature", "year": 2024, "read": False,
            "url": "https://www.nature.com/articles/d41586-1?utm_source=a", "tags": ["article/x"]}
    item = note_to_item(note)
    assert item["itemType"] == "magazineArticle"
    assert item["url"] == "https://www.nature.com/articles/d41586-1"
    assert item["tags"] == [{"tag": "to-read"}]
    assert note_to_item({**note, "read": True})["tags"] == []


def _item(kind, title, tags=()):
    return {"key": "K", "data": {"itemType": kind, "title": title, "tags": [{"tag": t} for t in tags]}}


def test_sample_only_unread_by_kind():
    items = [_item("journalArticle", f"p{i}", ["to-read"]) for i in range(5)]
    items += [_item("magazineArticle", "a0", ["to-read"]), _item("journalArticle", "read")]
    papers, articles = sample(items, 3, random.Random(0))
    assert len(papers) == 3 and all("to-read" in [t["tag"] for t in p["data"]["tags"]] for p in papers)
    assert [a["data"]["title"] for a in articles] == ["a0"]


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
