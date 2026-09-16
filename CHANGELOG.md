# Changelog

All notable changes to Antigravity are documented here.

## 0.3.0 — 2026-09-17

### Added
- portable JSON task bundles with `antigravity export-task` and `antigravity import-task`;
- task bundle round-trip support for machine-readable task state and human-readable Markdown;
- safety checks for duplicate task IDs, unsupported bundle schemas, and unsafe imported task IDs;
- safe import path rewriting under `.antigravity/tasks/` instead of trusting paths from imported bundles;
- compact role-specific Codex-ready prompts with `antigravity codex-prompt`;
- prompt roles for orchestrator, researcher, builder, reviewer, and finisher;
- optional prompt file output without invoking Codex, requiring credentials, or adding network dependencies;
- opt-in `antigravity-github` integration backed by an existing authenticated `gh` CLI;
- GitHub issue import with source URL, number, labels, and original issue body;
- local PR handoff generation from Antigravity task state without auto-pushing or auto-merging.

### Security
- GitHub integration uses argument-list subprocess execution with `shell=False`;
- Antigravity does not read GitHub tokens or credential files;
- imported remote issue content is treated as untrusted text and does not override repository policy.

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
