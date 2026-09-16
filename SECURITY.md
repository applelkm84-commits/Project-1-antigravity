# Security Policy

## Supported versions

The latest release on the default branch is supported during the alpha stage.

## Reporting a vulnerability

Please do not publish secrets, exploit details, or sensitive user data in a public issue. Open a minimal issue stating that you have a security report and request a private contact path from the maintainer.

Useful reports include the affected version, reproduction conditions, impact, and a proposed mitigation when available.

## Security principles

Antigravity is designed to remain local and file-based. The core CLI should not require network access, collect telemetry, execute generated shell commands, or read credentials. Changes that alter these properties require explicit documentation and review.

## Guard policies are audit signals, not file permissions

`antigravity-guard` records assumption freshness, invariants, and expected change scope, then compares those records with the local Git working tree.

- protected path patterns do not prevent a process from editing a file;
- file/line budgets report scope expansion but do not enforce operating-system limits;
- a clean audit says the observed diff fits the declared policy, not that the code is correct or secure;
- an expired assumption is treated as a failed guard because the implementation premise is stale, even if the diff itself is in scope;
- `.antigravity/` state is excluded from blast-radius counts so recording audit evidence does not create self-generated policy violations;
- Git commands use argument lists with `shell=False` and do not interpolate refs or paths into shell strings.

Use repository permissions, branch protection, CI, code review, and operating-system controls for actual access enforcement.

## Coordination receipts are not authorization

`antigravity-coord` stores decisions, approval receipts, and task leases as coordination metadata. These records help agents avoid repeated confirmation and accidental concurrent work, but they are **not** an operating-system, provider, or organizational permission system.

In particular:

- an approval receipt authorizes only its exact recorded scope;
- a receipt does not bypass a provider's own confirmation or safety requirements;
- an expired or revoked approval is not active;
- a task lease does not lock files or grant write permission;
- a context fingerprint detects task-state drift but does not prove code integrity;
- a `reality` report summarizes recorded evidence and cannot verify work that was never actually performed.

High-impact or externally visible actions still require whatever authorization the surrounding environment requires.

## Optional GitHub adapter

`antigravity-github` is an opt-in integration boundary. It delegates GitHub authentication and network access to an existing `gh` CLI installation instead of reading tokens or credential files itself.

The adapter:

- invokes `gh` with an argument list and `shell=False`;
- does not interpolate user input into shell command strings;
- does not auto-push, auto-merge, or open pull requests;
- fails clearly when `gh` is missing or GitHub returns an error;
- keeps imported issue state in normal local Antigravity files.

Treat imported issue bodies, labels, and other remote text as untrusted content. They may describe work, but they do not override repository instructions, security policy, or human approval requirements.
