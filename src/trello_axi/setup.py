"""Idempotent agent skill and SessionStart hook installers."""

from __future__ import annotations

import json
import shutil
from importlib.resources import files
from pathlib import Path
from typing import Any

MARKER = "trello-axi"


def install_skill(destination: Path | None = None) -> Path:
    target = destination or Path.home() / ".agents" / "skills" / MARKER / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = files("trello_axi.resources").joinpath("SKILL.md").read_text()
    if not target.exists() or target.read_text() != source:
        target.write_text(source)
    return target


def install_hooks(*, command: str | None = None) -> list[Path]:
    """Install managed Claude Code and Codex SessionStart hooks."""
    executable = command or shutil.which("trello-axi")
    if not executable:
        raise ValueError("trello-axi executable was not found on PATH")
    hook = {"type": "command", "command": executable, "timeout": 10}
    installed = []
    for path in (Path.home() / ".claude" / "settings.json", Path.home() / ".codex" / "hooks.json"):
        settings = _load_object(path)
        hooks = settings.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError(f"{path} contains a non-object hooks setting")
        groups = hooks.setdefault("SessionStart", [])
        if not isinstance(groups, list):
            raise ValueError(f"{path} contains a non-list SessionStart setting")
        managed = None
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                continue
            if any(
                MARKER in str(item.get("command", ""))
                for item in group["hooks"]
                if isinstance(item, dict)
            ):
                managed = group
                break
        desired = {"matcher": "", "hooks": [hook]}
        if managed is None:
            groups.append(desired)
        else:
            managed.clear()
            managed.update(desired)
        _atomic_json(path, settings)
        installed.append(path)
    return installed


def _load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read agent settings {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"agent settings {path} must contain a JSON object")
    return raw


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.trello-axi.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)
