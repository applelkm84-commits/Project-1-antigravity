from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .cli import (
    ROLES,
    ROLE_INSTRUCTIONS,
    dependency_cycle_ids,
    find_task,
    load_state,
    markdown_section,
    readiness_label,
    save_state,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return now_utc().isoformat()


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def active_decisions(task: dict) -> list[dict]:
    latest: dict[str, dict] = {}
    for decision in task.get("decisions", []):
        key = decision.get("key")
        if isinstance(key, str) and key:
            latest[key] = decision
    return list(latest.values())


def active_approvals(task: dict, at: datetime | None = None) -> list[dict]:
    at = at or now_utc()
    active: list[dict] = []
    for approval in task.get("approvals", []):
        if approval.get("revoked_at"):
            continue
        expires_at = approval.get("expires_at")
        if expires_at and parse_time(expires_at) <= at:
            continue
        active.append(approval)
    return active


def active_lease(task: dict, at: datetime | None = None) -> dict | None:
    at = at or now_utc()
    lease = task.get("lease")
    if not isinstance(lease, dict):
        return None
    expires_at = lease.get("expires_at")
    if not isinstance(expires_at, str) or parse_time(expires_at) <= at:
        return None
    return lease


def record_decision(root: Path, task_id: str, key: str, value: str, reason: str | None) -> dict:
    key = key.strip()
    value = value.strip()
    if not key or not value:
        raise SystemExit("Decision key and value must be non-empty")
    state = load_state(root)
    task = find_task(state, task_id)
    decision = {
        "key": key,
        "value": value,
        "reason": (reason or "").strip(),
        "created_at": iso_now(),
    }
    task.setdefault("decisions", []).append(decision)
    save_state(root, state)
    print(f"Recorded decision {key}={value} for {task_id}")
    return decision


def record_approval(
    root: Path,
    task_id: str,
    scope: str,
    approved_by: str,
    ttl_minutes: int | None,
    note: str | None,
) -> dict:
    scope = scope.strip()
    approved_by = approved_by.strip()
    if not scope or not approved_by:
        raise SystemExit("Approval scope and approver must be non-empty")
    if ttl_minutes is not None and ttl_minutes <= 0:
        raise SystemExit("Approval TTL must be greater than zero minutes")
    created = now_utc()
    approval = {
        "scope": scope,
        "approved_by": approved_by,
        "created_at": created.isoformat(),
    }
    if ttl_minutes is not None:
        approval["expires_at"] = (created + timedelta(minutes=ttl_minutes)).isoformat()
    if note:
        approval["note"] = note.strip()
    state = load_state(root)
    task = find_task(state, task_id)
    task.setdefault("approvals", []).append(approval)
    save_state(root, state)
    print(f"Recorded approval for {scope} on {task_id}")
    return approval


def revoke_approval(root: Path, task_id: str, scope: str, revoked_by: str) -> dict:
    state = load_state(root)
    task = find_task(state, task_id)
    candidates = [item for item in active_approvals(task) if item.get("scope") == scope]
    if not candidates:
        raise SystemExit(f"No active approval found for scope: {scope}")
    approval = candidates[-1]
    approval["revoked_at"] = iso_now()
    approval["revoked_by"] = revoked_by
    save_state(root, state)
    print(f"Revoked approval for {scope} on {task_id}")
    return approval


def _archive_lease(task: dict, lease: dict, event: str, actor: str | None = None) -> None:
    archived = dict(lease)
    archived["ended_at"] = iso_now()
    archived["end_reason"] = event
    if actor:
        archived["ended_by"] = actor
    task.setdefault("lease_history", []).append(archived)


def claim_task(root: Path, task_id: str, owner: str, ttl_minutes: int) -> dict:
    owner = owner.strip()
    if not owner:
        raise SystemExit("Lease owner must be non-empty")
    if ttl_minutes <= 0:
        raise SystemExit("Lease TTL must be greater than zero minutes")
    state = load_state(root)
    task = find_task(state, task_id)
    current = active_lease(task)
    if current and current.get("owner") != owner:
        raise SystemExit(
            f"Task is already claimed by {current.get('owner')} until {current.get('expires_at')}"
        )
    old = task.get("lease")
    if isinstance(old, dict):
        _archive_lease(task, old, "refreshed" if current else "expired", owner)
    created = now_utc()
    lease = {
        "owner": owner,
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(minutes=ttl_minutes)).isoformat(),
    }
    task["lease"] = lease
    save_state(root, state)
    print(f"Claimed {task_id} for {owner} until {lease['expires_at']}")
    return lease


def release_task(root: Path, task_id: str, owner: str) -> None:
    state = load_state(root)
    task = find_task(state, task_id)
    current = active_lease(task)
    if current is None:
        raise SystemExit("Task has no active lease")
    if current.get("owner") != owner:
        raise SystemExit(f"Task is claimed by {current.get('owner')}, not {owner}")
    _archive_lease(task, current, "released", owner)
    task.pop("lease", None)
    save_state(root, state)
    print(f"Released {task_id} from {owner}")


def context_payload(task: dict) -> dict:
    fields = (
        "id",
        "title",
        "status",
        "depends_on",
        "reviews",
        "verifications",
        "source",
        "decisions",
        "approvals",
        "lease",
        "completed_at",
    )
    return {key: task.get(key) for key in fields if key in task}


def context_fingerprint(task: dict) -> str:
    encoded = json.dumps(
        context_payload(task),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def check_context(root: Path, task_id: str, expected: str) -> bool:
    task = find_task(load_state(root), task_id)
    current = context_fingerprint(task)
    fresh = current == expected
    if fresh:
        print(f"fresh {current}")
        return True
    print(f"stale expected={expected} current={current}")
    return False


def latest_verifications(task: dict) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for item in task.get("verifications", []):
        check = item.get("check")
        if isinstance(check, str) and check:
            latest[check] = item
    return latest


def reality_report(state: dict, task: dict) -> dict:
    tasks = state.get("tasks", [])
    task_by_id = {item.get("id"): item for item in tasks if item.get("id")}
    readiness = readiness_label(task, task_by_id, dependency_cycle_ids(tasks)) or "complete"
    blockers: list[str] = []
    evidence_debt: list[str] = []

    if readiness.startswith("blocked="):
        blockers.append(readiness)

    error_findings = [item for item in task.get("reviews", []) if item.get("severity") == "error"]
    if error_findings:
        blockers.append(f"error_review_findings={len(error_findings)}")

    latest_checks = latest_verifications(task)
    failed_checks = [name for name, item in latest_checks.items() if item.get("result") == "failed"]
    passed_checks = [name for name, item in latest_checks.items() if item.get("result") == "passed"]
    if failed_checks:
        blockers.extend(f"failed_check={name}" for name in sorted(failed_checks))
    if not latest_checks:
        evidence_debt.append("no_verification_records")
    elif not passed_checks:
        evidence_debt.append("no_passed_verification")

    lease = active_lease(task)
    report = {
        "task_id": task.get("id"),
        "readiness": readiness,
        "finish_ready": not blockers and not evidence_debt,
        "blockers": blockers,
        "evidence_debt": evidence_debt,
        "active_decisions": len(active_decisions(task)),
        "active_approvals": len(active_approvals(task)),
        "lease": lease,
        "context_fingerprint": context_fingerprint(task),
    }
    return report


def show_reality(root: Path, task_id: str, as_json: bool = False) -> dict:
    state = load_state(root)
    task = find_task(state, task_id)
    report = reality_report(state, task)
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"task={task_id}")
        print(f"finish_ready={'yes' if report['finish_ready'] else 'no'}")
        print(f"readiness={report['readiness']}")
        print(f"fingerprint={report['context_fingerprint']}")
        lease = report["lease"]
        print(
            f"lease={lease['owner']} until {lease['expires_at']}"
            if lease
            else "lease=none"
        )
        print("blockers=" + (", ".join(report["blockers"]) or "none"))
        print("evidence_debt=" + (", ".join(report["evidence_debt"]) or "none"))
    return report


def coordination_prompt(root: Path, task_id: str, role: str, output: Path | None = None) -> str:
    if role not in ROLE_INSTRUCTIONS:
        raise SystemExit(f"Unknown role: {role}")
    state = load_state(root)
    task = find_task(state, task_id)
    task_path = root / task["path"]
    if not task_path.exists():
        raise SystemExit(f"Task Markdown is missing: {task['path']}")
    markdown = task_path.read_text(encoding="utf-8")
    report = reality_report(state, task)
    fingerprint = report["context_fingerprint"]

    decisions = active_decisions(task)
    decisions_text = "\n".join(
        f"- `{item['key']}` = {item['value']}" + (f" — {item.get('reason')}" if item.get("reason") else "")
        for item in decisions
    ) or "- None recorded"

    approvals = active_approvals(task)
    approvals_text = "\n".join(
        f"- {item['scope']} — approved by {item['approved_by']}"
        + (f" until {item['expires_at']}" if item.get("expires_at") else "")
        + (f" — {item['note']}" if item.get("note") else "")
        for item in approvals
    ) or "- None active"

    lease = active_lease(task)
    lease_text = (
        f"Owned by {lease['owner']} until {lease['expires_at']}"
        if lease
        else "No active lease"
    )
    role_lines = "\n".join(f"- {item}" for item in ROLE_INSTRUCTIONS[role])
    blockers = ", ".join(report["blockers"]) or "None"
    debt = ", ".join(report["evidence_debt"]) or "None"

    prompt = f"""# Antigravity coordination packet

Role: {role}
Task ID: {task_id}
Context fingerprint: {fingerprint}
Status: {task.get('status', 'planned')}
Readiness: {report['readiness']}
Lease: {lease_text}

## Objective
{markdown_section(markdown, 'Objective') or task.get('title', '')}

## Constraints
{markdown_section(markdown, 'Constraints') or '- None recorded'}

## Acceptance criteria
{markdown_section(markdown, 'Acceptance criteria') or '- None recorded'}

## Settled decisions
{decisions_text}

## Active approval receipts
{approvals_text}

## Current review findings
{markdown_section(markdown, 'Review findings') or 'None recorded.'}

## Recorded verification evidence
{markdown_section(markdown, 'Verification records') or 'None recorded.'}

## Reality check
- Finish ready: {'yes' if report['finish_ready'] else 'no'}
- Blockers: {blockers}
- Evidence debt: {debt}

## Role instructions
{role_lines}

## Coordination rules
- Treat settled decisions as the current source of truth unless a newer decision explicitly changes the same key.
- Do not re-ask for an action that is already covered by an active approval receipt with the same scope.
- An approval receipt does not authorize a broader or different action than its recorded scope.
- If another owner holds the active lease, stop before editing and coordinate instead of racing them.
- Before an irreversible or externally visible action, recompute/check the context fingerprint when possible. If it changed, refresh context before acting.
- Do not invent approvals, verification results, repository state, or completed work.

## Required handoff
Result: <decision or completed work>
Evidence/changes: <facts, files, checks actually run>
Risk/blocker: <only if present; otherwise None>
Next: <next action and role>
Context fingerprint used: {fingerprint}
"""
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(prompt, encoding="utf-8")
        print(output)
    else:
        print(prompt, end="")
    return prompt


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="antigravity-coord",
        description="Local coordination receipts, leases, stale-context checks, and reality reports",
    )
    p.add_argument("--root", default=".", help="Repository root (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    decide = sub.add_parser("decide", help="Record a durable keyed decision")
    decide.add_argument("task_id")
    decide.add_argument("key")
    decide.add_argument("value")
    decide.add_argument("--reason")

    approve = sub.add_parser("approve", help="Record a scoped approval receipt")
    approve.add_argument("task_id")
    approve.add_argument("scope")
    approve.add_argument("--by", dest="approved_by", required=True)
    approve.add_argument("--ttl-minutes", type=int)
    approve.add_argument("--note")

    revoke = sub.add_parser("revoke", help="Revoke the latest active approval for a scope")
    revoke.add_argument("task_id")
    revoke.add_argument("scope")
    revoke.add_argument("--by", dest="revoked_by", required=True)

    claim = sub.add_parser("claim", help="Claim a task with an expiring lease")
    claim.add_argument("task_id")
    claim.add_argument("--owner", required=True)
    claim.add_argument("--ttl-minutes", type=int, default=30)

    release = sub.add_parser("release", help="Release a task lease")
    release.add_argument("task_id")
    release.add_argument("--owner", required=True)

    fingerprint = sub.add_parser("fingerprint", help="Print the current deterministic task-context fingerprint")
    fingerprint.add_argument("task_id")

    check = sub.add_parser("check-context", help="Check whether a previously captured fingerprint is still current")
    check.add_argument("task_id")
    check.add_argument("fingerprint")

    reality = sub.add_parser("reality", help="Report blockers and evidence debt before finishing")
    reality.add_argument("task_id")
    reality.add_argument("--json", action="store_true", dest="as_json")

    prompt = sub.add_parser("prompt", help="Generate a coordination-aware role prompt")
    prompt.add_argument("task_id")
    prompt.add_argument("--role", choices=ROLES, required=True)
    prompt.add_argument("--output", type=Path)
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "decide":
        record_decision(root, args.task_id, args.key, args.value, args.reason)
    elif args.command == "approve":
        record_approval(root, args.task_id, args.scope, args.approved_by, args.ttl_minutes, args.note)
    elif args.command == "revoke":
        revoke_approval(root, args.task_id, args.scope, args.revoked_by)
    elif args.command == "claim":
        claim_task(root, args.task_id, args.owner, args.ttl_minutes)
    elif args.command == "release":
        release_task(root, args.task_id, args.owner)
    elif args.command == "fingerprint":
        task = find_task(load_state(root), args.task_id)
        print(context_fingerprint(task))
    elif args.command == "check-context":
        if not check_context(root, args.task_id, args.fingerprint):
            raise SystemExit(2)
    elif args.command == "reality":
        show_reality(root, args.task_id, args.as_json)
    elif args.command == "prompt":
        coordination_prompt(root, args.task_id, args.role, args.output)


if __name__ == "__main__":
    main()
