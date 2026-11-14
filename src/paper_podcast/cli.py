"""Command line entry points: `paper-podcast <command>` and `paper-pick`."""

import argparse

from paper_podcast import enrich, migrate, pick, podcast
from paper_podcast.config import VAULT_LIBRARY
from paper_podcast.zotero import Zotero


def main() -> None:
    """Runs `migrate`, `enrich`, `podcast`, `pause` or `resume`."""
    parser = argparse.ArgumentParser(prog="paper-podcast")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="copy the vault's Library/ into Zotero").add_argument(
        "--dry-run", action="store_true", help="look up everything but write nothing"
    )
    for name, text in [
        ("enrich", "tag items changed since the last run"),
        ("podcast", "make one episode"),
        ("pause", "stop new episodes"),
        ("resume", "allow new episodes"),
    ]:
        sub.add_parser(name, help=text)
    args = parser.parse_args()
    if args.command == "migrate":
        migrate.run(VAULT_LIBRARY, args.dry_run)
    elif args.command == "enrich":
        enrich.run()
    elif args.command == "podcast":
        podcast.run()
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
