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

Install the bundled skill and optional Claude Code/Codex SessionStart hooks:

```bash
trello-axi setup skill
trello-axi setup hooks
```

The hook installer preserves unmanaged hooks and updates only entries marked for `trello-axi`.

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
trello-axi labels --board Dream
trello-axi card view CARD_ID            # descriptions are bounded to 2,000 chars
trello-axi card view CARD_ID --full     # explicitly request the complete description
```

Mutations:

```bash
trello-axi card create --board Dream --list Backlog --title 'Task' --description-file task.md
trello-axi card ensure --board Dream --list Backlog --title 'Task' --description-file task.md
trello-axi card update CARD_ID --title 'New title' --due 2026-06-01
trello-axi card move CARD_ID --board Dream --list Doing
trello-axi card comment CARD_ID --text 'Implementation started'
trello-axi label ensure --board Dream --name 'Complexity: 5' --color yellow
trello-axi card add-label CARD_ID --board Dream --label 'Complexity: 5'
trello-axi card remove-label CARD_ID --board Dream --label 'Complexity: 5'
trello-axi card add-checklist CARD_ID --name Acceptance --item 'Tests pass' --item 'Docs updated'
trello-axi card archive CARD_ID
```

Labels are taxonomy-agnostic. For example, users can model Planning Poker and priority independently:

```bash
for points in 1 2 3 5 8 13 21; do
  trello-axi label ensure --board Dream --name "Complexity: $points" --color blue
done
for priority in P0 P1 P2 P3; do
  trello-axi label ensure --board Dream --name "Priority: $priority" --color red
done

trello-axi cards --board Dream --label 'Priority: P1'
trello-axi cards --board Dream --label-order 'Complexity: 1,Complexity: 2,Complexity: 3,Complexity: 5,Complexity: 8,Complexity: 13,Complexity: 21'
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

TOON-style output is the default and includes contextual next-command suggestions. JSON is available globally and uses a stable `{<resource>: ..., "help": [...]}` envelope:

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

The CLI supports boards and lists, generic label management, card CRUD, label filtering and custom ordering, search, moves, archive, comments, checklists, idempotent ensure, and batch creation. It intentionally excludes Power-Ups, webhooks, OAuth multi-user applications, and destructive permanent deletion.

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
