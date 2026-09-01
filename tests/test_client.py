from __future__ import annotations

import httpx
import pytest

from trello_axi.client import TrelloClient
from trello_axi.config import Credentials
from trello_axi.errors import AmbiguousMatchError, AuthenticationError, NotFoundError

CREDS = Credentials("key", "token")


def client(handler: httpx.MockTransport) -> TrelloClient:
    return TrelloClient(CREDS, transport=handler)


def test_credentials_are_applied_without_appearing_in_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "key"
        assert request.url.params["token"] == "token"
        return httpx.Response(200, json={"id": "me"})

    with client(httpx.MockTransport(handler)) as api:
        assert api.member()["id"] == "me"


def test_authentication_error_is_stable() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(401, text="invalid token"))
    with client(transport) as api, pytest.raises(AuthenticationError):
        api.member()


def test_exact_resolution_and_ambiguity() -> None:
    objects = [{"id": "1", "name": "Dream"}, {"id": "2", "name": "dream"}]
    assert TrelloClient._resolve("1", objects, "board")["id"] == "1"
    with pytest.raises(AmbiguousMatchError):
        TrelloClient._resolve("DREAM", objects, "board")
    with pytest.raises(NotFoundError):
        TrelloClient._resolve("Other", objects, "board")


def test_ensure_label_updates_color_by_exact_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/members/me/boards"):
            return httpx.Response(200, json=[{"id": "b1", "name": "Dream"}])
        if path.endswith("/boards/b1/labels"):
            return httpx.Response(
                200, json=[{"id": "l1", "name": "Complexity: 5", "color": "blue"}]
            )
        if path.endswith("/labels/l1") and request.method == "PUT":
            assert "color=yellow" in request.content.decode()
            return httpx.Response(
                200, json={"id": "l1", "name": "Complexity: 5", "color": "yellow"}
            )
        raise AssertionError(f"unexpected {request.method} {path}")

    with client(httpx.MockTransport(handler)) as api:
        result, action = api.ensure_label(board="Dream", name="complexity: 5", color="yellow")
    assert action == "updated"
    assert result["color"] == "yellow"


def test_add_label_is_idempotent() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "id": "c1",
                "name": "Task",
                "labels": [{"id": "label-1", "name": "P1"}],
            },
        )
    )
    with client(transport) as api:
        result = api.add_label("c1", "label-1")
    assert result == {"id": "label-1", "action": "unchanged"}


def test_archive_is_idempotent() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, json={"id": "c1", "name": "Done", "closed": True, "idList": "l1"}
        )

    with client(httpx.MockTransport(handler)) as api:
        result, action = api.archive_card("c1")
    assert action == "unchanged"
    assert result["closed"] is True
    assert len(requests) == 1


def test_all_cards_paginates_past_one_thousand() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        path = request.url.path
        if path.endswith("/members/me/boards"):
            return httpx.Response(200, json=[{"id": "b1", "name": "Dream"}])
        if path.endswith("/boards/b1/cards"):
            calls += 1
            if calls == 1:
                return httpx.Response(
                    200,
                    json=[{"id": f"c{i}", "name": f"Card {i}"} for i in range(1000)],
                )
            assert request.url.params["before"] == "c999"
            return httpx.Response(200, json=[{"id": "older", "name": "Older"}])
        raise AssertionError(f"unexpected {request.method} {path}")

    with client(httpx.MockTransport(handler)) as api:
        cards = api.all_cards("Dream")
    assert len(cards) == 1001
    assert calls == 2


def test_ensure_applies_due_and_labels() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "PUT":
            return httpx.Response(
                200,
                json={
                    "id": "c1",
                    "name": "Task",
                    "idList": "l1",
                    "due": "2026-06-01",
                    "labels": [{"id": "green", "name": "Ready"}],
                },
            )
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    existing = {"task": [{"id": "c1", "name": "Task", "idList": "l1", "due": None, "labels": []}]}
    with client(httpx.MockTransport(handler)) as api:
        card, action = api.ensure_card(
            board="Dream",
            list_value="Backlog",
            title="Task",
            due="2026-06-01",
            label_ids=("green",),
            target_list={"id": "l1", "name": "Backlog"},
            card_index=existing,
        )
    assert action == "updated"
    assert card["due"] == "2026-06-01"
    body = requests[0].content.decode()
    assert "due=2026-06-01" in body
    assert "idLabels=green" in body


def test_ensure_creates_when_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/members/me/boards"):
            return httpx.Response(200, json=[{"id": "b1", "name": "Dream"}])
        if path.endswith("/boards/b1/lists"):
            return httpx.Response(200, json=[{"id": "l1", "name": "Backlog"}])
        if path.endswith("/boards/b1/cards"):
            return httpx.Response(200, json=[])
        if path.endswith("/cards") and request.method == "POST":
            return httpx.Response(
                200, json={"id": "c1", "name": "New", "idList": "l1", "closed": False}
            )
        raise AssertionError(f"unexpected {request.method} {path}")

    with client(httpx.MockTransport(handler)) as api:
        card, action = api.ensure_card(board="Dream", list_value="Backlog", title="New")
    assert (card["id"], action) == ("c1", "created")
