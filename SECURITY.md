# Security Policy

## Supported versions

The latest release on the default branch is supported during the alpha stage.

## Reporting a vulnerability

Please do not publish secrets, exploit details, or sensitive user data in a public issue. Open a minimal issue stating that you have a security report and request a private contact path from the maintainer.

Useful reports include the affected version, reproduction conditions, impact, and a proposed mitigation when available.

## Security principles

Antigravity is designed to remain local and file-based. The core CLI should not require network access, collect telemetry, execute generated shell commands, or read credentials. Changes that alter these properties require explicit documentation and review.

## Failure memory is operational context, not a risk oracle

`antigravity-memory` stores project-level near-misses in `.antigravity/memory.json` and task-level evidence/rollback state in the normal Antigravity task state.

- near-miss matching is deterministic path/component/risk overlap; it does not infer semantic similarity or calculate a statistical probability of failure;
- component-risk scores prioritize review attention only and must not be treated as actuarial, security, or reliability probabilities;
- evidence-lineage links show which recorded evidence currently resolves for a criterion, but they do not prove that the criterion itself is sufficient or correctly written;
- failed checks and expired assumptions do not count as valid supporting evidence;
- changed criterion text does not silently inherit evidence linked to the previous wording;
- rollback rehearsal is planning only and never executes rollback commands;
- counterfactual promotion records a human/agent finding as durable project state, so the finding should be reviewed before promotion;
- `.antigravity/memory.json` can contain operational details, paths, incidents, mitigations, and evidence. Review it before publishing or sharing a repository if those details are sensitive.

Do not put credentials, customer secrets, production tokens, or sensitive incident payloads into near-miss evidence or rollback notes.

## Release proof is evidence, not a certificate

`antigravity-proof` aggregates existing local state and Git evidence into review artifacts. A green proof does not certify that code is correct, secure, authorized, or safe to deploy.

- proof digests are hashes for change detection, not signatures or identity proofs;
- verification freshness detects recorded/contextual drift and later local-file changes that Antigravity can observe, but cannot prove no unseen environment change occurred;
- counterfactual prompts propose hypotheses and required observations; they must not invent results;
- reproduction recipes intentionally omit assumption values and redact common credential/token patterns, but redaction is defense in depth rather than a general-purpose secret scanner;
- proof JSON/Markdown may still contain project-sensitive non-secret metadata, paths, issue references, decisions, or notes, so review artifacts should be shared according to the repository's own disclosure rules;
- release readiness is a governance signal and never bypasses provider, organizational, repository, or human approval requirements.

Keep credentials out of task descriptions, comments, Git history, verification notes, and assumption values whenever possible instead of depending on downstream redaction.

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
