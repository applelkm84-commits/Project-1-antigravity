# Changelog

All notable changes to Antigravity are documented here.

## 0.7.0 — 2026-09-17

### Added
- local `antigravity-memory` companion command;
- project-level `.antigravity/memory.json` near-miss ledger with paths, components, risk tags, evidence, and mitigation;
- deterministic prior-near-miss recall using path, component, and risk overlap without embeddings or model/API calls;
- acceptance-criterion evidence lineage linking requirements to checks, decisions, assumptions, invariants, or observations;
- explicit unsupported-criterion and orphaned-lineage reporting when evidence is absent, invalid, expired, failed, or attached to changed criterion text;
- deterministic component/path risk memory combining prior near-misses, failed latest checks, and related guard violations;
- rollback rehearsal records and packets covering state restoration, irreversible side effects, migration/downgrade concerns, post-rollback verification, and containment;
- promotion of counterfactual findings into durable invariants, expiring assumptions, verification templates, or near-miss records;
- dedicated memory/rollback documentation and regression tests.

### Design guarantees
- failure-memory matching is deterministic and local; risk scores prioritize review attention and are not statistical failure probabilities;
- criterion evidence resolves against current recorded state, so failed checks and expired assumptions do not silently support requirements;
- changed acceptance-criterion wording does not inherit old evidence automatically;
- rollback rehearsal is planning only and never executes rollback commands;
- the memory layer adds no network/runtime dependency.

## 0.6.0 — 2026-09-17

### Added
- `antigravity-proof bundle` release-evidence snapshots in Markdown and JSON;
- proof snapshots covering objective, dependency readiness, decisions, approvals, lease history, assumptions, invariants, latest verification evidence, blast-radius audit, reality check, Git HEAD, and coordination fingerprint;
- deterministic SHA-256 proof digests over the evidence snapshot;
- verification evidence ages and conservative stale-evidence detection after relevant task/context changes or later local file modification;
- non-ready proof exit status when blockers, evidence debt, stale checks, non-passing latest checks, or guard violations exist;
- `antigravity-proof counterfactual` prompts that search for falsifiable failure modes even when recorded checks are green;
- `antigravity-proof repro` minimal reproduction recipes in Markdown/JSON;
- secret-aware recipe redaction for common token/credential formats and secret-bearing assignments;
- dedicated release-proof documentation and regression tests.

### Design guarantees
- a release proof is an evidence artifact, not an authorization or correctness certificate;
- counterfactual review does not invent test results and explicitly attacks false-green, negative-case, assumption, security, rollback, scope, and stale-coordination blind spots;
- reproduction recipes omit assumption values and redact known secret-like material rather than copying task state wholesale;
- proof generation remains local-first and adds no network/runtime dependency.

## 0.5.0 — 2026-09-17

### Added
- local `antigravity-guard` companion command;
- keyed assumptions with optional source/evidence metadata and TTL;
- explicit expired-assumption reporting without silently falling back to older values;
- protected invariants that survive agent handoffs;
- per-task change policy with allowed path globs, protected path globs, maximum changed files, and maximum changed lines;
- local Git blast-radius audit covering tracked and untracked changes while ignoring `.antigravity/` state;
- non-zero audit exit when protected paths, out-of-scope files, change budgets, or latest-assumption freshness are violated;
- machine-readable JSON reports and compact guard packets for Builders / Reviewers;
- temporary-real-Git-repository tests for clean and violating diffs.

### Design guarantees
- the guard uses local Git only and adds no network/runtime dependency;
- Git commands use argument lists with `shell=False`;
- change policies and protected paths are governance/audit signals rather than filesystem permissions;
- stale assumptions can fail an audit even when the code diff itself is in scope, because implementation evidence is not trustworthy if its external premise expired.

## 0.4.0 — 2026-09-17

### Added
- local `antigravity-coord` companion command for multi-agent coordination state;
- durable keyed decisions where the latest value for a key is active while prior choices remain in history;
- scoped approval receipts with approver, optional expiry, note, and explicit revocation;
- expiring task leases with collision refusal, refresh/reclaim behavior, release, and lease history;
- deterministic SHA-256 context fingerprints for stale-prompt detection;
- `check-context` non-zero stale detection before externally visible or irreversible work;
- `reality` reports that separate dependency/review/check blockers from missing verification evidence;
- latest-result semantics for repeated verification checks while preserving historical records;
- coordination-aware role prompts containing decisions, approvals, lease ownership, reality status, and the context fingerprint.

### Design guarantees
- decisions and approval receipts are coordination records, not operating-system authorization;
- exact approval scopes do not silently authorize broader actions;
- leases are expiring coordination signals rather than filesystem locks;
- coordination features remain local/file-based and add no network or runtime dependency;
- stale-context checks detect task-state drift instead of relying on an agent's confidence or chat history.

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
