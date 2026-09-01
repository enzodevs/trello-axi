"""Argument parsing and orchestration for trello-axi."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from .client import TrelloClient
from .config import load_credentials, save_credentials
from .errors import TrelloAxiError
from .models import board as normalize_board
from .models import card as normalize_card
from .models import label as normalize_label
from .models import trello_list as normalize_list
from .output import emit, emit_error
from .setup import install_hooks, install_skill


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trello-axi", description="Agent-native Trello CLI")
    parser.add_argument(
        "--format", choices=("toon", "json"), default="toon", help="output format (default: toon)"
    )
    parser.add_argument("--version", action="version", version="trello-axi 0.3.0")
    commands = parser.add_subparsers(dest="command")

    auth = commands.add_parser("auth", help="manage and verify credentials")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)
    auth_set = auth_commands.add_parser("set", help="store credentials in a mode-0600 file")
    auth_set.add_argument("--api-key", required=True)
    auth_set.add_argument("--token", required=True)
    auth_commands.add_parser("status", help="verify credentials against Trello")

    setup = commands.add_parser("setup", help="install agent integration")
    setup_commands = setup.add_subparsers(dest="setup_command", required=True)
    setup_commands.add_parser("skill", help="install the bundled agent skill")
    hooks = setup_commands.add_parser("hooks", help="install Claude/Codex SessionStart hooks")
    hooks.add_argument(
        "--command", dest="hook_command", help="absolute trello-axi executable used by hooks"
    )

    boards = commands.add_parser("boards", help="list visible boards")
    boards.add_argument("--all", action="store_true", help="include closed boards")

    board_cmd = commands.add_parser("board", help="show a board summary")
    board_cmd.add_argument("board")

    lists = commands.add_parser("lists", help="list board lists")
    lists.add_argument("--board", required=True)
    lists.add_argument("--all", action="store_true")

    labels = commands.add_parser("labels", help="list board labels")
    labels.add_argument("--board", required=True)

    label = commands.add_parser("label", help="create or update board labels")
    label_commands = label.add_subparsers(dest="label_command", required=True)
    label_create = label_commands.add_parser("create")
    label_create.add_argument("--board", required=True)
    label_create.add_argument("--name", required=True)
    label_create.add_argument("--color", required=True)
    label_ensure = label_commands.add_parser("ensure", help="idempotently create/update by name")
    label_ensure.add_argument("--board", required=True)
    label_ensure.add_argument("--name", required=True)
    label_ensure.add_argument("--color", required=True)
    label_update = label_commands.add_parser("update")
    label_update.add_argument("label")
    label_update.add_argument("--name")
    label_update.add_argument("--color")

    cards = commands.add_parser("cards", help="list cards")
    cards.add_argument("--board", required=True)
    cards.add_argument("--list")
    cards.add_argument("--limit", type=_positive_int, default=50)
    cards.add_argument("--full", action="store_true")
    cards.add_argument(
        "--label", action="append", default=[], help="filter by exact label name or ID"
    )
    cards.add_argument(
        "--label-order",
        help="comma-separated exact label names or IDs used as a custom sort order",
    )

    search = commands.add_parser("search", help="search cards")
    search.add_argument("query")
    search.add_argument("--board")
    search.add_argument("--limit", type=_positive_int, default=50)
    search.add_argument("--full", action="store_true")

    card = commands.add_parser("card", help="inspect or mutate cards")
    card_commands = card.add_subparsers(dest="card_command", required=True)
    view = card_commands.add_parser("view")
    view.add_argument("card")
    view.add_argument("--board")
    view.add_argument("--full", action="store_true", help="do not truncate the description")
    create = card_commands.add_parser("create")
    _create_args(create)
    ensure = card_commands.add_parser("ensure", help="create, move, or update by unique title")
    _create_args(ensure)
    update = card_commands.add_parser("update")
    update.add_argument("card")
    update.add_argument("--title")
    update.add_argument("--description")
    update.add_argument("--description-file", type=Path)
    update.add_argument("--due")
    update.add_argument("--due-complete", choices=("true", "false"))
    move = card_commands.add_parser("move")
    move.add_argument("card")
    move.add_argument("--board", required=True)
    move.add_argument("--list", required=True)
    archive = card_commands.add_parser("archive")
    archive.add_argument("card")
    comment = card_commands.add_parser("comment")
    comment.add_argument("card")
    comment.add_argument("--text", required=True)
    add_label = card_commands.add_parser("add-label")
    add_label.add_argument("card")
    add_label_group = add_label.add_mutually_exclusive_group(required=True)
    add_label_group.add_argument("--label-id")
    add_label_group.add_argument("--label", help="exact label name; requires --board")
    add_label.add_argument("--board")
    remove_label = card_commands.add_parser("remove-label")
    remove_label.add_argument("card")
    remove_label_group = remove_label.add_mutually_exclusive_group(required=True)
    remove_label_group.add_argument("--label-id")
    remove_label_group.add_argument("--label", help="exact label name; requires --board")
    remove_label.add_argument("--board")
    checklist = card_commands.add_parser("add-checklist")
    checklist.add_argument("card")
    checklist.add_argument("--name", required=True)
    checklist.add_argument("--item", action="append", default=[])
    batch = card_commands.add_parser("create-batch", help="create cards from JSON/YAML")
    batch.add_argument("--board", required=True)
    batch.add_argument("--list", required=True)
    batch.add_argument("--file", required=True, type=Path)
    batch.add_argument(
        "--ensure",
        action="store_true",
        help="idempotently ensure titles instead of always creating",
    )
    return parser


def _create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--board", required=True)
    parser.add_argument("--list", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--description-file", type=Path)
    parser.add_argument("--due")
    parser.add_argument("--label-id", action="append", default=[])


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1 or number > 1000:
        raise argparse.ArgumentTypeError("must be between 1 and 1000")
    return number


def _description(args: argparse.Namespace) -> str:
    if getattr(args, "description_file", None):
        if getattr(args, "description", ""):
            raise ValueError("use only one of --description and --description-file")
        return args.description_file.read_text()
    return getattr(args, "description", "") or ""


def _load_batch(path: Path) -> list[dict[str, Any]]:
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load batch file {path}: {exc}") from exc
    if isinstance(raw, dict):
        raw = raw.get("cards")
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError("batch file must be a list, or an object containing a `cards` list")
    for index, item in enumerate(raw, 1):
        if not str(item.get("title", "")).strip():
            raise ValueError(f"batch card {index} is missing a title")
        label_ids = item.get("label_ids", [])
        if not isinstance(label_ids, list) or not all(
            isinstance(label_id, str) and label_id.strip() for label_id in label_ids
        ):
            raise ValueError(f"batch card {index} label_ids must be a list of strings")
        due = item.get("due")
        if due is not None and not isinstance(due, str):
            raise ValueError(f"batch card {index} due must be a string")
    return raw


def run(args: argparse.Namespace) -> tuple[Any, str]:
    if args.command == "auth" and args.auth_command == "set":
        path = save_credentials(args.api_key, args.token)
        return {"configured": True, "path": str(path), "permissions": "0600"}, "auth"
    if args.command == "setup":
        if args.setup_command == "skill":
            path = install_skill()
            return {"installed": True, "skill": str(path)}, "setup"
        paths = install_hooks(command=args.hook_command)
        return {"installed": True, "hooks": [str(path) for path in paths]}, "setup"
    credentials = load_credentials()
    with TrelloClient(credentials) as client:
        if args.command == "auth":
            member = client.member()
            return {
                "authenticated": True,
                "username": member.get("username"),
                "name": member.get("fullName"),
            }, "auth"
        if args.command in {None, "boards"}:
            return [
                normalize_board(item)
                for item in client.boards(include_closed=getattr(args, "all", False))
            ], "boards"
        if args.command == "board":
            selected = client.resolve_board(args.board)
            lists = client.lists(args.board)
            cards = client.all_cards(args.board)
            counts = {item["id"]: 0 for item in lists}
            for item in cards:
                counts[item["idList"]] = counts.get(item["idList"], 0) + 1
            return {
                **normalize_board(selected),
                "list_count": len(lists),
                "open_card_count": len(cards),
                "lists": [
                    {"id": item["id"], "name": item["name"], "cards": counts[item["id"]]}
                    for item in lists
                ],
            }, "board"
        if args.command == "lists":
            return [
                normalize_list(item) for item in client.lists(args.board, include_closed=args.all)
            ], "lists"
        if args.command == "labels":
            return [normalize_label(item) for item in client.labels(args.board)], "labels"
        if args.command == "label":
            if args.label_command == "create":
                result = client.create_label(board=args.board, name=args.name, color=args.color)
                action = "created"
            elif args.label_command == "ensure":
                result, action = client.ensure_label(
                    board=args.board, name=args.name, color=args.color
                )
            else:
                result = client.update_label(args.label, name=args.name, color=args.color)
                action = "updated"
            return {"action": action, **normalize_label(result)}, "label"
        if args.command == "cards":
            raw_cards = client.cards(args.board, list_value=args.list, limit=args.limit)
            raw_cards = _filter_and_sort_cards(
                raw_cards, labels=args.label, label_order=args.label_order
            )
            return [normalize_card(item, full=args.full) for item in raw_cards], "cards"
        if args.command == "search":
            return [
                normalize_card(item, full=args.full)
                for item in client.search(args.query, board=args.board, limit=args.limit)
            ], "cards"
        if args.command == "card":
            return _run_card(client, args)
    raise ValueError("unknown command")


def _run_card(client: TrelloClient, args: argparse.Namespace) -> tuple[Any, str]:
    command = args.card_command
    if command == "view":
        limit = None if args.full else 2000
        return normalize_card(
            client.card(args.card, board=args.board), full=True, description_limit=limit
        ), "card"
    if command in {"create", "ensure"}:
        description = _description(args)
        if command == "create":
            result = client.create_card(
                board=args.board,
                list_value=args.list,
                title=args.title,
                description=description,
                due=args.due,
                label_ids=args.label_id,
            )
            action = "created"
        else:
            result, action = client.ensure_card(
                board=args.board,
                list_value=args.list,
                title=args.title,
                description=description,
                due=args.due,
                label_ids=args.label_id,
            )
        return {"action": action, **normalize_card(result, full=True)}, "card"
    if command == "update":
        description = _description(args) if args.description or args.description_file else None
        if all(value is None for value in (args.title, description, args.due, args.due_complete)):
            raise ValueError("card update requires at least one mutation flag")
        result = client.update_card(
            args.card,
            name=args.title,
            desc=description,
            due=args.due,
            dueComplete=args.due_complete,
        )
        return {"action": "updated", **normalize_card(result, full=True)}, "card"
    if command == "move":
        result, action = client.move_card(args.card, board=args.board, list_value=args.list)
        return {"action": action, **normalize_card(result)}, "card"
    if command == "archive":
        result, action = client.archive_card(args.card)
        return {"action": action, **normalize_card(result)}, "card"
    if command == "comment":
        result = client.comment(args.card, args.text)
        return {"action": "commented", "id": result.get("id"), "card_id": args.card}, "comment"
    if command in {"add-label", "remove-label"}:
        label_id = _resolve_label_argument(client, args)
        if command == "add-label":
            result = client.add_label(args.card, label_id)
        else:
            result = client.remove_label(args.card, label_id)
        return {"action": result["action"], "id": result.get("id")}, "label"
    if command == "add-checklist":
        result = client.add_checklist(args.card, args.name, args.item)
        return {
            "action": "checklist_added",
            "id": result.get("id"),
            "name": result.get("name"),
            "items": len(args.item),
        }, "checklist"
    if command == "create-batch":
        results = []
        target = client.resolve_list(args.board, args.list)
        index = client.index_cards(client.all_cards(args.board)) if args.ensure else {}
        for item in _load_batch(args.file):
            title = str(item["title"])
            description = str(item.get("description", ""))
            due = item.get("due")
            label_ids = item.get("label_ids", ())
            if args.ensure:
                result, action = client.ensure_card(
                    board=args.board,
                    list_value=args.list,
                    title=title,
                    description=description,
                    due=due,
                    label_ids=label_ids,
                    target_list=target,
                    card_index=index,
                )
                index[title.casefold()] = [result]
            else:
                result = client.create_card_in_list(
                    str(target["id"]),
                    title=title,
                    description=description,
                    due=due,
                    label_ids=label_ids,
                )
                action = "created"
            results.append({"action": action, **normalize_card(result)})
        return results, "cards"
    raise ValueError(f"unsupported card command: {command}")


def _label_keys(card: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for item in card.get("labels", []):
        keys.add(str(item.get("id", "")).casefold())
        keys.add(str(item.get("name", "")).casefold())
    return keys


def _filter_and_sort_cards(
    cards: list[dict[str, Any]], *, labels: list[str], label_order: str | None
) -> list[dict[str, Any]]:
    requested = {item.casefold() for item in labels}
    filtered = [item for item in cards if requested <= _label_keys(item)]
    if not label_order:
        return filtered
    order = {
        value.strip().casefold(): index
        for index, value in enumerate(label_order.split(","))
        if value.strip()
    }
    if not order:
        raise ValueError("--label-order must contain at least one label name or ID")
    fallback = len(order)
    return sorted(
        filtered,
        key=lambda item: min(
            (order[key] for key in _label_keys(item) if key in order), default=fallback
        ),
    )


def _resolve_label_argument(client: TrelloClient, args: argparse.Namespace) -> str:
    if args.label_id:
        return str(args.label_id)
    if not args.board:
        raise ValueError("--board is required when resolving --label by name")
    return str(client.resolve_label(args.board, args.label)["id"])


def _next_steps(args: argparse.Namespace, data: Any) -> tuple[str, ...]:
    if args.command in {None, "boards"}:
        return ("trello-axi board <board-id>", "trello-axi lists --board <board-id>")
    if args.command == "board":
        return (
            f"trello-axi cards --board {args.board} --list <list-id>",
            f"trello-axi search <query> --board {args.board}",
        )
    if args.command == "lists":
        return (f"trello-axi cards --board {args.board} --list <list-id>",)
    if args.command == "labels":
        return (f"trello-axi label ensure --board {args.board} --name <name> --color <color>",)
    if args.command == "label" and isinstance(data, dict) and data.get("id"):
        return (f"trello-axi card add-label <card-id> --label-id {data['id']}",)
    if args.command in {"cards", "search"}:
        return (
            "trello-axi card view <card-id>",
            "trello-axi card move <card-id> --board <board-id> --list <list-id>",
        )
    if args.command == "card" and isinstance(data, dict) and data.get("id"):
        return (
            f"trello-axi card view {data['id']}",
            f"trello-axi card comment {data['id']} --text <text>",
        )
    if args.command == "setup":
        return ("trello-axi auth status", "trello-axi boards")
    if args.command == "auth":
        return ("trello-axi boards", "trello-axi setup skill")
    return ()


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        data, name = run(args)
        emit(
            data,
            fmt=args.format,
            name=name,
            help_commands=_next_steps(args, data),
        )
        return 0
    except TrelloAxiError as exc:
        emit_error(
            str(exc),
            code=exc.__class__.__name__,
            fmt=args.format,
            help_commands=("trello-axi auth status", "trello-axi --help"),
        )
        return exc.exit_code
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit_error(
            str(exc), code="InputError", fmt=args.format, help_commands=("trello-axi --help",)
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
