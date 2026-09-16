from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .cli import find_task, load_state, save_state


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def record_assumption(
    root: Path,
    task_id: str,
    key: str,
    value: str,
    source: str | None,
    ttl_minutes: int | None,
) -> dict:
    key = key.strip()
    value = value.strip()
    if not key or not value:
        raise SystemExit("Assumption key and value must be non-empty")
    if ttl_minutes is not None and ttl_minutes <= 0:
        raise SystemExit("Assumption TTL must be greater than zero minutes")
    created = now_utc()
    assumption = {
        "key": key,
        "value": value,
        "created_at": created.isoformat(),
    }
    if source:
        assumption["source"] = source.strip()
    if ttl_minutes is not None:
        assumption["expires_at"] = (created + timedelta(minutes=ttl_minutes)).isoformat()
    state = load_state(root)
    task = find_task(state, task_id)
    task.setdefault("assumptions", []).append(assumption)
    save_state(root, state)
    print(f"Recorded assumption {key}={value} for {task_id}")
    return assumption


def latest_assumptions(task: dict) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for assumption in task.get("assumptions", []):
        key = assumption.get("key")
        if isinstance(key, str) and key:
            latest[key] = assumption
    return latest


def assumption_status(task: dict, at: datetime | None = None) -> tuple[list[dict], list[dict]]:
    at = at or now_utc()
    active: list[dict] = []
    expired: list[dict] = []
    for assumption in latest_assumptions(task).values():
        expires_at = assumption.get("expires_at")
        if expires_at and parse_time(expires_at) <= at:
            expired.append(assumption)
        else:
            active.append(assumption)
    return active, expired


def add_invariant(root: Path, task_id: str, text: str) -> dict:
    text = text.strip()
    if not text:
        raise SystemExit("Invariant text must be non-empty")
    state = load_state(root)
    task = find_task(state, task_id)
    existing = [item for item in task.get("invariants", []) if item.get("text") == text]
    if existing:
        print(f"Invariant already recorded for {task_id}")
        return existing[-1]
    invariant = {"text": text, "created_at": now_utc().isoformat()}
    task.setdefault("invariants", []).append(invariant)
    save_state(root, state)
    print(f"Recorded invariant for {task_id}: {text}")
    return invariant


def set_change_policy(
    root: Path,
    task_id: str,
    allow: list[str],
    protect: list[str],
    max_files: int | None,
    max_lines: int | None,
) -> dict:
    if max_files is not None and max_files <= 0:
        raise SystemExit("max-files must be greater than zero")
    if max_lines is not None and max_lines <= 0:
        raise SystemExit("max-lines must be greater than zero")
    policy = {
        "allow": [item for item in allow if item],
        "protect": [item for item in protect if item],
        "max_files": max_files,
        "max_lines": max_lines,
        "updated_at": now_utc().isoformat(),
    }
    state = load_state(root)
    task = find_task(state, task_id)
    task["change_policy"] = policy
    save_state(root, state)
    print(f"Updated change policy for {task_id}")
    return policy


def run_git(root: Path, args: list[str]) -> str:
    if shutil.which("git") is None:
        raise SystemExit("Git was not found in PATH")
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or f"exit code {completed.returncode}"
        raise SystemExit(f"Git command failed: {detail}")
    return completed.stdout


def _visible_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return normalized != ".antigravity" and not normalized.startswith(".antigravity/")


def changed_files(root: Path, base: str | None = None) -> list[str]:
    comparison = base or "HEAD"
    tracked = [
        line.strip().replace("\\", "/")
        for line in run_git(root, ["diff", "--name-only", comparison, "--"]).splitlines()
        if line.strip()
    ]
    untracked = [
        line.strip().replace("\\", "/")
        for line in run_git(root, ["ls-files", "--others", "--exclude-standard"]).splitlines()
        if line.strip()
    ]
    return sorted({path for path in [*tracked, *untracked] if _visible_path(path)})


def changed_line_count(root: Path, changed: list[str], base: str | None = None) -> int:
    comparison = base or "HEAD"
    total = 0
    tracked_paths: set[str] = set()
    for line in run_git(root, ["diff", "--numstat", comparison, "--"]).splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        additions, deletions, path = parts[0], parts[1], parts[-1].replace("\\", "/")
        if not _visible_path(path):
            continue
        tracked_paths.add(path)
        if additions.isdigit():
            total += int(additions)
        if deletions.isdigit():
            total += int(deletions)

    for path in changed:
        if path in tracked_paths:
            continue
        candidate = root / path
        if not candidate.is_file():
            continue
        try:
            total += len(candidate.read_text(encoding="utf-8").splitlines())
        except (UnicodeDecodeError, OSError):
            continue
    return total


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def guard_status(task: dict) -> dict:
    active, expired = assumption_status(task)
    return {
        "active_assumptions": active,
        "expired_assumptions": expired,
        "invariants": task.get("invariants", []),
        "change_policy": task.get("change_policy", {}),
    }


def audit_git(root: Path, task_id: str, base: str | None = None, record: bool = True) -> dict:
    state = load_state(root)
    task = find_task(state, task_id)
    policy = task.get("change_policy") or {}
    allow = list(policy.get("allow") or [])
    protect = list(policy.get("protect") or [])
    files = changed_files(root, base)
    lines = changed_line_count(root, files, base)

    protected_changes = [path for path in files if _matches(path, protect)]
    outside_scope = [path for path in files if allow and not _matches(path, allow)]
    violations: list[str] = []
    violations.extend(f"protected_path:{path}" for path in protected_changes)
    violations.extend(f"outside_scope:{path}" for path in outside_scope if path not in protected_changes)

    max_files = policy.get("max_files")
    max_lines = policy.get("max_lines")
    if isinstance(max_files, int) and len(files) > max_files:
        violations.append(f"max_files:{len(files)}>{max_files}")
    if isinstance(max_lines, int) and lines > max_lines:
        violations.append(f"max_lines:{lines}>{max_lines}")

    active, expired = assumption_status(task)
    violations.extend(f"expired_assumption:{item['key']}" for item in expired)

    report = {
        "task_id": task_id,
        "base": base or "HEAD",
        "clean": not violations,
        "changed_files": files,
        "changed_file_count": len(files),
        "changed_line_count": lines,
        "protected_changes": protected_changes,
        "outside_scope": outside_scope,
        "violations": violations,
        "active_assumptions": [item["key"] for item in active],
        "expired_assumptions": [item["key"] for item in expired],
        "invariant_count": len(task.get("invariants", [])),
        "audited_at": now_utc().isoformat(),
    }
    if record:
        task.setdefault("guard_audits", []).append(report)
        save_state(root, state)
    return report


def render_report(report: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print(f"task={report['task_id']}")
    print(f"clean={'yes' if report['clean'] else 'no'}")
    print(f"base={report['base']}")
    print(f"changed_files={report['changed_file_count']}")
    print(f"changed_lines={report['changed_line_count']}")
    print("violations=" + (", ".join(report["violations"]) or "none"))
    print("expired_assumptions=" + (", ".join(report["expired_assumptions"]) or "none"))


def guard_packet(root: Path, task_id: str, output: Path | None = None) -> str:
    task = find_task(load_state(root), task_id)
    active, expired = assumption_status(task)
    assumptions = "\n".join(
        f"- `{item['key']}` = {item['value']}"
        + (f" — source: {item['source']}" if item.get("source") else "")
        + (f" — expires: {item['expires_at']}" if item.get("expires_at") else "")
        for item in active
    ) or "- None active"
    expired_text = "\n".join(
        f"- `{item['key']}` expired at {item.get('expires_at')}"
        for item in expired
    ) or "- None"
    invariants = "\n".join(f"- {item['text']}" for item in task.get("invariants", [])) or "- None recorded"
    policy = task.get("change_policy") or {}
    packet = f"""# Antigravity guard context

## Active assumptions
{assumptions}

## Expired assumptions
{expired_text}

## Protected invariants
{invariants}

## Change policy
- Allowed paths: {', '.join(policy.get('allow') or []) or 'unrestricted'}
- Protected paths: {', '.join(policy.get('protect') or []) or 'none'}
- Maximum changed files: {policy.get('max_files') if policy.get('max_files') is not None else 'unlimited'}
- Maximum changed lines: {policy.get('max_lines') if policy.get('max_lines') is not None else 'unlimited'}

## Guard rules
- Do not treat an expired assumption as current fact; refresh its evidence first.
- Preserve every invariant unless the human explicitly changes it.
- Keep edits inside the declared scope and change budget.
- A clean Git audit is evidence about scope, not proof that the implementation is correct.
"""
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(packet, encoding="utf-8")
        print(output)
    else:
        print(packet, end="")
    return packet


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="antigravity-guard",
        description="Local assumption freshness and Git blast-radius checks",
    )
    p.add_argument("--root", default=".", help="Repository root (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    assume = sub.add_parser("assume", help="Record a keyed assumption with optional TTL and source")
    assume.add_argument("task_id")
    assume.add_argument("key")
    assume.add_argument("value")
    assume.add_argument("--source")
    assume.add_argument("--ttl-minutes", type=int)

    invariant = sub.add_parser("invariant", help="Record a protected invariant")
    invariant.add_argument("task_id")
    invariant.add_argument("text")

    policy = sub.add_parser("policy", help="Replace the task's local change policy")
    policy.add_argument("task_id")
    policy.add_argument("--allow", action="append", default=[])
    policy.add_argument("--protect", action="append", default=[])
    policy.add_argument("--max-files", type=int)
    policy.add_argument("--max-lines", type=int)

    status = sub.add_parser("status", help="Show assumptions, invariants, and change policy")
    status.add_argument("task_id")
    status.add_argument("--json", action="store_true", dest="as_json")

    audit = sub.add_parser("audit", help="Audit local Git changes against task scope and freshness")
    audit.add_argument("task_id")
    audit.add_argument("--base", help="Compare working tree against this Git ref (default: HEAD)")
    audit.add_argument("--json", action="store_true", dest="as_json")
    audit.add_argument("--no-record", action="store_true")

    packet = sub.add_parser("packet", help="Generate assumption/invariant/change-policy context")
    packet.add_argument("task_id")
    packet.add_argument("--output", type=Path)
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "assume":
        record_assumption(root, args.task_id, args.key, args.value, args.source, args.ttl_minutes)
    elif args.command == "invariant":
        add_invariant(root, args.task_id, args.text)
    elif args.command == "policy":
        set_change_policy(root, args.task_id, args.allow, args.protect, args.max_files, args.max_lines)
    elif args.command == "status":
        task = find_task(load_state(root), args.task_id)
        report = guard_status(task)
        if args.as_json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            active, expired = assumption_status(task)
            print("active_assumptions=" + (", ".join(item["key"] for item in active) or "none"))
            print("expired_assumptions=" + (", ".join(item["key"] for item in expired) or "none"))
            print(f"invariants={len(task.get('invariants', []))}")
            print(json.dumps(task.get("change_policy") or {}, ensure_ascii=False))
    elif args.command == "audit":
        report = audit_git(root, args.task_id, args.base, not args.no_record)
        render_report(report, args.as_json)
        if not report["clean"]:
            raise SystemExit(3)
    elif args.command == "packet":
        guard_packet(root, args.task_id, args.output)


if __name__ == "__main__":
    main()
