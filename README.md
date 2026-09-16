# Antigravity

A lightweight, file-based multi-agent workflow for Codex and other coding agents.

Antigravity gives a repository a small operating system for agentic work: clear roles, explicit handoffs, durable task state, dependency-aware readiness, verification evidence, portable task bundles, and a repeatable definition of done. It is designed for solo builders and small teams that want stronger agent autonomy without a heavy orchestration server.

## Why

Agent workflows often fail for predictable reasons:

- every task starts from zero context;
- planning, implementation, review, and release get mixed together;
- agents ask for unnecessary confirmations;
- important constraints disappear between turns;
- token usage grows because the same context is repeated;
- there is no durable record of what is done, blocked, or actually verified.

Antigravity uses repository files as the control plane so humans and agents can inspect the same source of truth.

## Core roles

1. **Orchestrator** — decomposes work, routes it, and owns completion.
2. **Researcher** — resolves unknowns and records evidence, without modifying product code.
3. **Builder** — implements the approved plan with the smallest safe change set.
4. **Reviewer** — checks correctness, regressions, security, and instruction compliance.
5. **Finisher** — runs final checks, updates documentation, and prepares the handoff/release summary.

## Quick start

```bash
python -m pip install -e .
antigravity init
antigravity task "Prepare API schema"
```

`antigravity init` creates:

```text
AGENTS.md
.antigravity/
  state.json
  tasks/
```

A task command creates a durable task brief containing objective, constraints, acceptance criteria, dependencies, handoffs, review findings, verification records, and completion state.

## Operating model

Antigravity follows five rules:

- **Act when the request is clear.** Do not ask for confirmation that adds no safety or information value.
- **Clarify only material ambiguity.** If a reasonable default is reversible, state it and proceed.
- **Separate roles.** Research does not silently become implementation; review does not rewrite the whole solution.
- **Use compact handoffs.** Pass decisions, evidence, changed files, risks, and next action — not the entire conversation.
- **Finish the loop.** A task is not complete until verification and documentation are recorded.

See [`docs/WORKFLOW.md`](docs/WORKFLOW.md) for the full lifecycle and [`AGENTS.example.md`](AGENTS.example.md) for a drop-in repository policy.

## CLI

### Initialize a repository

```bash
antigravity init
```

### Create a task

```bash
antigravity task "Fix mobile navigation overlap" \
  --constraint "Do not change desktop navigation" \
  --accept "No overlap at 320px width" \
  --accept "Existing tests pass"
```

### Add task dependencies

Use repeatable `--depends-on` arguments to express prerequisites without turning Antigravity into a scheduler:

```bash
antigravity task "Build GitHub adapter" \
  --depends-on 20260917-010000-define-adapter-schema \
  --depends-on 20260917-011500-add-auth-boundary
```

`antigravity status` marks incomplete dependency chains as blocked, missing task references as `blocked=missing:<id>`, dependency cycles as `blocked=cycle`, and runnable planned tasks as `ready`.

### Record a review finding

```bash
antigravity review <task-id> "Add a regression check" \
  --severity warning \
  --path src/navigation.css
```

Review findings are stored in both the task state and the human-readable task brief.

### Record a verification result

Antigravity records evidence but does **not** execute the command for you:

```bash
pytest -q
antigravity verify <task-id> "pytest -q" \
  --result passed \
  --note "12 tests passed"
```

Supported results are `passed`, `failed`, and `skipped`. Each record stores the check name, result, timestamp, and optional note in `.antigravity/state.json`, while also appending a readable entry to the task brief.

### Export and import a task brief

A task can be moved between repositories as a portable JSON bundle containing both machine-readable state and the human-readable Markdown brief:

```bash
antigravity export-task <task-id> --output task.bundle.json
antigravity --root ../another-repo import-task task.bundle.json
```

Imports reject unsupported bundle schemas, duplicate task IDs, and unsafe IDs that could escape `.antigravity/tasks/`. Imported task paths are always rewritten inside the destination repository.

### Inspect state

```bash
antigravity status
```

Status combines readiness, review count, and verification summaries, for example:

```text
planned    <task-id>  Build adapter  blocked=<dependency-id> reviews=1 checks=2/3 failed=1
```

## Repository structure

```text
src/antigravity/        Python CLI
AGENTS.example.md       Agent governance template
docs/WORKFLOW.md        Workflow and handoff protocol
templates/TASK.md       Human-readable task template
examples/               Example task briefs
tests/                  Unit tests
```

## Design goals

- no service or database required;
- plain files that work with Git;
- low ceremony and low token overhead;
- human-readable state;
- compatible with existing project instructions;
- safe defaults without turning every action into an approval checkpoint.

## Non-goals

Antigravity is not an autonomous deployment platform, secret manager, permission system, or replacement for CI/CD. It is a governance and coordination layer for coding-agent work.

## Contributing

Issues and pull requests are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for notable project changes.

## License

MIT. See [`LICENSE`](LICENSE).

> Antigravity is an independent open-source project and is not affiliated with or endorsed by OpenAI.
