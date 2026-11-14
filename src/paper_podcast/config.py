"""Settings read from the environment, and the paths the tools share."""

import os
from pathlib import Path

PODCASTS_DIR = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Podcasts"
STATE_FILE = Path.home() / ".local/state/paper-podcast/state.json"

GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")


def env(name: str) -> str:
    """Reads a required environment variable.

    Args:
        name: Variable name, e.g. `ZOTERO_API_KEY`.

    Returns:
        The variable's value.

    Raises:
        SystemExit: If the variable is not set.
    """
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is not set (add it to ~/.config/secrets.zsh)")
    return value
