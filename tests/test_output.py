import json

from trello_axi.output import emit_error, toon


def test_toon_tabular_output() -> None:
    assert toon([{"id": "1", "name": "Backlog"}], name="lists") == "lists[1]{id,name}:\n  1,Backlog"


def test_toon_escapes_multiline_and_commas() -> None:
    output = toon([{"name": "a,b", "description": "one\ntwo"}], name="cards")
    assert '"a,b"' in output
    assert "one\\ntwo" in output


def test_empty_collection_is_truthful() -> None:
    assert toon([], name="cards") == "cards[0]:"


def test_json_errors_are_machine_readable(capsys) -> None:  # type: ignore[no-untyped-def]
    emit_error("bad input", code="InputError", fmt="json", help_commands=("trello-axi --help",))
    payload = json.loads(capsys.readouterr().err)
    assert payload == {
        "error": "InputError",
        "message": "bad input",
        "help": ["trello-axi --help"],
    }
