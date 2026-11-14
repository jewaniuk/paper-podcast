"""Command line entry points: `paper-podcast <command>` and `paper-pick`."""

import argparse

from paper_podcast import enrich, pick, podcast
from paper_podcast.zotero import Zotero


def main() -> None:
    """Runs `enrich`, `podcast`, `pause` or `resume`."""
    parser = argparse.ArgumentParser(prog="paper-podcast")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("podcast", help="make one episode").add_argument(
        "--item", help="Zotero item key to use instead of a random pick (for testing)"
    )
    for name, text in [
        ("enrich", "tag items changed since the last run"),
        ("pause", "stop new episodes"),
        ("resume", "allow new episodes"),
    ]:
        sub.add_parser(name, help=text)
    args = parser.parse_args()
    if args.command == "enrich":
        enrich.run()
    elif args.command == "podcast":
        podcast.run(only_key=args.item)
    else:
        podcast.set_paused(args.command == "pause")


def pick_main() -> None:
    """Prints links to N random `to-read` papers and N articles."""
    parser = argparse.ArgumentParser(prog="paper-pick")
    parser.add_argument("-n", type=int, default=3, help="how many of each kind (default 3)")
    papers, articles = pick.sample(Zotero().items(), parser.parse_args().n)
    for heading, chosen in [("papers", papers), ("articles", articles)]:
        print(f"\n{heading}")
        for item in chosen:
            print(f"  {item['data']['title']}\n    {pick.link(item)}")
