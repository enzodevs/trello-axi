from __future__ import annotations

import json
from pathlib import Path

import pytest

from trello_axi.config import load_credentials, save_credentials


def test_environment_takes_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "file", "token": "file"}))
    monkeypatch.setenv("TRELLO_API_KEY", "environment-key")
    monkeypatch.setenv("TRELLO_TOKEN", "environment-token")
    credentials = load_credentials(path)
    assert credentials.api_key == "environment-key"
    assert credentials.token == "environment-token"


def test_save_credentials_is_private(tmp_path: Path) -> None:
    path = save_credentials("key", "token", tmp_path / "nested" / "config.json")
    assert path.stat().st_mode & 0o777 == 0o600
    assert load_credentials(path).token == "token"


def test_wrong_shaped_credentials_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TRELLO_API_KEY", raising=False)
    monkeypatch.delenv("TRELLO_TOKEN", raising=False)
    path = tmp_path / "config.json"
    path.write_text("[]")
    with pytest.raises(ValueError, match="JSON object"):
        load_credentials(path)


def test_missing_credentials_is_actionable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TRELLO_API_KEY", raising=False)
    monkeypatch.delenv("TRELLO_TOKEN", raising=False)
    with pytest.raises(ValueError, match="auth set"):
        load_credentials(tmp_path / "missing")
