# Security Policy

## Supported versions

The latest release on the default branch is supported during the alpha stage.

## Reporting a vulnerability

Please do not publish secrets, exploit details, or sensitive user data in a public issue. Open a minimal issue stating that you have a security report and request a private contact path from the maintainer.

Useful reports include the affected version, reproduction conditions, impact, and a proposed mitigation when available.

## Security principles

Antigravity is designed to remain local and file-based. The core CLI should not require network access, collect telemetry, execute generated shell commands, or read credentials. Changes that alter these properties require explicit documentation and review.
