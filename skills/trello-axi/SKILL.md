---
name: trello-axi
description: Use Trello through an agent-native CLI for compact board context, card CRUD, search, comments, labels, checklists, and idempotent batch workflows.
---

# trello-axi

Use IDs after initial discovery. Keep reads bounded and request JSON only when another program must parse output.

## Discover

```bash
trello-axi auth status
trello-axi boards
trello-axi board "<board>"
trello-axi cards --board "<board>" --list "<list>" --limit 50
```

## Labels and custom taxonomies

Labels are generic. Resolve or create them by exact name, then filter/order cards using a user-defined taxonomy:

```bash
trello-axi labels --board "<board>"
trello-axi label ensure --board "<board>" --name "<label>" --color blue
trello-axi card add-label <card-id> --board "<board>" --label "<label>"
trello-axi cards --board "<board>" --label "<label>"
trello-axi cards --board "<board>" --label-order "<first>,<second>,<third>"
```

## Mutate safely

Prefer idempotent `ensure` when retrying is possible:

```bash
trello-axi card ensure --board "<board>" --list "<list>" --title "<title>" --description-file <path>
```

Use card IDs for subsequent operations:

```bash
trello-axi card move <card-id> --board "<board>" --list "<list>"
trello-axi card comment <card-id> --text "<comment>"
trello-axi card archive <card-id>
```

Execute explicit archive and batch requests noninteractively; do not introduce confirmation prompts inside the command workflow. Never print, log, or request API credentials in chat. Do not use permanent deletion; this CLI intentionally archives cards instead.
