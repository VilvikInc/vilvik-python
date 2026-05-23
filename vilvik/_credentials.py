"""Local credential cache for `vilvik login` (the device-auth flow).

Stores a single API key as JSON at ``$XDG_CONFIG_HOME/vilvik/credentials``
(default ``~/.config/vilvik/credentials``), readable only by the user.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "vilvik"


def credentials_path() -> str:
    return str(_config_dir() / "credentials")


def save_api_key(api_key: str) -> None:
    d = _config_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / "credentials"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps({"api_key": api_key}).encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(str(path), 0o600)


def load_api_key() -> Optional[str]:
    path = _config_dir() / "credentials"
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    key = data.get("api_key")
    return key or None
