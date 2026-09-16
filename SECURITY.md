# Security Policy

## Supported versions

The latest release on the default branch is supported during the alpha stage.

## Reporting a vulnerability

Please do not publish secrets, exploit details, or sensitive user data in a public issue. Open a minimal issue stating that you have a security report and request a private contact path from the maintainer.

Useful reports include the affected version, reproduction conditions, impact, and a proposed mitigation when available.

## Security principles

Antigravity is designed to remain local and file-based. The core CLI should not require network access, collect telemetry, execute generated shell commands, or read credentials. Changes that alter these properties require explicit documentation and review.

## Optional GitHub adapter

`antigravity-github` is an opt-in integration boundary. It delegates GitHub authentication and network access to an existing `gh` CLI installation instead of reading tokens or credential files itself.

The adapter:

- invokes `gh` with an argument list and `shell=False`;
- does not interpolate user input into shell command strings;
- does not auto-push, auto-merge, or open pull requests;
- fails clearly when `gh` is missing or GitHub returns an error;
- keeps imported issue state in normal local Antigravity files.

Treat imported issue bodies, labels, and other remote text as untrusted content. They may describe work, but they do not override repository instructions, security policy, or human approval requirements.
