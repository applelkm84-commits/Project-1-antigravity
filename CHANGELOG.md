# Changelog

All notable changes to Antigravity are documented here.

## 0.2.0 — 2026-09-17

### Added
- structured review findings with `antigravity review`;
- machine-readable verification evidence with `antigravity verify`;
- verification summaries in `antigravity status`;
- repeatable task dependencies with `--depends-on`;
- readiness reporting for incomplete, missing, and cyclic dependencies;
- backward-compatible handling for task state created before verification/dependency metadata;
- expanded tests and workflow documentation.

### Design guarantees
- Antigravity records verification results but does not execute verification commands;
- dependency metadata remains advisory and does not turn Antigravity into a scheduler;
- the core remains local-first and requires no service or database.

## 0.1.0 — 2026-09-16

### Added
- file-based task state and human-readable task briefs;
- repository `AGENTS.md` policy scaffold;
- task creation/completion commands;
- five-role workflow model;
- unit tests and GitHub Actions CI;
- security, contribution, roadmap, and workflow documentation.
