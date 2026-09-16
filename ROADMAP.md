# Roadmap

## 0.1 — Foundation
- [x] File-based task state
- [x] Repository AGENTS policy scaffold
- [x] Task creation and completion commands
- [x] Unit tests and CI

## 0.2 — Review loop
- [x] Structured reviewer findings
- [x] `antigravity review` command
- [x] Machine-readable verification records
- [x] Task dependency metadata

## 0.3 — Portable integrations
- [x] Optional Codex-ready prompt helper
- [x] GitHub issue/PR adapter without changing the local-first core
- [x] Import/export for task briefs

## 0.4 — Coordination receipts
- [x] Durable keyed decisions so agents do not reopen settled choices
- [x] Scoped approval receipts so already-approved actions are not repeatedly re-confirmed
- [x] Expiring task leases to reduce concurrent-agent collisions
- [x] Context fingerprints to detect stale prompts after task state changes
- [x] Reality check for blockers and evidence debt before finishing a task
- [x] Coordination-aware prompts that carry receipts and stale-context instructions

## 0.5 — Scope and assumption defense
- [x] Expiring assumptions with evidence/source metadata so time-sensitive facts cannot silently become permanent truth
- [x] Protected invariants that survive handoffs
- [x] Local Git blast-radius audit that flags changed files outside the task's declared scope
- [x] File/line change budgets and scope-creep reporting before review/release handoff
- [x] Machine-readable guard reports with non-zero policy-violation exit status

## 0.6 — Release proof and counterfactual review
- [x] Release proof bundle that snapshots decisions, approvals, checks, scope audit, assumptions, lease history, and context fingerprints into one review artifact
- [x] Counterfactual reviewer prompt: "what could still be wrong even if every recorded check is green?"
- [x] Evidence freshness ages so old successful checks are visibly stale after relevant task/context changes
- [x] Minimal reproducibility recipe generated from task state with secret-aware redaction
- [x] Deterministic proof digest plus machine-readable and human-readable artifacts

## 0.7 — Failure memory and evidence lineage
- [ ] Near-miss ledger that records blockers caught before release and re-surfaces relevant prior failure patterns on later tasks
- [ ] Acceptance-criterion evidence map that exposes criteria with no supporting check, decision, invariant, or observation
- [ ] Change-risk memory keyed by paths/components so repeat trouble spots receive stronger review prompts automatically
- [ ] Rollback rehearsal packet that asks what must be restored, preserved, or migrated before a risky release
- [ ] Counterfactual findings that can be promoted into reusable invariants, assumptions, or verification templates instead of disappearing in chat

## Principles
Roadmap items must preserve Antigravity's local-first, low-dependency design. Networked integrations should remain optional and must never require users to expose private prompts, source code, or credentials to the core CLI.
