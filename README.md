# trello-axi

Agent-native, token-efficient CLI for Trello. It calls the official Trello REST API directly and implements the [AXI](https://axi.md/) design principles: compact truthful output, bounded reads, exact resolution, idempotent mutations, structured failures, batching, and non-interactive operation.

## Install

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install trello-axi
```

For development:

```bash
uv sync --locked --all-groups
uv run trello-axi --version
```

## Authentication

Prefer environment variables in managed environments:

```bash
export TRELLO_API_KEY='...'
export TRELLO_TOKEN='...'
trello-axi auth status
```

Or store them locally (the file is created with mode `0600`):

```bash
trello-axi auth set --api-key '...' --token '...'
```

Default path: `${XDG_CONFIG_HOME:-~/.config}/trello-axi/config.json`. Environment variables take precedence. Never commit the token or pass credentials through agent prompts.

## Agent-oriented workflows

No arguments returns live board data rather than help:

```bash
trello-axi
trello-axi boards
trello-axi board Dream
trello-axi lists --board Dream
trello-axi cards --board Dream --list Backlog --limit 50
trello-axi search videoaula --board Dream
trello-axi card view CARD_ID
```

Mutations:

```bash
trello-axi card create --board Dream --list Backlog --title 'Task' --description-file task.md
trello-axi card ensure --board Dream --list Backlog --title 'Task' --description-file task.md
trello-axi card update CARD_ID --title 'New title' --due 2026-06-01
trello-axi card move CARD_ID --board Dream --list Doing
trello-axi card comment CARD_ID --text 'Implementation started'
trello-axi card add-label CARD_ID --label-id LABEL_ID
trello-axi card add-checklist CARD_ID --name Acceptance --item 'Tests pass' --item 'Docs updated'
trello-axi card archive CARD_ID
```

`ensure` is idempotent by exact case-insensitive title: it creates a missing card, moves/updates one match, leaves the desired state unchanged, and refuses ambiguous matches.

Batch creation accepts JSON or YAML:

```yaml
cards:
  - title: First task
    description: Detailed scope
  - title: Second task
    due: '2026-06-30'
```

```bash
trello-axi card create-batch --board Dream --list Backlog --file cards.yaml --ensure
```

## Output contract

TOON-style output is the default and JSON is available globally:

```bash
trello-axi --format json cards --board Dream --limit 10
```

Unknown flags fail. Reads default to 50 records and are capped at 1000. Failures are written to stderr with stable exit codes:

| Code | Meaning |
|---:|---|
| 0 | Success / desired state already satisfied |
| 1 | Unexpected local failure |
| 2 | Invalid input or configuration |
| 3 | Authentication/permission failure |
| 4 | Resource not found |
| 5 | Ambiguous name; use an ID |
| 6 | Trello API/network failure |

## Scope

The MVP supports boards and lists, card CRUD, search, moves, archive, comments, labels, checklists, idempotent ensure, and batch creation. It intentionally excludes Power-Ups, webhooks, OAuth multi-user applications, and destructive permanent deletion.

## Development

```bash
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run ty check .
uv run pytest
uv build
```

## License

MIT
