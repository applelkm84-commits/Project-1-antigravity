from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .cli import create_task, dependency_cycle_ids, find_task, load_state, markdown_section, readiness_label, save_state


def run_gh(args: list[str]) -> str:
    """Run an already-authenticated GitHub CLI command without invoking a shell."""
    if shutil.which("gh") is None:
        raise SystemExit("GitHub CLI 'gh' was not found. Install and authenticate gh first.")
    completed = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or f"exit code {completed.returncode}"
        raise SystemExit(f"GitHub CLI failed: {detail}")
    return completed.stdout


def import_issue(root: Path, repo: str, issue_number: int) -> Path:
    raw = run_gh(
        [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo,
            "--json",
            "number,title,body,url,labels",
        ]
    )
    try:
        issue = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"GitHub CLI returned invalid JSON: {exc}") from exc

    title = str(issue.get("title") or "").strip()
    url = str(issue.get("url") or "").strip()
    number = issue.get("number")
    if not title or not url or not isinstance(number, int):
        raise SystemExit("GitHub issue response is missing title, URL, or issue number")

    path = create_task(
        root,
        title,
        constraints=[f"Source issue: {url}"],
        acceptance=["Address the source issue without silently expanding scope"],
    )
    state = load_state(root)
    task = state["tasks"][-1]
    labels = [item.get("name") for item in issue.get("labels", []) if isinstance(item, dict) and item.get("name")]
    task["source"] = {
        "provider": "github",
        "type": "issue",
        "repo": repo,
        "number": number,
        "url": url,
        "labels": labels,
        "body": str(issue.get("body") or ""),
    }
    save_state(root, state)

    text = path.read_text(encoding="utf-8")
    source_block = (
        "## Source\n"
        f"- GitHub issue: {url}\n"
        f"- Repository: `{repo}`\n"
        f"- Issue: #{number}\n"
        f"- Labels: {', '.join(labels) if labels else 'None'}\n\n"
        "### Original issue body\n"
        f"{task['source']['body'] or 'No issue body provided.'}\n\n"
    )
    text = text.replace("## Plan\n", source_block + "## Plan\n", 1)
    path.write_text(text, encoding="utf-8")
    print(path)
    return path


def pr_handoff(root: Path, task_id: str, output: Path | None = None) -> str:
    state = load_state(root)
    task = find_task(state, task_id)
    task_path = root / task["path"]
    if not task_path.exists():
        raise SystemExit(f"Task Markdown is missing: {task['path']}")
    markdown = task_path.read_text(encoding="utf-8")
    task_by_id = {item.get("id"): item for item in state.get("tasks", []) if item.get("id")}
    readiness = readiness_label(task, task_by_id, dependency_cycle_ids(state.get("tasks", []))) or "complete"
    source = task.get("source") or {}
    source_line = source.get("url") if isinstance(source, dict) else None

    handoff = f"""## Summary
{markdown_section(markdown, 'Objective') or task.get('title', '')}

## Source
{source_line or 'No external source recorded.'}

## Task state
- Antigravity task: `{task_id}`
- Status: {task.get('status', 'planned')}
- Readiness: {readiness}

## Acceptance criteria
{markdown_section(markdown, 'Acceptance criteria') or '- None recorded'}

## Review findings
{markdown_section(markdown, 'Review findings') or 'None recorded.'}

## Verification evidence
{markdown_section(markdown, 'Verification records') or 'None recorded.'}

## Completion notes
{markdown_section(markdown, 'Completion notes') or 'Pending.'}

---
Generated locally by Antigravity. Review before using as a pull request description.
"""
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(handoff, encoding="utf-8")
        print(output)
    else:
        print(handoff, end="")
    return handoff


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="antigravity-github",
        description="Opt-in GitHub helpers backed by an existing authenticated gh CLI",
    )
    p.add_argument("--root", default=".", help="Repository root (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("import-issue", help="Import a GitHub issue into a local Antigravity task")
    issue.add_argument("repo", help="GitHub repository in owner/name form")
    issue.add_argument("issue_number", type=int)

    handoff = sub.add_parser("pr-handoff", help="Generate a PR-ready handoff from local task state")
    handoff.add_argument("task_id")
    handoff.add_argument("--output", type=Path)
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "import-issue":
        import_issue(root, args.repo, args.issue_number)
    elif args.command == "pr-handoff":
        pr_handoff(root, args.task_id, args.output)


if __name__ == "__main__":
    main()
