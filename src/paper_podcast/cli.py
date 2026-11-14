"""Command line entry points: `paper-podcast <command>` and `paper-pick`."""

import argparse
import sys

from paper_podcast import enrich, pick, podcast
from paper_podcast.zotero import Zotero


def main() -> None:
    """Runs `enrich`, `podcast`, `progress`, `pause` or `resume`."""
    parser = argparse.ArgumentParser(prog="paper-podcast")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("podcast", help="make one episode").add_argument(
        "--item", help="Zotero item key to use instead of a random pick (for testing)"
    )
    for name, text in [
        ("enrich", "tag items changed since the last run"),
        ("progress", "count read papers and articles"),
        ("pause", "stop new episodes"),
        ("resume", "allow new episodes"),
    ]:
        sub.add_parser(name, help=text)
    args = parser.parse_args()
    if args.command == "enrich":
        enrich.run()
    elif args.command == "podcast":
        podcast.run(only_key=args.item)
    elif args.command == "progress":
        for heading, items in zip(("papers", "articles"), pick.split_kinds(Zotero().items())):
            print(pick.progress(heading, items))
    else:
        podcast.set_paused(args.command == "pause")


def _styled(text: str, sgr: str, on: bool, url: str = "") -> str:
    """Wraps text in ANSI style codes and, given a url, an OSC 8 hyperlink.

    Args:
        text: The text to show.
        sgr: ANSI style parameters, e.g. `1` for bold or `2` for dim.
        on: False to return the text unchanged, as when output is piped.
        url: Where the text links to, or empty for no link.

    Returns:
        The styled text.
    """
    if not on:
        return text
    if url:
        text = f"\x1b]8;;{url}\x1b\\{text}\x1b]8;;\x1b\\"
    return f"\x1b[{sgr}m{text}\x1b[0m"


def pick_main() -> None:
    """Prints N random `to-read` papers and N articles, each title linking to the item."""
    parser = argparse.ArgumentParser(prog="paper-pick")
    parser.add_argument("-n", type=int, default=3, help="how many of each kind (default 3)")
    n = parser.parse_args().n
    on = sys.stdout.isatty()
    pools = pick.split_kinds(pick.to_read(Zotero().items()))
    for heading, pool in zip(("papers", "articles"), pools):
        print(f"\n{_styled(heading, '1;36', on)}  ({min(n, len(pool))} of {len(pool)} to-read)")
        for item in pick.sample(pool, n):
            print(f"\n  {_styled(item['data']['title'], '1', on, pick.link(item))}")
            print(f"  {pick.byline(item)}")
            if tags := pick.tag_line(item):
                print(f"  {_styled(tags, '2', on)}")
