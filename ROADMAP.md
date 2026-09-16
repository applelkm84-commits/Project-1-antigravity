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
- [ ] Expiring assumptions with evidence/source metadata so time-sensitive facts cannot silently become permanent truth
- [ ] Protected invariants that survive handoffs (for example: public API compatibility or "never touch production config")
- [ ] Local Git blast-radius audit that flags changed files outside the task's declared scope
- [ ] Change-budget / scope-creep report before review and release handoff

## Principles
Roadmap items must preserve Antigravity's local-first, low-dependency design. Networked integrations should remain optional and must never require users to expose private prompts, source code, or credentials to the core CLI.
