# Workflow

Antigravity is intentionally small. The repository is the coordination layer; task files are the durable memory; Git remains the audit trail.

## Lifecycle

### 1. Intake
The Orchestrator converts a request into an objective, constraints, acceptance criteria, and optional prerequisite task IDs. It does not ask for confirmation when the request is already clear.

### 2. Resolve material unknowns
Route to the Researcher only when an unknown can change implementation. Research should end with a compact evidence record and a recommendation for the next action.

### 3. Check readiness
A planned task with no incomplete prerequisites is `ready`. A task is blocked when a referenced prerequisite is incomplete, missing, or part of a dependency cycle.

Create dependencies with repeatable `--depends-on` arguments:

```bash
antigravity task "Build adapter" --depends-on <task-id>
```

`antigravity status` reports:

- `ready` when all known prerequisites are complete;
- `blocked=<task-id>` when a prerequisite is incomplete;
- `blocked=missing:<task-id>` when the referenced task does not exist;
- `blocked=cycle` when the task participates in a dependency cycle.

Dependencies are advisory workflow metadata. Antigravity does not schedule tasks or automatically execute blocked work.

### 4. Implement
The Builder makes the smallest safe change set. Unrelated cleanup should be deferred unless it is required for correctness.

### 5. Review
The Reviewer checks the implementation independently. Review should focus on concrete failures, regressions, security issues, missing tests, or instruction violations rather than stylistic churn.

### 6. Verify
Run the relevant checks outside Antigravity, then record what actually happened:

```bash
pytest -q
antigravity verify <task-id> "pytest -q" --result passed --note "12 tests passed"
```

Antigravity never executes the check itself. A verification record stores the check name, `passed` / `failed` / `skipped` result, timestamp, and optional note in machine-readable task state and mirrors it into the task Markdown.

This separation prevents an agent from confusing a proposed command with a command that was actually run.

### 7. Finish
The Finisher updates documentation, records completion notes, checks the recorded verification evidence, and marks the task complete.

## Portable task handoffs
When a task needs to move between repositories or teams, export a task bundle rather than copying disconnected snippets:

```bash
antigravity export-task <task-id> --output task.bundle.json
antigravity --root ../destination import-task task.bundle.json
```

A version-1 bundle contains the machine-readable task state plus the complete human-readable Markdown task brief. Import preserves reviews, verification evidence, dependencies, status, and timestamps.

For safety, import does not trust the task path stored in the bundle. It validates the task ID and always rewrites the destination under `.antigravity/tasks/<task-id>.md`. Duplicate task IDs and unsupported bundle schema versions fail clearly rather than overwriting local state.

Bundles are plain JSON and do not trigger network access or execute commands.

## When to ask a human
Ask only when at least one of these is true:

- a decision is irreversible or externally visible and approval was not already granted;
- credentials, secrets, money, production data, or destructive actions are involved;
- two plausible interpretations would produce materially different outcomes;
- a required fact cannot be discovered safely from available sources;
- policy, legal, or contractual constraints require human authorization.

Otherwise choose a reversible default, record it, and continue.

## Compact handoff protocol
A handoff should fit in a short block:

```text
Result: <decision or completed work>
Evidence/changes: <facts, files, tests>
Risk/blocker: <only if present>
Next: <next action + role>
```

This prevents token-heavy transcript replay.

## Verification records
Verification records answer a narrow question: **what check was actually performed, and what was the result?**

Example state fragment:

```json
{
  "verifications": [
    {
      "check": "pytest -q",
      "result": "passed",
      "created_at": "2026-09-17T00:00:00+00:00",
      "note": "12 tests passed"
    }
  ]
}
```

Use `failed` for a check that ran and failed, and `skipped` when a planned check was intentionally not performed. Do not record `passed` for a command that was only suggested or assumed.

## Failure handling

1. Record the failed check or blocker exactly.
2. Decide whether the same role can resolve it without new information.
3. Retry only when the new attempt changes an input, hypothesis, or implementation.
4. Escalate to the human only when a material decision or unavailable input is required.

## Definition of done
Completion requires evidence, not a claim. Record the tests or checks actually executed, any unresolved limitations, and whether documentation changed.
