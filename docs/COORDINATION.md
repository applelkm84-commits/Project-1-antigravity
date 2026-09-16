# Coordination receipts

Antigravity 0.4 adds a local coordination layer for a failure mode that appears once more than one human or coding agent touches the same task: the code may be correct while the **coordination state is stale, duplicated, or contradictory**.

The companion command is:

```bash
antigravity-coord
```

It is file-based, has no network dependency, and stores its records inside normal Antigravity task state.

## 1. Durable keyed decisions

Record a settled choice once instead of making every later agent rediscover or debate it:

```bash
antigravity-coord decide <task-id> database sqlite \
  --reason "Single-user local state; no server required"
```

A later decision with the same key becomes the active value while the old record remains in history:

```bash
antigravity-coord decide <task-id> database postgres \
  --reason "Multi-user deployment is now required"
```

This is intentionally different from free-form notes. A key such as `database`, `api-shape`, or `release-strategy` gives later agents a stable fact to consume.

## 2. Scoped approval receipts

When a human has already approved a specific action, record that approval so another agent does not ask again simply because the conversation changed:

```bash
antigravity-coord approve <task-id> "edit source files" \
  --by maintainer

antigravity-coord approve <task-id> "publish release" \
  --by maintainer \
  --ttl-minutes 60 \
  --note "Valid for the reviewed 0.4 release only"
```

An approval authorizes only its exact recorded scope. It does not silently expand to a broader action.

Revoke an active scope when circumstances change:

```bash
antigravity-coord revoke <task-id> "publish release" --by maintainer
```

## 3. Expiring task leases

Two agents editing the same task at once can produce perfectly valid but mutually incompatible work. A short lease makes ownership visible without creating a server-side lock manager:

```bash
antigravity-coord claim <task-id> --owner builder-a --ttl-minutes 30
```

A different owner is refused while the lease is active. Expired leases can be reclaimed automatically, and lease history remains in the task state.

```bash
antigravity-coord release <task-id> --owner builder-a
```

Leases are coordination signals, not filesystem locks. They reduce accidental races while keeping recovery simple.

## 4. Context fingerprints

A prompt can become unsafe even if it was correct when generated. Another agent may have changed the task, recorded a failed verification, revoked approval, or changed a settled decision.

Capture the deterministic fingerprint:

```bash
antigravity-coord fingerprint <task-id>
```

Before an externally visible or irreversible action, compare the saved fingerprint with current task state:

```bash
antigravity-coord check-context <task-id> <fingerprint>
```

Output is `fresh` when the state is unchanged and `stale` with the new fingerprint when it changed. The command exits non-zero for stale context.

## 5. Reality check / evidence debt

Agent workflows often confuse "the implementation looks done" with "there is evidence that it is done." The reality report separates blockers from evidence debt:

```bash
antigravity-coord reality <task-id>
antigravity-coord reality <task-id> --json
```

The report checks:

- dependency readiness;
- recorded error-severity review findings;
- the **latest** result for each verification check;
- missing verification evidence;
- active lease ownership;
- active decision and approval counts;
- the current context fingerprint.

Example:

```text
finish_ready=no
readiness=ready
blockers=failed_check=pytest -q
evidence_debt=none
```

If a failed check is later rerun and recorded as passed, the latest result replaces the failure for reality-check purposes while the historical evidence remains in state.

## 6. Coordination-aware agent prompts

Generate a prompt that includes not only the task brief but the coordination state that normally gets lost between agents:

```bash
antigravity-coord prompt <task-id> --role builder
```

The packet includes:

- objective, constraints, and acceptance criteria;
- active keyed decisions;
- active approval receipts and expiry;
- current lease owner;
- review findings and verification evidence;
- reality-check blockers / evidence debt;
- deterministic context fingerprint;
- role-specific instructions and compact handoff format.

The generated packet tells an agent not to re-ask for an already approved exact scope, not to race another lease owner, and to refresh context if the fingerprint becomes stale.

## What these features do not do

Coordination receipts are not an authorization system or security boundary. They do not grant operating-system permissions, bypass provider confirmation requirements, execute commands, or replace human judgment for high-impact actions.

They make **what was decided, what was approved, who is working, what was verified, and whether context is stale** explicit and durable so humans and agents can coordinate with less repeated conversation and fewer silent assumptions.
