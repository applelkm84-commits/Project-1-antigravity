from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = ".antigravity"
STATE_FILE = "state.json"
TASK_DIR = "tasks"

AGENT_POLICY = """# AGENTS.md

## Mission
Complete clear tasks autonomously while preserving project constraints, evidence, and reviewability.

## Roles
- Orchestrator: owns decomposition, routing, and completion.
- Researcher: resolves unknowns and records evidence; does not silently modify product code.
- Builder: implements the smallest safe change that satisfies the task.
- Reviewer: checks correctness, regressions, security, and instruction compliance.
- Finisher: runs final verification, updates documentation, and records the handoff.

## Autonomy rules
1. Do not ask for confirmation when the request is clear and the action is reversible.
2. Ask only when ambiguity could materially change cost, safety, scope, or irreversible outcomes.
3. Prefer a reasonable documented default over a low-value clarification.
4. Never invent evidence, test results, repository state, or user approval.
5. Keep handoffs compact: decisions, evidence, changed files, risks, next action.

## Definition of done
A task is complete only when implementation, verification, and a concise completion record exist.
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:48] or "task"


def state_path(root: Path) -> Path:
    return root / STATE_DIR / STATE_FILE


def load_state(root: Path) -> dict:
    path = state_path(root)
    if not path.exists():
        return {"version": 1, "tasks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(root: Path, state: dict) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def init_repo(root: Path) -> None:
    (root / STATE_DIR / TASK_DIR).mkdir(parents=True, exist_ok=True)
    agents = root / "AGENTS.md"
    if not agents.exists():
        agents.write_text(AGENT_POLICY, encoding="utf-8")
    path = state_path(root)
    if not path.exists():
        save_state(root, {"version": 1, "created_at": utc_now(), "tasks": []})
    print(f"Initialized Antigravity in {root}")


def render_task(title: str, task_id: str, constraints: list[str], acceptance: list[str]) -> str:
    constraints_text = "\n".join(f"- {item}" for item in constraints) or "- None recorded"
    acceptance_text = "\n".join(f"- [ ] {item}" for item in acceptance) or "- [ ] Define and verify acceptance criteria"
    return f"""# {title}

**Task ID:** `{task_id}`  
**Status:** planned  
**Created:** {utc_now()}

## Objective
{title}

## Constraints
{constraints_text}

## Acceptance criteria
{acceptance_text}

## Plan
1. Orchestrator confirms scope and material unknowns.
2. Researcher resolves only the unknowns needed for implementation.
3. Builder implements the smallest safe change set.
4. Reviewer checks correctness, regressions, security, and constraints.
5. Finisher records verification and completion notes.

## Handoffs
Record only decisions, evidence, changed files, risks, and the next action.

## Review findings
None recorded.

## Verification
- [ ] Relevant tests/checks executed
- [ ] Acceptance criteria reviewed
- [ ] Documentation updated if behavior changed

## Completion notes
Pending.
"""


def find_task(state: dict, task_id: str) -> dict:
    for task in state.get("tasks", []):
        if task.get("id") == task_id:
            return task
    raise SystemExit(f"Unknown task id: {task_id}")


def create_task(root: Path, title: str, constraints: list[str], acceptance: list[str]) -> Path:
    if not state_path(root).exists():
        init_repo(root)
    state = load_state(root)
    created = datetime.now(timezone.utc)
    stamp = created.strftime("%Y%m%d-%H%M%S")
    task_id = f"{stamp}-{slugify(title)}"
    relative = Path(STATE_DIR) / TASK_DIR / f"{task_id}.md"
    path = root / relative
    path.write_text(render_task(title, task_id, constraints, acceptance), encoding="utf-8")
    state.setdefault("tasks", []).append(
        {
            "id": task_id,
            "title": title,
            "status": "planned",
            "path": relative.as_posix(),
            "created_at": created.replace(microsecond=0).isoformat(),
            "reviews": [],
        }
    )
    save_state(root, state)
    print(path)
    return path


def record_review(root: Path, task_id: str, severity: str, finding: str, path_ref: str | None) -> None:
    state = load_state(root)
    task = find_task(state, task_id)
    review = {
        "severity": severity,
        "finding": finding,
        "created_at": utc_now(),
    }
    if path_ref:
        review["path"] = path_ref
    task.setdefault("reviews", []).append(review)
    save_state(root, state)

    task_path = root / task["path"]
    if task_path.exists():
        text = task_path.read_text(encoding="utf-8")
        location = f" ({path_ref})" if path_ref else ""
        line = f"- **{severity.upper()}**{location}: {finding}"
        empty_marker = "## Review findings\nNone recorded."
        if empty_marker in text:
            text = text.replace(empty_marker, f"## Review findings\n{line}", 1)
        elif "## Review findings\n" in text and "\n\n## Verification" in text:
            text = text.replace("\n\n## Verification", f"\n{line}\n\n## Verification", 1)
        else:
            text = text.replace("## Verification", f"## Review findings\n{line}\n\n## Verification", 1)
        task_path.write_text(text, encoding="utf-8")
    print(f"Recorded {severity} finding for {task_id}")


def complete_task(root: Path, task_id: str, note: str | None) -> None:
    state = load_state(root)
    task = find_task(state, task_id)
    task["status"] = "complete"
    task["completed_at"] = utc_now()
    task_path = root / task["path"]
    if task_path.exists():
        text = task_path.read_text(encoding="utf-8")
        text = text.replace("**Status:** planned", "**Status:** complete", 1)
        completion = note or "Task marked complete after verification."
        text = text.replace("## Completion notes\nPending.", f"## Completion notes\n{completion}", 1)
        task_path.write_text(text, encoding="utf-8")
    save_state(root, state)
    print(f"Completed {task_id}")


def show_status(root: Path) -> None:
    state = load_state(root)
    tasks = state.get("tasks", [])
    if not tasks:
        print("No tasks recorded.")
        return
    for task in tasks:
        reviews = len(task.get("reviews", []))
        suffix = f"  reviews={reviews}" if reviews else ""
        print(f"{task['status']:<10} {task['id']}  {task['title']}{suffix}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="antigravity", description="File-based multi-agent workflow for coding agents")
    p.add_argument("--root", default=".", help="Repository root (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize Antigravity files")

    task = sub.add_parser("task", help="Create a durable task brief")
    task.add_argument("title")
    task.add_argument("--constraint", action="append", default=[], help="Constraint; repeatable")
    task.add_argument("--accept", action="append", default=[], help="Acceptance criterion; repeatable")

    review = sub.add_parser("review", help="Record a structured review finding")
    review.add_argument("task_id")
    review.add_argument("finding")
    review.add_argument("--severity", choices=["info", "warning", "error"], default="warning")
    review.add_argument("--path", dest="path_ref", help="Optional file/path reference")

    sub.add_parser("status", help="Show recorded task state")

    complete = sub.add_parser("complete", help="Mark a task complete")
    complete.add_argument("task_id")
    complete.add_argument("--note", help="Completion note")
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "init":
        init_repo(root)
    elif args.command == "task":
        create_task(root, args.title, args.constraint, args.accept)
    elif args.command == "review":
        record_review(root, args.task_id, args.severity, args.finding, args.path_ref)
    elif args.command == "status":
        show_status(root)
    elif args.command == "complete":
        complete_task(root, args.task_id, args.note)


if __name__ == "__main__":
    main()
