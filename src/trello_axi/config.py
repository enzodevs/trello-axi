"""Credential loading without leaking secrets."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Credentials:
    api_key: str
    token: str


def default_config_path() -> Path:
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "trello-axi"
        / "config.json"
    )


def load_credentials(config_path: Path | None = None) -> Credentials:
    """Load environment credentials first, then the local config file."""
    api_key = os.environ.get("TRELLO_API_KEY", "").strip()
    token = os.environ.get("TRELLO_TOKEN", "").strip()
    path = config_path or default_config_path()
    if (not api_key or not token) and path.exists():
        try:
            raw = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read credential file {path}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise ValueError(f"credential file {path} must contain a JSON object")
        api_key = api_key or str(raw.get("api_key", "")).strip()
        token = token or str(raw.get("token", "")).strip()
    if not api_key or not token:
        raise ValueError(
            "Trello credentials are missing. Set TRELLO_API_KEY and TRELLO_TOKEN, "
            "or run `trello-axi auth set --api-key <key> --token <token>`."
        )
    return Credentials(api_key=api_key, token=token)


def save_credentials(api_key: str, token: str, config_path: Path | None = None) -> Path:
    if not api_key.strip() or not token.strip():
        raise ValueError("both --api-key and --token are required")
    path = config_path or default_config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    payload = json.dumps({"api_key": api_key.strip(), "token": token.strip()}) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise
    return path
