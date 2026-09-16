# Antigravity

A lightweight, Git-native operating layer for Codex and other coding agents.

Antigravity keeps the parts of agentic work that usually disappear between chats in durable repository files: task state, decisions, approvals, leases, dependencies, verification evidence, assumptions, protected invariants, scope budgets, release proof, and compact handoffs.

It is designed for solo builders and small teams that want stronger agent autonomy **without** a hosted orchestration server.

## Why

Coding agents often fail in ways that ordinary task lists and CI do not capture:

- every new session starts from incomplete context;
- agents re-ask for approvals that were already granted;
- two agents can unknowingly work the same task at once;
- a settled decision gets reopened because it lived only in chat;
- a green test survives even though requirements or assumptions changed afterwards;
- external facts quietly expire;
- a small fix grows into a broad refactor while tests still pass;
- reviewers see a confident summary but cannot reconstruct the evidence behind it;
- reproduction notes accidentally carry secrets or credentials.

Antigravity treats the repository as the coordination and evidence layer so humans and agents can inspect the same source of truth.

## Core roles

1. **Orchestrator** — owns decomposition, routing, and completion.
2. **Researcher** — resolves only material unknowns and records evidence.
3. **Builder** — implements the smallest safe change set.
4. **Reviewer** — checks correctness, regressions, security, and instruction compliance.
5. **Finisher** — checks actual evidence, updates docs, and prepares the handoff/release state.

## Quick start

```bash
python -m pip install -e .
antigravity init
antigravity task "Fix mobile navigation overlap" \
  --constraint "Do not change desktop navigation" \
  --accept "No overlap at 320px width" \
  --accept "Existing tests pass"
```

`antigravity init` creates:

```text
AGENTS.md
.antigravity/
  state.json
  tasks/
```

## Core task commands

```bash
antigravity task "Build adapter"
antigravity status
antigravity review <task-id> "Add a regression check" --severity warning --path src/adapter.py
antigravity verify <task-id> "pytest -q" --result passed --note "24 tests passed"
antigravity complete <task-id> --note "Acceptance criteria verified"
```

Antigravity records verification evidence; it does **not** pretend a suggested command ran.

### Dependency-aware readiness

```bash
antigravity task "Build GitHub adapter" \
  --depends-on 20260917-010000-define-schema \
  --depends-on 20260917-011500-auth-boundary
```

`status` reports `ready`, incomplete blockers, missing dependency IDs, and dependency cycles.

### Portable task bundles

```bash
antigravity export-task <task-id> --output task.bundle.json
antigravity --root ../another-repo import-task task.bundle.json
```

Imports rewrite paths safely under `.antigravity/tasks/` and reject duplicate IDs, unsafe task IDs, and unsupported bundle schemas.

### Codex-ready prompts

```bash
antigravity codex-prompt <task-id> --role builder
antigravity codex-prompt <task-id> --role reviewer --output reviewer-prompt.md
```

Prompts carry only durable task context and a compact handoff contract instead of replaying an entire conversation. The helper does not invoke Codex or require credentials.

## Optional GitHub handoffs

GitHub support stays outside the network-free core and uses an already authenticated `gh` CLI:

```bash
gh auth status
antigravity-github import-issue owner/repo 42
antigravity-github pr-handoff <task-id> --output pr-body.md
```

`import-issue` creates a normal local task with source metadata. `pr-handoff` prepares a reviewable PR description but does not push, open, or merge a pull request.

See [`docs/GITHUB.md`](docs/GITHUB.md).

## Coordination receipts

`antigravity-coord` makes decisions and approvals survive chat/session boundaries.

### Settled decisions

```bash
antigravity-coord decide <task-id> database sqlite --reason "Single-user local state"
```

The newest value for a decision key is active while history remains available.

### Exact-scope approvals

```bash
antigravity-coord approve <task-id> "edit source files" --by maintainer
antigravity-coord approve <task-id> "publish release" --by maintainer --ttl-minutes 60
```

Receipts prevent low-value re-confirmation but authorize only the exact recorded scope. They can expire or be revoked.

### Expiring task leases

```bash
antigravity-coord claim <task-id> --owner builder-a --ttl-minutes 30
antigravity-coord release <task-id> --owner builder-a
```

A second agent can see that another owner is already working the task instead of racing them unknowingly.

### Context freshness and reality checks

```bash
FINGERPRINT=$(antigravity-coord fingerprint <task-id>)
antigravity-coord check-context <task-id> "$FINGERPRINT"
antigravity-coord reality <task-id>
antigravity-coord prompt <task-id> --role reviewer
```

The reality report separates actual blockers from evidence debt. Context fingerprints make stale task snapshots detectable before high-impact work.

See [`docs/COORDINATION.md`](docs/COORDINATION.md).

## Guard layer: assumptions and blast radius

`antigravity-guard` catches two failures tests often miss: a premise went stale, or the implementation changed far more than the task intended.

### Expiring assumptions

```bash
antigravity-guard assume <task-id> vendor-api supports-v2 \
  --source "vendor docs checked 2026-09-17" \
  --ttl-minutes 1440
```

If the newest value expires, Antigravity reports it as expired instead of silently falling back to an older claim.

### Protected invariants

```bash
antigravity-guard invariant <task-id> "Public API remains backward-compatible"
antigravity-guard invariant <task-id> "Never modify production credentials"
```

### Change policy and local Git audit

```bash
antigravity-guard policy <task-id> \
  --allow "src/**" \
  --allow "tests/**" \
  --protect "config/prod/**" \
  --max-files 8 \
  --max-lines 300

antigravity-guard audit <task-id>
antigravity-guard audit <task-id> --base origin/main --json
```

The audit includes tracked and untracked local changes, ignores `.antigravity/` state, and fails non-zero on protected-path edits, out-of-scope files, budget overruns, or expired latest assumptions.

See [`docs/GUARD.md`](docs/GUARD.md).

## Release proof: challenge apparently-green work

Version 0.6 adds `antigravity-proof`, an evidence layer for review and release decisions.

### Build one proof artifact

```bash
antigravity-proof bundle <task-id>

antigravity-proof bundle <task-id> \
  --json-out .antigravity/proofs/release.json \
  --markdown-out .antigravity/proofs/release.md
```

The proof snapshots:

- objective and acceptance criteria;
- dependency readiness;
- settled decisions and active approval receipts;
- lease state/history;
- active/expired assumptions and invariants;
- latest verification result for each named check;
- evidence age and stale-evidence signals;
- current blast-radius audit;
- reality-check blockers/evidence debt;
- Git HEAD, coordination fingerprint, and a deterministic proof digest.

A non-ready proof exits non-zero. The artifact still explains exactly why it is not ready.

### Counterfactual reviewer

```bash
antigravity-proof counterfactual <task-id>
antigravity-proof counterfactual <task-id> --output counterfactual-review.md
```

This prompt deliberately assumes the current green checks are truthful, then asks a reviewer to find ways the release could **still** fail: false-green tests, missing negative cases, wrong assumptions, security boundaries, rollback/migration risk, scope drift, and stale coordination.

Instead of another confidence summary, it requires **falsifiable hypotheses** and the cheapest test that could disprove each one.

### Redacted reproduction recipe

```bash
antigravity-proof repro <task-id>
antigravity-proof repro <task-id> --json --output repro.json
```

The recipe carries changed paths, non-secret assumption names/sources, invariants, acceptance criteria, Git HEAD, and recorded verification command names. It omits assumption values and redacts common credential/token patterns and secret-bearing assignments.

See [`docs/RELEASE_PROOF.md`](docs/RELEASE_PROOF.md).

## A practical end-to-end flow

```text
GitHub issue / human request
          ↓
Antigravity task + dependencies
          ↓
Decisions + exact approval receipts
          ↓
Task lease
          ↓
Assumptions + invariants + change budget
          ↓
Builder / Codex prompt
          ↓
Recorded verification + independent review
          ↓
Reality check + blast-radius audit
          ↓
Release proof
          ↓
Counterfactual review
          ↓
Human/release system decides whether to ship
```

## Repository structure

```text
src/antigravity/
  cli.py                 Core local task workflow
  github_adapter.py      Opt-in gh-backed GitHub bridge
  coordination.py        Decisions, approvals, leases, freshness, reality checks
  guard.py               Assumption TTLs, invariants, Git blast-radius audits
  proof.py               Release proofs, counterfactual prompts, repro recipes

docs/
  WORKFLOW.md
  GITHUB.md
  COORDINATION.md
  GUARD.md
  RELEASE_PROOF.md
AGENTS.example.md
templates/
examples/
tests/
```

## Design goals

- no service or database required;
- plain files that work with Git;
- low ceremony and low token overhead;
- human-readable state plus machine-readable evidence;
- compatible with existing project instructions;
- safe defaults without turning every action into an approval checkpoint;
- network integrations remain explicit and optional;
- coordination state survives chat/session boundaries;
- stale evidence, stale facts, and scope creep become visible before release;
- reviewers can challenge green evidence rather than simply trusting it.

## Non-goals

Antigravity is not a secret manager, operating-system permission system, autonomous deployment platform, or replacement for CI/CD. Approval receipts, leases, protected paths, proof bundles, and change budgets are governance/evidence mechanisms, not security boundaries or correctness guarantees.

## Contributing

Issues and pull requests are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).

## License

MIT. See [`LICENSE`](LICENSE).

> Antigravity is an independent open-source project and is not affiliated with or endorsed by OpenAI.
