from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = ".antigravity"
STATE_FILE = "state.json"
TASK_DIR = "tasks"
BUNDLE_SCHEMA_VERSION = 1
SAFE_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
ROLES = ("orchestrator", "researcher", "builder", "reviewer", "finisher")

ROLE_INSTRUCTIONS = {
    "orchestrator": [
        "Confirm the objective, constraints, acceptance criteria, and current readiness.",
        "Route only material unknowns to research and avoid unnecessary approval loops.",
        "Keep the next handoff compact: decisions, evidence, risks, and next owner.",
    ],
    "researcher": [
        "Resolve only unknowns that can materially change implementation.",
        "Record evidence and conclusions without silently modifying product code.",
        "End with the minimum facts the Builder or Orchestrator needs next.",
    ],
    "builder": [
        "Implement the smallest safe change that satisfies the acceptance criteria.",
        "Preserve unrelated behavior and existing project conventions.",
        "Do not claim verification that was not actually run and recorded.",
    ],
    "reviewer": [
        "Review independently for correctness, regressions, security, and instruction compliance.",
        "Prefer concrete findings with file/path references over stylistic churn.",
        "Separate verified failures from suggestions and unresolved questions.",
    ],
    "finisher": [
        "Check the recorded verification evidence and unresolved review findings.",
        "Update documentation when public behavior changed.",
        "Report changed files, checks actually run, remaining risks, and completion status.",
    ],
}

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


def render_task(
    title: str,
    task_id: str,
    constraints: list[str],
    acceptance: list[str],
    dependencies: list[str] | None = None,
) -> str:
    constraints_text = "\n".join(f"- {item}" for item in constraints) or "- None recorded"
    acceptance_text = "\n".join(f"- [ ] {item}" for item in acceptance) or "- [ ] Define and verify acceptance criteria"
    dependencies = dependencies or []
    dependencies_text = "\n".join(f"- `{item}`" for item in dependencies) or "- None"
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

## Dependencies
{dependencies_text}

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

## Verification records
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


def create_task(
    root: Path,
    title: str,
    constraints: list[str],
    acceptance: list[str],
    dependencies: list[str] | None = None,
) -> Path:
    if not state_path(root).exists():
        init_repo(root)
    dependencies = dependencies or []
    state = load_state(root)
    created = datetime.now(timezone.utc)
    stamp = created.strftime("%Y%m%d-%H%M%S")
    task_id = f"{stamp}-{slugify(title)}"
    relative = Path(STATE_DIR) / TASK_DIR / f"{task_id}.md"
    path = root / relative
    path.write_text(render_task(title, task_id, constraints, acceptance, dependencies), encoding="utf-8")
    state.setdefault("tasks", []).append(
        {
            "id": task_id,
            "title": title,
            "status": "planned",
            "path": relative.as_posix(),
            "created_at": created.replace(microsecond=0).isoformat(),
            "reviews": [],
            "verifications": [],
            "depends_on": dependencies,
        }
    )
    save_state(root, state)
    print(path)
    return path


def record_review(root: Path, task_id: str, severity: str, finding: str, path_ref: str | None) -> None:
    state = load_state(root)
    task = find_task(state, task_id)
    review = {"severity": severity, "finding": finding, "created_at": utc_now()}
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
        elif "## Review findings\n" in text and "\n\n## Verification records" in text:
            text = text.replace("\n\n## Verification records", f"\n{line}\n\n## Verification records", 1)
        elif "## Review findings\n" in text and "\n\n## Verification" in text:
            text = text.replace("\n\n## Verification", f"\n{line}\n\n## Verification", 1)
        else:
            text = text.replace("## Verification", f"## Review findings\n{line}\n\n## Verification", 1)
        task_path.write_text(text, encoding="utf-8")
    print(f"Recorded {severity} finding for {task_id}")


def record_verification(root: Path, task_id: str, check: str, result: str, note: str | None) -> None:
    state = load_state(root)
    task = find_task(state, task_id)
    verification = {"check": check, "result": result, "created_at": utc_now()}
    if note:
        verification["note"] = note
    task.setdefault("verifications", []).append(verification)
    save_state(root, state)
    task_path = root / task["path"]
    if task_path.exists():
        text = task_path.read_text(encoding="utf-8")
        note_text = f" — {note}" if note else ""
        line = f"- **{result.upper()}** `{check}`{note_text}"
        empty_marker = "## Verification records\nNone recorded."
        if empty_marker in text:
            text = text.replace(empty_marker, f"## Verification records\n{line}", 1)
        elif "## Verification records\n" in text and "\n\n## Verification" in text:
            text = text.replace("\n\n## Verification", f"\n{line}\n\n## Verification", 1)
        else:
            text = text.replace("## Verification", f"## Verification records\n{line}\n\n## Verification", 1)
        task_path.write_text(text, encoding="utf-8")
    print(f"Recorded {result} verification for {task_id}: {check}")


def dependency_cycle_ids(tasks: list[dict]) -> set[str]:
    task_by_id = {task.get("id"): task for task in tasks if task.get("id")}
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: set[str] = set()

    def visit(task_id: str) -> None:
        state[task_id] = 1
        stack.append(task_id)
        for dependency in task_by_id[task_id].get("depends_on", []):
            if dependency not in task_by_id:
                continue
            dependency_state = state.get(dependency, 0)
            if dependency_state == 0:
                visit(dependency)
            elif dependency_state == 1:
                cycles.update(stack[stack.index(dependency) :])
        stack.pop()
        state[task_id] = 2

    for task_id in task_by_id:
        if state.get(task_id, 0) == 0:
            visit(task_id)
    return cycles


def readiness_label(task: dict, task_by_id: dict[str, dict], cycle_ids: set[str]) -> str | None:
    if task.get("status") == "complete":
        return None
    task_id = task.get("id")
    if task_id in cycle_ids:
        return "blocked=cycle"
    for dependency in task.get("depends_on", []):
        dependency_task = task_by_id.get(dependency)
        if dependency_task is None:
            return f"blocked=missing:{dependency}"
        if dependency_task.get("status") != "complete":
            return f"blocked={dependency}"
    return "ready"


def export_task(root: Path, task_id: str, output: Path | None) -> str:
    state = load_state(root)
    task = find_task(state, task_id)
    task_path = root / task["path"]
    if not task_path.exists():
        raise SystemExit(f"Task Markdown is missing: {task['path']}")
    payload = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "task": task,
        "markdown": task_path.read_text(encoding="utf-8"),
    }
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        print(output)
    else:
        print(serialized, end="")
    return serialized


def import_task(root: Path, source: Path) -> Path:
    if not state_path(root).exists():
        init_repo(root)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Unable to read task bundle: {exc}") from exc
    if payload.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise SystemExit(f"Unsupported task bundle schema: {payload.get('schema_version')}")
    task = payload.get("task")
    markdown = payload.get("markdown")
    if not isinstance(task, dict) or not isinstance(markdown, str):
        raise SystemExit("Invalid task bundle: expected task object and markdown text")
    task_id = task.get("id")
    title = task.get("title")
    status = task.get("status", "planned")
    if not isinstance(task_id, str) or not SAFE_TASK_ID.fullmatch(task_id):
        raise SystemExit("Invalid task bundle: unsafe task id")
    if not isinstance(title, str) or not title.strip():
        raise SystemExit("Invalid task bundle: missing task title")
    if status not in {"planned", "complete"}:
        raise SystemExit(f"Invalid task bundle: unsupported task status {status!r}")
    state = load_state(root)
    if any(existing.get("id") == task_id for existing in state.get("tasks", [])):
        raise SystemExit(f"Task already exists: {task_id}")
    relative = Path(STATE_DIR) / TASK_DIR / f"{task_id}.md"
    imported = dict(task)
    imported["path"] = relative.as_posix()
    imported.setdefault("reviews", [])
    imported.setdefault("verifications", [])
    imported.setdefault("depends_on", [])
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    state.setdefault("tasks", []).append(imported)
    save_state(root, state)
    print(path)
    return path


def markdown_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*\n(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group(1).strip() if match else ""


def codex_prompt(root: Path, task_id: str, role: str, output: Path | None) -> str:
    if role not in ROLE_INSTRUCTIONS:
        raise SystemExit(f"Unknown role: {role}")
    state = load_state(root)
    task = find_task(state, task_id)
    task_path = root / task["path"]
    if not task_path.exists():
        raise SystemExit(f"Task Markdown is missing: {task['path']}")
    markdown = task_path.read_text(encoding="utf-8")
    task_by_id = {item.get("id"): item for item in state.get("tasks", []) if item.get("id")}
    readiness = readiness_label(task, task_by_id, dependency_cycle_ids(state.get("tasks", []))) or "complete"

    objective = markdown_section(markdown, "Objective") or task.get("title", "")
    constraints = markdown_section(markdown, "Constraints") or "- None recorded"
    acceptance = markdown_section(markdown, "Acceptance criteria") or "- None recorded"
    dependencies = markdown_section(markdown, "Dependencies") or "- None"
    reviews = markdown_section(markdown, "Review findings") or "None recorded."
    verifications = markdown_section(markdown, "Verification records") or "None recorded."
    role_lines = "\n".join(f"- {item}" for item in ROLE_INSTRUCTIONS[role])

    prompt = f"""# Antigravity task context

Role: {role}
Task ID: {task_id}
Title: {task.get('title', '')}
Status: {task.get('status', 'planned')}
Readiness: {readiness}

## Objective
{objective}

## Constraints
{constraints}

## Acceptance criteria
{acceptance}

## Dependencies
{dependencies}

## Current review findings
{reviews}

## Recorded verification evidence
{verifications}

## Role instructions
{role_lines}

## Required handoff
Return a compact handoff using exactly these fields:
Result: <decision or completed work>
Evidence/changes: <facts, files, checks actually run>
Risk/blocker: <only if present; otherwise None>
Next: <next action and role>

Do not invent repository state, test results, approvals, or evidence. Do not replay the full conversation.
"""
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(prompt, encoding="utf-8")
        print(output)
    else:
        print(prompt, end="")
    return prompt


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
    task_by_id = {task.get("id"): task for task in tasks if task.get("id")}
    cycle_ids = dependency_cycle_ids(tasks)
    for task in tasks:
        reviews = len(task.get("reviews", []))
        verifications = task.get("verifications", [])
        passed = sum(1 for item in verifications if item.get("result") == "passed")
        failed = sum(1 for item in verifications if item.get("result") == "failed")
        parts: list[str] = []
        readiness = readiness_label(task, task_by_id, cycle_ids)
        if readiness:
            parts.append(readiness)
        if reviews:
            parts.append(f"reviews={reviews}")
        if verifications:
            parts.append(f"checks={passed}/{len(verifications)}")
        if failed:
            parts.append(f"failed={failed}")
        suffix = f"  {' '.join(parts)}" if parts else ""
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
    task.add_argument("--depends-on", action="append", default=[], help="Prerequisite task ID; repeatable")

    review = sub.add_parser("review", help="Record a structured review finding")
    review.add_argument("task_id")
    review.add_argument("finding")
    review.add_argument("--severity", choices=["info", "warning", "error"], default="warning")
    review.add_argument("--path", dest="path_ref", help="Optional file/path reference")

    verify = sub.add_parser("verify", help="Record the result of a check without executing it")
    verify.add_argument("task_id")
    verify.add_argument("check", help="Check or command name, e.g. 'pytest -q'")
    verify.add_argument("--result", choices=["passed", "failed", "skipped"], required=True)
    verify.add_argument("--note", help="Optional verification note")

    export_cmd = sub.add_parser("export-task", help="Export one task as a portable JSON bundle")
    export_cmd.add_argument("task_id")
    export_cmd.add_argument("--output", type=Path, help="Write bundle to this path instead of stdout")

    import_cmd = sub.add_parser("import-task", help="Import a portable JSON task bundle")
    import_cmd.add_argument("source", type=Path)

    codex = sub.add_parser("codex-prompt", help="Generate a compact role-specific prompt from task state")
    codex.add_argument("task_id")
    codex.add_argument("--role", choices=ROLES, required=True)
    codex.add_argument("--output", type=Path, help="Write prompt to this path instead of stdout")

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
        create_task(root, args.title, args.constraint, args.accept, args.depends_on)
    elif args.command == "review":
        record_review(root, args.task_id, args.severity, args.finding, args.path_ref)
    elif args.command == "verify":
        record_verification(root, args.task_id, args.check, args.result, args.note)
    elif args.command == "export-task":
        export_task(root, args.task_id, args.output)
    elif args.command == "import-task":
        import_task(root, args.source)
    elif args.command == "codex-prompt":
        codex_prompt(root, args.task_id, args.role, args.output)
    elif args.command == "status":
        show_status(root)
    elif args.command == "complete":
        complete_task(root, args.task_id, args.note)


if __name__ == "__main__":
    main()
