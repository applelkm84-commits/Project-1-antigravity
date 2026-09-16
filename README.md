# Antigravity

A lightweight, file-based multi-agent workflow for Codex and other coding agents.

Antigravity gives a repository a small operating system for agentic work: clear roles, explicit handoffs, durable task state, dependency-aware readiness, verification evidence, portable task bundles, compact role-specific prompts, opt-in GitHub handoffs, coordination receipts, expiring assumptions, protected invariants, and local Git blast-radius audits.

## Why

Agent workflows often fail for predictable reasons:

- every task starts from zero context;
- planning, implementation, review, and release get mixed together;
- agents ask for approvals that were already given in another conversation;
- two agents can unknowingly work the same task at once;
- important decisions disappear between turns;
- a prompt can remain syntactically valid after the underlying task state has changed;
- an external fact can quietly expire while the implementation still assumes it is current;
- a small fix can silently grow into a broad refactor touching protected files;
- there is no durable record of what is done, blocked, approved, assumed, in-scope, or actually verified.

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

### Record a verification result

Antigravity records evidence but does **not** execute the command for you:

```bash
pytest -q
antigravity verify <task-id> "pytest -q" \
  --result passed \
  --note "12 tests passed"
```

### Export and import a task brief

```bash
antigravity export-task <task-id> --output task.bundle.json
antigravity --root ../another-repo import-task task.bundle.json
```

Imports reject unsupported bundle schemas, duplicate task IDs, and unsafe IDs that could escape `.antigravity/tasks/`.

### Generate a Codex-ready prompt

```bash
antigravity codex-prompt <task-id> --role builder
antigravity codex-prompt <task-id> --role reviewer --output reviewer-prompt.md
```

The command does not invoke Codex, require credentials, or add a network dependency.

### Optional GitHub issue / PR handoffs

The core remains network-free. GitHub support is provided by a separate opt-in command that uses an already authenticated GitHub CLI (`gh`):

```bash
gh auth status
antigravity-github import-issue owner/repo 42
antigravity-github pr-handoff <task-id> --output pr-body.md
```

See [`docs/GITHUB.md`](docs/GITHUB.md) for the integration and security boundary.

## Coordination layer: receipts instead of repeated conversation

The `antigravity-coord` companion command keeps coordination facts durable without turning Antigravity into a server or permissions system.

### Record settled decisions

```bash
antigravity-coord decide <task-id> database sqlite \
  --reason "Single-user local state"
```

### Record exact approval scopes

```bash
antigravity-coord approve <task-id> "edit source files" --by maintainer
antigravity-coord approve <task-id> "publish release" \
  --by maintainer --ttl-minutes 60
```

Approval receipts exist to prevent low-value re-confirmation. They authorize only the exact recorded scope and can expire or be revoked.

### Prevent agent collisions with expiring leases

```bash
antigravity-coord claim <task-id> --owner builder-a --ttl-minutes 30
antigravity-coord release <task-id> --owner builder-a
```

### Detect stale agent context

```bash
FINGERPRINT=$(antigravity-coord fingerprint <task-id>)
antigravity-coord check-context <task-id> "$FINGERPRINT"
```

### Measure evidence debt before saying “done”

```bash
antigravity-coord reality <task-id>
antigravity-coord reality <task-id> --json
```

### Generate a coordination-aware prompt

```bash
antigravity-coord prompt <task-id> --role builder
```

See [`docs/COORDINATION.md`](docs/COORDINATION.md) for the full model and limitations.

## Guard layer: stale assumptions and scope creep

The `antigravity-guard` companion command makes two otherwise invisible risks explicit: **the facts behind a task may expire**, and **the actual diff may exceed the task's intended blast radius**.

### Record an assumption with evidence and TTL

```bash
antigravity-guard assume <task-id> vendor-api supports-v2 \
  --source "vendor docs checked 2026-09-17" \
  --ttl-minutes 1440
```

The newest value for a key is the current assumption. If that value expires, Antigravity reports it as expired instead of silently falling back to an older value.

### Preserve invariants across agent handoffs

```bash
antigravity-guard invariant <task-id> "Public API remains backward-compatible"
antigravity-guard invariant <task-id> "Never modify production credentials"
```

### Declare the expected blast radius

```bash
antigravity-guard policy <task-id> \
  --allow "src/**" \
  --allow "tests/**" \
  --protect "config/prod/**" \
  --max-files 8 \
  --max-lines 300
```

### Audit the real local Git diff

```bash
antigravity-guard audit <task-id>
antigravity-guard audit <task-id> --base origin/main --json
```

The audit includes tracked and untracked local changes, ignores `.antigravity/` state, and fails non-zero when it finds protected-path edits, files outside the allowed patterns, file/line budget overruns, or an expired latest assumption.

This catches a class of failure that unit tests do not: the code may work, but the agent changed far more than the task authorized or relied on an external fact that is no longer fresh.

Generate a compact guard context for a Builder or Reviewer:

```bash
antigravity-guard packet <task-id>
```

See [`docs/GUARD.md`](docs/GUARD.md) for the audit model and limitations.

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
src/antigravity/          Core CLI + optional integration/coordination/guard modules
AGENTS.example.md         Agent governance template
docs/WORKFLOW.md          Workflow and handoff protocol
docs/GITHUB.md            Opt-in GitHub integration boundary
docs/COORDINATION.md      Decisions, approvals, leases, fingerprints, reality checks
docs/GUARD.md             Assumption freshness, invariants, and blast-radius audits
templates/TASK.md         Human-readable task template
examples/                 Example task briefs
tests/                    Unit tests
```

## Design goals

- no service or database required;
- plain files that work with Git;
- low ceremony and low token overhead;
- human-readable state;
- compatible with existing project instructions;
- safe defaults without turning every action into an approval checkpoint;
- network integrations remain explicit and optional;
- coordination state should survive chat/session boundaries;
- scope and evidence drift should be visible before review or release.

## Non-goals

Antigravity is not an autonomous deployment platform, secret manager, operating-system permission system, or replacement for CI/CD. Approval receipts, leases, protected paths, and change budgets are governance records and audit signals, not security boundaries.

## Contributing

Issues and pull requests are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for notable project changes.

## License

MIT. See [`LICENSE`](LICENSE).

> Antigravity is an independent open-source project and is not affiliated with or endorsed by OpenAI.
