"""Making one podcast episode: pick, fetch text, write the script, voice it, save, tag."""

import base64
import io
import random
import re
from datetime import date
from pathlib import Path

import lameenc
from pypdf import PdfReader
from google import genai
from mutagen.id3 import COMM, ID3, TIT2, TPE1, WOAF

from paper_podcast import sources
from paper_podcast.config import GEMINI_TEXT_MODEL, GEMINI_TTS_MODEL, PODCASTS_DIR, env
from paper_podcast.identifiers import arxiv_id
from paper_podcast.pick import to_read
from paper_podcast.zotero import Zotero

HOSTS = {"Alex": "Kore", "Sam": "Puck"}  # speaker name -> Gemini voice
SAMPLE_RATE = 24000  # Gemini tts output: 16-bit mono pcm at 24 kHz
TTS_CHUNK_CHARS = 3500  # tts requests are limited in length, so the script is voiced in pieces
SCRIPTS_DIR = Path(__file__).parents[2] / "scripts"  # generated scripts, never committed
PROMPT_FILE = Path(__file__).parents[2] / "prompts" / "podcast.md"  # edit this file to change the episode style


def is_paused(directory: Path = PODCASTS_DIR) -> bool:
    """Checks for the `paused` directory that stops new episodes.

    Args:
        directory: The iCloud `Podcasts/` directory.

    Returns:
        True if `paused` exists inside it.
    """
    return (directory / "paused").is_dir()


def set_paused(paused: bool, directory: Path = PODCASTS_DIR) -> None:
    """Creates or removes the `paused` directory.

    Args:
        paused: True to pause, False to resume.
        directory: The iCloud `Podcasts/` directory.
    """
    flag = directory / "paused"
    if paused:
        flag.mkdir(parents=True, exist_ok=True)
    elif flag.is_dir():
        flag.rmdir()


def eligible(items: list[dict]) -> list[dict]:
    """Unread items that haven't been podcasted or marked as lacking a PDF.

    Args:
        items: Zotero item dicts.

    Returns:
        The items that may still be picked.
    """
    skip = {"podcasted", "no-pdf"}
    return [i for i in to_read(items) if not skip & {t["tag"] for t in i["data"].get("tags", [])}]


def file_name(item: dict, today: date) -> str:
    """Builds `<YYYY-MM-DD> <first author> <year> - <title>.mp3`.

    Args:
        item: A Zotero item dict.
        today: The episode date.

    Returns:
        A file name safe on iCloud and macOS (no slashes or colons);
        articles have no first author, so their publication stands in.
    """
    data = item["data"]
    creators = data.get("creators") or []
    who = creators[0].get("lastName", "") if creators else data.get("publicationTitle", "")
    year = (data.get("date") or "")[:4]
    title = re.sub(r'[\\/:*?"<>|]', "", data["title"]).strip()[:120]
    return f"{today:%Y-%m-%d} {who} {year} - {title}.mp3"


def get_text(data: dict) -> str | None:
    """Gets the source text: the PDF for papers, the web page for articles.

    PDF order is publisher, arXiv, Unpaywall.

    Args:
        data: The `data` dict of a Zotero item.

    Returns:
        Text, or None if no PDF could be had (or the page is empty).
    """
    if data["itemType"] == "magazineArticle":
        text = sources.page_text(data["url"])
        return text if len(text) > 1000 else None
    doi = data.get("DOI")
    aid = arxiv_id(data.get("url", ""))
    attempts = [
        lambda: doi and sources.publisher_pdf(doi),
        lambda: aid and sources.arxiv_pdf(aid),
        lambda: doi and sources.unpaywall_pdf(doi, env("UNPAYWALL_EMAIL")),
    ]
    for attempt in attempts:
        pdf = attempt()
        if pdf:
            return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    return None


def write_script(client: genai.Client, data: dict, text: str) -> str:
    """Has Gemini write the two-host script.

    Args:
        client: Gemini client.
        data: The item's `data` dict.
        text: Paper or article text.

    Returns:
        The script, one `Alex:`/`Sam:` line per turn.
    """
    kind = "news article" if data["itemType"] == "magazineArticle" else "research paper"
    prompt = (
        PROMPT_FILE.read_text()
        .replace("{kind}", kind)
        .replace("{title}", data["title"])
        .replace("{text}", text[:200_000])  # replace, not format, so braces in the paper are safe
    )
    return client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=prompt).text.strip()


def _turns(script: str) -> list[tuple[str, str]]:
    """Splits a script into (speaker, text) turns, ignoring lines with no known speaker."""
    turns = []
    for line in script.splitlines():
        speaker, _, text = line.partition(":")
        if speaker.strip() in HOSTS and text.strip():
            turns.append((speaker.strip(), text.strip()))
    return turns


def _chunks(turns: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    pieces, current, size = [], [], 0
    for turn in turns:
        if current and size + len(turn[1]) > TTS_CHUNK_CHARS:
            pieces.append(current)
            current, size = [], 0
        current.append(turn)
        size += len(turn[1])
    return pieces + [current]


def synthesize(client: genai.Client, script: str) -> bytes:
    """Voices the script with Gemini multi-speaker text-to-speech.

    Uses the Interactions API, which the Gemini 3 TTS models require: each
    turn is sent as a text block tagged with its speaker.

    Args:
        client: Gemini client.
        script: Lines starting `Alex:` or `Sam:`.

    Returns:
        mp3 bytes (mono, 64 kbit/s).
    """
    speakers = [{"speaker": name, "voice": voice} for name, voice in HOSTS.items()]
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(64)
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(1)
    encoder.set_quality(2)
    mp3 = b""
    for piece in _chunks(_turns(script)):
        content = [
            {"type": "text", "text": text, "annotations": [{"type": "speech_metadata", "speaker": speaker}]}
            for speaker, text in piece
        ]
        interaction = client.interactions.create(
            model=GEMINI_TTS_MODEL,
            input=[{"type": "user_input", "content": content}],
            response_format={"type": "audio", "mime_type": "audio/l16"},  # raw pcm, so chunks can be joined
            generation_config={"speech_config": {"speakers": speakers}},
        )
        mp3 += encoder.encode(base64.b64decode(interaction.output_audio.data))
    return mp3 + encoder.flush()


def tag_mp3(path: Path, item: dict) -> None:
    """Writes title, author, DOI and Zotero link into the mp3.

    Args:
        path: The saved mp3.
        item: The Zotero item dict it was made from.
    """
    data = item["data"]
    creators = data.get("creators") or []
    link = f"zotero://select/library/items/{item['key']}"
    tags = ID3()
    tags.add(TIT2(encoding=3, text=data["title"]))
    if creators:
        tags.add(TPE1(encoding=3, text=creators[0].get("lastName", "")))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=f"DOI: {data.get('DOI', '-')}\n{link}"))
    tags.add(WOAF(url=link))
    tags.save(path)


def upgrade_preprint(zotero: Zotero, item: dict) -> dict:
    """Replaces a preprint with its journal version in Zotero, if one exists.

    Args:
        zotero: Zotero client.
        item: A Zotero item dict.

    Returns:
        The updated item (now a `journalArticle` with a DOI), or the same
        item if it is not a preprint or has not been published.
    """
    data = item["data"]
    aid = arxiv_id(data.get("url", "")) if data["itemType"] == "preprint" else None
    doi = sources.published_doi(aid) if aid else None
    journal = sources.crossref(doi) if doi else None
    if journal is None:
        return item
    kept = {k: data[k] for k in ("tags", "collections") if k in data}
    saved = zotero.write([{"key": item["key"], "version": item["version"], **journal, **kept}])[0]
    return item if "failed" in saved else saved


def run(directory: Path = PODCASTS_DIR, only_key: str | None = None) -> None:
    """Makes one episode, unless paused.

    Picks random eligible items (swapping a preprint for its journal
    version first, if published) until one yields text (items without one
    are tagged `no-pdf`), writes and voices the script, saves the mp3 and
    tags the item `podcasted`.

    Args:
        directory: The iCloud `Podcasts/` directory.
        only_key: Zotero item key to make the episode from, for testing; skips
            the random pick and the `to-read` and `podcasted` checks.
    """
    if is_paused(directory):
        print("paused, nothing to do")
        return
    zotero = Zotero()
    items = zotero.items()
    pool = [i for i in items if i["key"] == only_key] if only_key else eligible(items)
    random.shuffle(pool)
    for item in pool:
        item = upgrade_preprint(zotero, item)
        text = get_text(item["data"])
        if text is None:
            zotero.add_tags(item, ["no-pdf"])
            continue
        client = genai.Client(api_key=env("GEMINI_API_KEY"), http_options={"api_version": "v1beta"})
        name = file_name(item, date.today())
        script_file = SCRIPTS_DIR / name.replace(".mp3", ".txt")
        if not script_file.exists():  # a retry after a failed voicing reuses the script
            SCRIPTS_DIR.mkdir(exist_ok=True)
            script_file.write_text(write_script(client, item["data"], text))
        script = script_file.read_text()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_bytes(synthesize(client, script))
        tag_mp3(path, item)
        zotero.add_tags(item, ["podcasted"])
        print(f"saved {path}")
        return
    print("no eligible items left")
