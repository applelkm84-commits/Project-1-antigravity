# Assumption freshness and blast-radius guard

Antigravity 0.5 adds a local guard layer for two common failures in agentic development:

1. a fact that was true when work started quietly becomes stale;
2. a small task expands into changes across files nobody intended to touch.

The companion command is:

```bash
antigravity-guard
```

It uses local task state and local Git only. It does not call a network service.

## Expiring assumptions

Decisions describe choices. Assumptions describe facts the work currently relies on, and facts can become stale.

```bash
antigravity-guard assume <task-id> vendor-api supports-v2 \
  --source "vendor docs checked 2026-09-17" \
  --ttl-minutes 1440
```

Assumptions are keyed. The newest value for a key is authoritative; if that newest value expires, Antigravity reports the key as expired instead of silently falling back to an older value.

This is useful for things such as:

- current API capabilities;
- schema versions;
- temporary feature flags;
- external service limits;
- current pricing / quota assumptions;
- facts copied from documentation that may change.

## Protected invariants

Some truths should survive every handoff even when implementation details change:

```bash
antigravity-guard invariant <task-id> "Public API remains backward-compatible"
antigravity-guard invariant <task-id> "Never modify production credentials"
```

Invariants are durable context, not test assertions. They tell later agents which properties must not be traded away to make implementation easier.

## Change policy

Declare where the task is expected to make changes and how large the change should be:

```bash
antigravity-guard policy <task-id> \
  --allow "src/**" \
  --allow "tests/**" \
  --protect "config/prod/**" \
  --max-files 8 \
  --max-lines 300
```

- `--allow` is repeatable. When at least one allowed pattern exists, changed files outside those patterns are reported.
- `--protect` is repeatable and always reports a violation when matched.
- `--max-files` limits the number of changed files.
- `--max-lines` limits additions + deletions reported by Git, plus lines in new untracked text files.

The policy is intentionally a **review signal**, not a filesystem permission boundary.

## Audit the actual local blast radius

```bash
antigravity-guard audit <task-id>
```

The audit compares the working tree against `HEAD`, includes untracked files, and ignores `.antigravity/` state so recording an audit does not create its own violation.

You can compare against another Git ref:

```bash
antigravity-guard audit <task-id> --base origin/main
```

Example failure:

```text
clean=no
changed_files=11
changed_lines=487
violations=outside_scope:docs/migration.md, protected_path:config/prod/settings.yml, max_files:11>8, max_lines:487>300
```

The command exits non-zero when violations exist, which makes it usable in local scripts or CI without making Antigravity itself execute or approve code changes.

Use `--json` for machine-readable output or `--no-record` when you do not want the report appended to task history.

## Expired assumptions participate in audits

An otherwise in-scope diff is still reported non-clean if the task relies on an expired latest assumption:

```text
violations=expired_assumption:vendor-api
```

This is deliberate. The code may still compile, but the reason for the implementation may no longer be trustworthy.

## Guard context for agents

Generate a compact context block:

```bash
antigravity-guard packet <task-id>
```

It contains active assumptions with source/expiry, expired assumptions, invariants, and the change policy. Give this packet to a Builder or Reviewer alongside the normal Antigravity task or coordination prompt.

## Security boundary

The guard does not prevent a process from writing a file. It reports when observed Git changes violate the declared task policy. Protected paths and budgets are governance signals, not operating-system access control.

Git is invoked with an argument list and `shell=False`; Antigravity does not interpolate paths or refs into a shell command string.
