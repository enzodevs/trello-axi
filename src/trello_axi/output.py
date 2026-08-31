"""Compact deterministic output for agents."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).replace("\n", "\\n")
    if any(char in text for char in ',"'):
        return '"' + text.replace('"', '""') + '"'
    return text


def toon(data: Any, *, name: str = "result") -> str:
    """Render a small TOON-style subset: scalar maps and tabular arrays."""
    if isinstance(data, list):
        if not data:
            return f"{name}[0]:"
        rows = [item for item in data if isinstance(item, Mapping)]
        if len(rows) == len(data):
            fields = list(
                dict.fromkeys(
                    key for row in rows for key in row if not isinstance(row[key], (dict, list))
                )
            )
            lines = [f"{name}[{len(rows)}]{{{','.join(fields)}}}:"]
            lines.extend(
                "  " + ",".join(_scalar(row.get(field)) for field in fields) for row in rows
            )
            return "\n".join(lines)
    if isinstance(data, Mapping):
        lines = [f"{name}:"]
        for key, value in data.items():
            if isinstance(value, list):
                lines.append(toon(value, name=str(key)))
            elif isinstance(value, Mapping):
                lines.append(
                    f"  {key}: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
                )
            else:
                lines.append(f"  {key}: {_scalar(value)}")
        return "\n".join(lines)
    return f"{name}: {_scalar(data)}"


def emit(data: Any, *, fmt: str = "toon", name: str = "result") -> None:
    if fmt == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(toon(data, name=name))


def emit_error(
    message: str, *, code: str, fmt: str = "toon", help_commands: Sequence[str] = ()
) -> None:
    payload = {"error": code, "message": message, "help": list(help_commands)}
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    else:
        print(toon(payload, name="failure"), file=sys.stderr)
