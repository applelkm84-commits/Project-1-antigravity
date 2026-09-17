# Failure Memory, Evidence Lineage, and Rollback Rehearsal

Antigravity 0.7 adds a local memory layer for failures that should not disappear when a task or pull request closes.

The goal is not to make an agent remember every conversation. It is to preserve only operationally useful facts: near-misses, evidence supporting acceptance criteria, repeated risk around components, rollback knowledge, and counterfactual findings worth promoting into durable controls.

## Project-level near-miss ledger

Near-misses are stored in `.antigravity/memory.json`, separate from any single task. This lets a later task discover a prior problem even when it belongs to a different issue or pull request.

```bash
antigravity-memory near-miss add <task-id> duplicate-charge \
  "Retry path could charge twice" \
  --path src/payments/api.py \
  --component payments \
  --risk idempotency \
  --evidence "staging replay" \
  --mitigation "persist idempotency keys"
```

A near-miss can carry affected paths, components, risk tags, evidence, and mitigation.

To make a current task easier to match, add explicit memory context:

```bash
antigravity-memory context <task-id> \
  --path src/payments/service.py \
  --component payments \
  --risk idempotency
```

Recall is deterministic and local. It scores path matches first, then component and risk overlap:

```bash
antigravity-memory near-miss relevant <task-id>
antigravity-memory near-miss relevant <task-id> --json
```

No model or embedding service is used for matching.

## Acceptance-criterion evidence lineage

A task can have tests without proving that every requirement is actually supported. The lineage layer links each acceptance criterion to concrete evidence.

Supported evidence types are:

- `check` — the latest recorded result for a verification check must be `passed`;
- `decision` — the keyed decision must currently exist;
- `assumption` — the latest assumption for the key must still be active, not expired;
- `invariant` — the invariant text must still be recorded;
- `observation` — a human/agent observation explicitly recorded as evidence.

Example:

```bash
antigravity-memory lineage link <task-id> 1 --type check --ref "pytest -q"
antigravity-memory lineage link <task-id> 2 --type decision --ref storage
antigravity-memory lineage report <task-id>
```

The report marks unsupported criteria explicitly and exits non-zero when one or more criteria lack valid current evidence. If the criterion text changes later, old links do not silently support the new requirement; they become orphaned lineage records.

## Component/path risk memory

`risk` looks for prior trouble related to the current task's paths/components. It combines:

- relevant near-misses;
- failed latest verification checks from related historical tasks;
- related guard violations such as protected-path or out-of-scope changes.

```bash
antigravity-memory risk <task-id>
antigravity-memory risk <task-id> --json
```

The output is deterministic and returns a cumulative score with `low`, `elevated`, `high`, or `critical` attention levels. The score is a review-priority signal, not a probability of failure.

## Rollback rehearsal

Rollback plans often remain an afterthought until an incident. Antigravity makes the minimum rollback questions explicit before release.

Record knowledge incrementally:

```bash
antigravity-memory rollback record <task-id> \
  --restore-state "previous application image" \
  --irreversible "emails already sent cannot be unsent" \
  --migration "confirm down migration is backward-compatible" \
  --verify "smoke test login and database reads" \
  --contain "disable write traffic during rollback"
```

Render a rehearsal packet:

```bash
antigravity-memory rollback packet <task-id>
antigravity-memory rollback packet <task-id> --json
antigravity-memory rollback packet <task-id> --output rollback.md
```

The packet always covers five sections:

1. state to restore;
2. irreversible side effects;
3. migration/downgrade concerns;
4. verification after rollback;
5. containment steps.

Missing sections are shown as `UNSPECIFIED` instead of being silently omitted.

## Promote counterfactual findings

The useful output of a skeptical review should survive the review session. `promote` turns a finding into a durable control.

### Invariant

```bash
antigravity-memory promote <task-id> \
  --finding "Never bypass payment signature validation" \
  --to invariant
```

### Assumption with TTL

```bash
antigravity-memory promote <task-id> \
  --finding "Provider retry behavior may change" \
  --to assumption \
  --key provider-retry \
  --value "retries at most 3 times" \
  --source "provider docs" \
  --ttl-minutes 1440
```

### Verification template

```bash
antigravity-memory promote <task-id> \
  --finding "Duplicate callback delivery is not covered" \
  --to verification-template \
  --check "simulate duplicate callback"
```

Verification templates are reminders/evidence requirements. They are not executed automatically.

### Near-miss record

```bash
antigravity-memory promote <task-id> \
  --finding "A duplicate webhook could create duplicate fulfillment" \
  --to near-miss \
  --failure-class duplicate-fulfillment \
  --path src/checkout/webhook.py \
  --risk idempotency \
  --mitigation "persist webhook event ids"
```

## Security and limitations

- The memory layer is local/file-based and adds no network dependency.
- Near-miss matching is deterministic; it does not infer semantic similarity beyond path/component/risk overlap.
- Risk scores prioritize review attention and must not be interpreted as statistical failure probabilities.
- An evidence link proves only that a particular recorded item currently resolves; it does not prove the criterion itself is correct or complete.
- Rollback rehearsal is planning, not execution. Antigravity never runs rollback commands.
- Project memory may contain operational details. Review `.antigravity/memory.json` before publishing a repository if those details are sensitive.
