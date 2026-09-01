"""Pure normalization functions for token-efficient API output."""

from __future__ import annotations

from typing import Any


def board(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "closed": raw.get("closed", False),
        "url": raw.get("url"),
    }


def trello_list(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "closed": raw.get("closed", False),
        "pos": raw.get("pos"),
    }


def label(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "color": raw.get("color"),
        "uses": raw.get("uses", 0),
    }


def card(
    raw: dict[str, Any], *, full: bool = False, description_limit: int | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "list_id": raw.get("idList"),
        "due": raw.get("due"),
    }
    labels = raw.get("labels") or []
    result["labels"] = ";".join(item.get("name") or item.get("color", "") for item in labels)
    if full:
        description = str(raw.get("desc", ""))
        truncated = description_limit is not None and len(description) > description_limit
        if truncated:
            description = description[:description_limit] + "…"
        result.update(
            description=description,
            description_chars=len(str(raw.get("desc", ""))),
            description_truncated=truncated,
            closed=raw.get("closed", False),
            url=raw.get("url"),
            due_complete=raw.get("dueComplete", False),
            member_ids=raw.get("idMembers", []),
            checklist_ids=raw.get("idChecklists", []),
        )
    return result
