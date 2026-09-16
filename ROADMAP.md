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
- [ ] Task dependency metadata

## 0.3 — Portable integrations
- [ ] Optional Codex CLI helper commands
- [ ] GitHub issue/PR adapters without changing the local-first core
- [ ] Import/export for task briefs

## Principles
Roadmap items must preserve Antigravity's local-first, low-dependency design. Networked integrations should remain optional and must never require users to expose private prompts, source code, or credentials to the core CLI.
