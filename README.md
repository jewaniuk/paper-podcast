# paper-podcast

Tools for a Zotero paper library and a daily two-host podcast of one unread paper.

- `paper-podcast enrich` adds OpenAlex keywords and `group/<last author>` as automatic tags to items changed since the last run
- `paper-podcast podcast` makes one episode into iCloud Drive `Podcasts/` and tags the item `podcasted`
- `paper-podcast pause` / `resume` create / remove `Podcasts/paused`, which stops `podcast` (it can also be done in the iOS Files app)
- `paper-pick [-n N]` prints N random `to-read` papers and N articles

## Setup

Put these in `~/.config/secrets.zsh`:

```
export ZOTERO_API_KEY=...      # zotero.org/settings/keys, read and write
export ZOTERO_USER_ID=...      # same page, "your userID for use in API calls"
export GEMINI_API_KEY=...      # aistudio.google.com, free tier
export UNPAYWALL_EMAIL=...     # any address; unpaywall requires one per request
```

Then `uv sync` and `uv run pytest`.

## Scheduling on the Mac Mini

```
cp launchd/com.jewaniuk.paper-podcast.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jewaniuk.paper-podcast.plist
launchctl kickstart gui/$(id -u)/com.jewaniuk.paper-podcast   # run once now to test
```

Log: `/tmp/paper-podcast.log`. Remove with `launchctl bootout gui/$(id -u)/com.jewaniuk.paper-podcast`.
