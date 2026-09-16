# Workflow

Antigravity is intentionally small. The repository is the coordination layer; task files are the durable memory; Git remains the audit trail.

## Lifecycle

### 1. Intake
The Orchestrator converts a request into an objective, constraints, and acceptance criteria. It does not ask for confirmation when the request is already clear.

### 2. Resolve material unknowns
Route to the Researcher only when an unknown can change implementation. Research should end with a compact evidence record and a recommendation for the next action.

### 3. Implement
The Builder makes the smallest safe change set. Unrelated cleanup should be deferred unless it is required for correctness.

### 4. Review
The Reviewer checks the implementation independently. Review should focus on concrete failures, regressions, security issues, missing tests, or instruction violations rather than stylistic churn.

### 5. Finish
The Finisher runs the relevant checks, updates documentation, records completion notes, and marks the task complete.

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

## Failure handling

1. Record the failed check or blocker exactly.
2. Decide whether the same role can resolve it without new information.
3. Retry only when the new attempt changes an input, hypothesis, or implementation.
4. Escalate to the human only when a material decision or unavailable input is required.

## Definition of done
Completion requires evidence, not a claim. Record the tests or checks actually executed, any unresolved limitations, and whether documentation changed.
