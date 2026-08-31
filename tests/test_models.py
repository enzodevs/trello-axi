from trello_axi.models import card


def test_card_list_shape_is_compact() -> None:
    result = card(
        {"id": "c1", "name": "Task", "idList": "l1", "closed": False, "url": "https://example"}
    )
    assert result == {"id": "c1", "name": "Task", "list_id": "l1", "due": None, "labels": ""}


def test_card_view_signals_description_truncation() -> None:
    result = card({"id": "c1", "name": "Task", "desc": "abcdef"}, full=True, description_limit=3)
    assert result["description"] == "abc…"
    assert result["description_chars"] == 6
    assert result["description_truncated"] is True


def test_full_card_view_does_not_truncate() -> None:
    result = card({"id": "c1", "name": "Task", "desc": "abcdef"}, full=True)
    assert result["description"] == "abcdef"
    assert result["description_truncated"] is False
