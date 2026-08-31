from trello_axi.cli import main


def test_version_is_fast_path(capsys) -> None:  # type: ignore[no-untyped-def]
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "trello-axi" in capsys.readouterr().out
