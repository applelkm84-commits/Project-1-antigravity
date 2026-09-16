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
- [ ] Durable decisions so agents do not reopen settled choices
- [ ] Scoped approval receipts so already-approved actions are not repeatedly re-confirmed
- [ ] Expiring task leases to reduce concurrent-agent collisions
- [ ] Context fingerprints to detect stale prompts after task state changes
- [ ] Reality check for evidence debt before finishing a task

## Principles
Roadmap items must preserve Antigravity's local-first, low-dependency design. Networked integrations should remain optional and must never require users to expose private prompts, source code, or credentials to the core CLI.
