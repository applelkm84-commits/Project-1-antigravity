# Antigravity

A lightweight, file-based multi-agent workflow for Codex and other coding agents.

Antigravity gives a repository a small operating system for agentic work: clear roles, explicit handoffs, approval gates, durable task state, and a repeatable definition of done. It is designed for solo builders and small teams that want stronger agent autonomy without a heavy orchestration server.

## Why

Agent workflows often fail for predictable reasons:

- every task starts from zero context;
- planning, implementation, review, and release get mixed together;
- agents ask for unnecessary confirmations;
- important constraints disappear between turns;
- token usage grows because the same context is repeated;
- there is no durable record of what is done, blocked, or approved.

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
antigravity task "Add a responsive pricing section"
```

`antigravity init` creates:

```text
AGENTS.md
.antigravity/
  state.json
  tasks/
```

A task command creates a durable task brief containing objective, constraints, acceptance criteria, plan, handoffs, and completion state.

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

### Inspect state

```bash
antigravity status
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

## License

MIT. See [`LICENSE`](LICENSE).

> Antigravity is an independent open-source project and is not affiliated with or endorsed by OpenAI.
