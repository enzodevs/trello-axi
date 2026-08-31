from __future__ import annotations

from pathlib import Path

import pytest

from trello_axi.cli import _load_batch, _parser, _positive_int


def test_unknown_flags_fail_loud() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["boards", "--invented"])


def test_limits_are_bounded() -> None:
    with pytest.raises(Exception, match="between"):
        _positive_int("1001")


def test_yaml_batch(tmp_path: Path) -> None:
    path = tmp_path / "cards.yaml"
    path.write_text("cards:\n  - title: First\n    description: Body\n")
    assert _load_batch(path) == [{"title": "First", "description": "Body"}]


def test_batch_requires_titles(tmp_path: Path) -> None:
    path = tmp_path / "cards.json"
    path.write_text('[{"description":"missing"}]')
    with pytest.raises(ValueError, match="missing a title"):
        _load_batch(path)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ('[{"title":"Bad labels","label_ids":1}]', "label_ids must be a list"),
        ('[{"title":"Bad label","label_ids":[1]}]', "label_ids must be a list"),
        ('[{"title":"Bad due","due":20260601}]', "due must be a string"),
    ],
)
def test_batch_validates_optional_field_types(tmp_path: Path, payload: str, message: str) -> None:
    path = tmp_path / "cards.json"
    path.write_text(payload)
    with pytest.raises(ValueError, match=message):
        _load_batch(path)
