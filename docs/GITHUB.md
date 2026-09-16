# GitHub adapter

Antigravity's core remains local and network-free. GitHub support is an **opt-in companion command** that delegates network access and authentication to an existing GitHub CLI (`gh`) installation.

## Requirements

Install and authenticate GitHub CLI first:

```bash
gh auth status
```

Antigravity does not read GitHub tokens, passwords, credential files, or environment secrets. It invokes `gh` with an argument list and never uses a shell string.

## Import an issue

```bash
antigravity-github import-issue owner/repo 42
```

This reads the issue with `gh issue view`, creates a normal local Antigravity task, and records source metadata including:

- repository and issue number;
- canonical issue URL;
- labels;
- original issue body.

The imported task remains a local file under `.antigravity/tasks/`. No branch, commit, pull request, or issue is modified by this command.

## Generate a PR handoff

```bash
antigravity-github pr-handoff <task-id>
antigravity-github pr-handoff <task-id> --output pr-body.md
```

The handoff summarizes the task objective, source issue, readiness, acceptance criteria, review findings, verification evidence, and completion notes. It is intentionally **not** posted automatically. Review the generated text before using it as a pull request description.

## Failure behavior

The adapter fails without changing local state when:

- `gh` is missing;
- GitHub CLI authentication or authorization fails;
- the GitHub API request fails;
- GitHub CLI returns malformed JSON.

The adapter does not auto-push, create branches, open pull requests, merge changes, or run arbitrary shell commands.
