"""Thin Trello REST adapter with exact-name resolution and safe mutations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from .config import Credentials
from .errors import AmbiguousMatchError, ApiError, AuthenticationError, NotFoundError

CARD_FIELDS = "id,name,idList,desc,due,dueComplete,closed,url,labels,idMembers,idChecklists"


class TrelloClient:
    def __init__(
        self, credentials: Credentials, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._client = httpx.Client(
            base_url="https://api.trello.com/1",
            params={"key": credentials.api_key, "token": credentials.token},
            timeout=30,
            transport=transport,
        )

    def __enter__(self) -> TrelloClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self._client.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(f"Trello request failed: {exc}") from exc
        if response.status_code in {401, 403}:
            raise AuthenticationError("Trello rejected the credentials or required permission")
        if response.status_code == 404:
            raise NotFoundError("Trello resource was not found or is not visible to this token")
        if response.is_error:
            try:
                detail = response.json().get("message", response.text)
            except (ValueError, AttributeError):
                detail = response.text
            raise ApiError(
                f"Trello API returned HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        if not response.content:
            return {}
        return response.json()

    def member(self) -> dict[str, Any]:
        return self.request("GET", "/members/me", params={"fields": "id,username,fullName"})

    def boards(self, *, include_closed: bool = False) -> list[dict[str, Any]]:
        return self.request(
            "GET",
            "/members/me/boards",
            params={"filter": "all" if include_closed else "open", "fields": "id,name,closed,url"},
        )

    def resolve_board(self, value: str) -> dict[str, Any]:
        return self._resolve(value, self.boards(include_closed=True), "board")

    def lists(self, board: str, *, include_closed: bool = False) -> list[dict[str, Any]]:
        board_id = self.resolve_board(board)["id"]
        return self.request(
            "GET",
            f"/boards/{board_id}/lists",
            params={"filter": "all" if include_closed else "open", "fields": "id,name,closed,pos"},
        )

    def resolve_list(self, board: str, value: str) -> dict[str, Any]:
        return self._resolve(value, self.lists(board, include_closed=True), "list")

    def cards(
        self, board: str, *, list_value: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        path = self._cards_path(board, list_value)
        return self.request(
            "GET",
            path,
            params={"filter": "open", "limit": limit, "fields": CARD_FIELDS},
        )

    def all_cards(self, board: str) -> list[dict[str, Any]]:
        """Read every open card with deterministic Trello ID pagination."""
        path = self._cards_path(board, None)
        results: list[dict[str, Any]] = []
        before: str | None = None
        while True:
            params = {"filter": "open", "limit": 1000, "fields": CARD_FIELDS}
            if before:
                params["before"] = before
            page = self.request("GET", path, params=params)
            results.extend(page)
            if len(page) < 1000:
                return results
            next_before = str(page[-1]["id"])
            if next_before == before:
                raise ApiError("Trello card pagination did not advance")
            before = next_before

    def _cards_path(self, board: str, list_value: str | None) -> str:
        if list_value:
            list_id = self.resolve_list(board, list_value)["id"]
            return f"/lists/{list_id}/cards"
        board_id = self.resolve_board(board)["id"]
        return f"/boards/{board_id}/cards"

    def card(self, value: str, *, board: str | None = None) -> dict[str, Any]:
        if board:
            return self._resolve(value, self.all_cards(board), "card")
        return self.request("GET", f"/cards/{value}", params={"fields": CARD_FIELDS})

    def search(
        self, query: str, *, board: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "query": query,
            "modelTypes": "cards",
            "card_fields": CARD_FIELDS,
            "cards_limit": limit,
        }
        if board:
            params["idBoards"] = self.resolve_board(board)["id"]
        result = self.request("GET", "/search", params=params)
        return result.get("cards", [])

    def create_card(
        self,
        *,
        board: str,
        list_value: str,
        title: str,
        description: str = "",
        due: str | None = None,
        label_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        list_id = self.resolve_list(board, list_value)["id"]
        return self.create_card_in_list(
            list_id, title=title, description=description, due=due, label_ids=label_ids
        )

    def create_card_in_list(
        self,
        list_id: str,
        *,
        title: str,
        description: str = "",
        due: str | None = None,
        label_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "idList": list_id,
            "name": title,
            "desc": description,
            "pos": "bottom",
        }
        if due is not None:
            data["due"] = due
        if label_ids:
            data["idLabels"] = ",".join(label_ids)
        return self.request("POST", "/cards", data=data)

    def ensure_card(
        self,
        *,
        board: str,
        list_value: str,
        title: str,
        description: str = "",
        due: str | None = None,
        label_ids: Sequence[str] = (),
        target_list: Mapping[str, Any] | None = None,
        card_index: Mapping[str, Sequence[dict[str, Any]]] | None = None,
    ) -> tuple[dict[str, Any], str]:
        target = target_list or self.resolve_list(board, list_value)
        index = card_index if card_index is not None else self.index_cards(self.all_cards(board))
        matches = list(index.get(title.casefold(), ()))
        if len(matches) > 1:
            raise AmbiguousMatchError(f"multiple cards named {title!r}; use an ID")
        if not matches:
            return self.create_card_in_list(
                str(target["id"]),
                title=title,
                description=description,
                due=due,
                label_ids=label_ids,
            ), "created"
        current = matches[0]
        changes: dict[str, Any] = {}
        if current.get("idList") != target["id"]:
            changes["idList"] = target["id"]
        if description and current.get("desc") != description:
            changes["desc"] = description
        if due is not None and current.get("due") != due:
            changes["due"] = due
        if label_ids:
            current_labels = {str(label.get("id")) for label in current.get("labels", [])}
            if current_labels != set(label_ids):
                changes["idLabels"] = ",".join(label_ids)
        if changes:
            current = self.request("PUT", f"/cards/{current['id']}", data=changes)
            return current, "updated"
        return current, "unchanged"

    @staticmethod
    def index_cards(cards: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        for item in cards:
            index.setdefault(str(item.get("name", "")).casefold(), []).append(item)
        return index

    def update_card(self, card_id: str, **changes: Any) -> dict[str, Any]:
        data = {key: value for key, value in changes.items() if value is not None}
        if not data:
            return self.card(card_id)
        return self.request("PUT", f"/cards/{card_id}", data=data)

    def move_card(self, card_id: str, *, board: str, list_value: str) -> tuple[dict[str, Any], str]:
        target = self.resolve_list(board, list_value)
        current = self.card(card_id)
        if current.get("idList") == target["id"]:
            return current, "unchanged"
        return self.update_card(card_id, idList=target["id"]), "moved"

    def archive_card(self, card_id: str) -> tuple[dict[str, Any], str]:
        current = self.card(card_id)
        if current.get("closed"):
            return current, "unchanged"
        return self.update_card(card_id, closed="true"), "archived"

    def comment(self, card_id: str, text: str) -> dict[str, Any]:
        return self.request("POST", f"/cards/{card_id}/actions/comments", data={"text": text})

    def add_label(self, card_id: str, label_id: str) -> dict[str, Any]:
        return self.request("POST", f"/cards/{card_id}/idLabels", data={"value": label_id})

    def add_checklist(self, card_id: str, name: str, items: Sequence[str]) -> dict[str, Any]:
        checklist = self.request("POST", f"/cards/{card_id}/checklists", data={"name": name})
        for item in items:
            self.request("POST", f"/checklists/{checklist['id']}/checkItems", data={"name": item})
        return checklist

    @staticmethod
    def _resolve(value: str, objects: Sequence[Mapping[str, Any]], kind: str) -> dict[str, Any]:
        by_id = [item for item in objects if item.get("id") == value]
        if by_id:
            return dict(by_id[0])
        exact = [
            item for item in objects if str(item.get("name", "")).casefold() == value.casefold()
        ]
        if not exact:
            raise NotFoundError(f"{kind} {value!r} was not found; use `{kind}s` to list valid IDs")
        if len(exact) > 1:
            ids = ", ".join(str(item.get("id")) for item in exact)
            raise AmbiguousMatchError(f"{kind} {value!r} is ambiguous; matching IDs: {ids}")
        return dict(exact[0])
