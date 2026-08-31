from __future__ import annotations

import json
from pathlib import Path

import pytest

from trello_axi.setup import install_hooks, install_skill


def test_install_skill_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "skills" / "trello-axi" / "SKILL.md"
    assert install_skill(target) == target
    first = target.read_text()
    assert "name: trello-axi" in first
    assert install_skill(target).read_text() == first


def test_install_hooks_preserves_unmanaged_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    claude = tmp_path / ".claude" / "settings.json"
    claude.parent.mkdir()
    claude.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "",
                            "hooks": [{"type": "command", "command": "other-tool"}],
                        }
                    ]
                }
            }
        )
    )
    paths = install_hooks(command="/usr/local/bin/trello-axi")
    assert len(paths) == 2
    settings = json.loads(claude.read_text())
    groups = settings["hooks"]["SessionStart"]
    assert groups[0]["hooks"][0]["command"] == "other-tool"
    assert groups[1]["hooks"][0]["command"] == "/usr/local/bin/trello-axi"


def test_install_hooks_updates_managed_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    install_hooks(command="/old/trello-axi")
    install_hooks(command="/new/trello-axi")
    settings = json.loads((tmp_path / ".codex" / "hooks.json").read_text())
    groups = settings["hooks"]["SessionStart"]
    assert len(groups) == 1
    assert groups[0]["hooks"][0]["command"] == "/new/trello-axi"
