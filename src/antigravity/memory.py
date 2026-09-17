from __future__ import annotations

import argparse
import fnmatch
import json
from datetime import datetime, timezone
from pathlib import Path

from .cli import find_task, load_state, markdown_section, save_state
from .coordination import active_decisions, latest_verifications
from .guard import add_invariant, assumption_status, latest_assumptions, record_assumption, run_git

MEMORY_FILE = "memory.json"
MEMORY_VERSION = 1
EVIDENCE_TYPES = ("check", "decision", "assumption", "invariant", "observation")
PROMOTION_TYPES = ("invariant", "assumption", "verification-template", "near-miss")
GENERIC_COMPONENTS = {"src", "lib", "app", "apps", "test", "tests", "docs", "config"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return now_utc().isoformat()


def memory_path(root: Path) -> Path:
    return root / ".antigravity" / MEMORY_FILE


def load_memory(root: Path) -> dict:
    path = memory_path(root)
    if not path.exists():
        return {"version": MEMORY_VERSION, "near_misses": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != MEMORY_VERSION:
        raise SystemExit(f"Unsupported failure-memory version: {data.get('version')}")
    data.setdefault("near_misses", [])
    return data


def save_memory(root: Path, memory: dict) -> None:
    path = memory_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _unique(values: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        value = raw.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def derive_components(paths: list[str]) -> list[str]:
    components: list[str] = []
    for raw in paths:
        path = raw.replace("\\", "/").strip("/")
        parts = [part for part in path.split("/") if part and not any(ch in part for ch in "*?[]")]
        if not parts:
            continue
        directories = parts[:-1] if "." in parts[-1] else parts
        for index, part in enumerate(directories):
            if part.lower() not in GENERIC_COMPONENTS:
                components.append(part)
            if index > 0:
                prefix = "/".join(directories[: index + 1])
                components.append(prefix)
    return _unique(components)


def set_task_context(
    root: Path,
    task_id: str,
    paths: list[str] | None,
    components: list[str] | None,
    risks: list[str] | None,
) -> dict:
    state = load_state(root)
    task = find_task(state, task_id)
    context = task.setdefault("memory_context", {})
    context["paths"] = _unique(list(context.get("paths", [])) + list(paths or []))
    context["components"] = _unique(list(context.get("components", [])) + list(components or []))
    context["risks"] = _unique(list(context.get("risks", [])) + list(risks or []))
    context["updated_at"] = iso_now()
    save_state(root, state)
    print(f"Updated memory context for {task_id}")
    return context


def task_signals(task: dict) -> dict[str, list[str]]:
    context = task.get("memory_context") or {}
    paths = list(context.get("paths", []))
    components = list(context.get("components", []))
    risks = list(context.get("risks", []))

    audits = task.get("guard_audits", [])
    if audits:
        paths.extend(audits[-1].get("changed_files", []))
    policy = task.get("change_policy") or {}
    paths.extend(policy.get("allow", []) or [])
    components.extend(derive_components(paths))
    return {
        "paths": _unique(paths),
        "components": _unique(components),
        "risks": _unique(risks),
    }


def record_near_miss(
    root: Path,
    task_id: str,
    failure_class: str,
    summary: str,
    paths: list[str] | None = None,
    components: list[str] | None = None,
    risks: list[str] | None = None,
    evidence: str | None = None,
    mitigation: str | None = None,
) -> dict:
    failure_class = failure_class.strip()
    summary = summary.strip()
    if not failure_class or not summary:
        raise SystemExit("Near-miss failure class and summary must be non-empty")
    find_task(load_state(root), task_id)
    memory = load_memory(root)
    created = now_utc()
    near_miss = {
        "id": f"nm-{created.strftime('%Y%m%d%H%M%S')}-{len(memory['near_misses']) + 1}",
        "task_id": task_id,
        "failure_class": failure_class,
        "summary": summary,
        "paths": _unique(paths),
        "components": _unique(list(components or []) + derive_components(list(paths or []))),
        "risks": _unique(risks),
        "created_at": created.isoformat(),
    }
    if evidence:
        near_miss["evidence"] = evidence.strip()
    if mitigation:
        near_miss["mitigation"] = mitigation.strip()
    memory["near_misses"].append(near_miss)
    save_memory(root, memory)
    print(f"Recorded near miss {near_miss['id']} for {task_id}")
    return near_miss


def _path_matches(left: str, right: str) -> bool:
    left = left.replace("\\", "/")
    right = right.replace("\\", "/")
    if left == right:
        return True
    if fnmatch.fnmatch(left, right) or fnmatch.fnmatch(right, left):
        return True
    left_prefix = left.rstrip("/*")
    right_prefix = right.rstrip("/*")
    return bool(left_prefix and right_prefix and (left_prefix.startswith(right_prefix + "/") or right_prefix.startswith(left_prefix + "/")))


def relevant_near_misses(
    root: Path,
    task_id: str,
    paths: list[str] | None = None,
    components: list[str] | None = None,
    risks: list[str] | None = None,
) -> list[dict]:
    task = find_task(load_state(root), task_id)
    signals = task_signals(task)
    current_paths = _unique(signals["paths"] + list(paths or []))
    current_components = {item.lower() for item in _unique(signals["components"] + list(components or []))}
    current_risks = {item.lower() for item in _unique(signals["risks"] + list(risks or []))}
    matches: list[dict] = []

    for item in load_memory(root).get("near_misses", []):
        if item.get("task_id") == task_id:
            continue
        reasons: list[str] = []
        score = 0
        for old_path in item.get("paths", []):
            if any(_path_matches(old_path, current) for current in current_paths):
                reasons.append(f"path:{old_path}")
                score += 5
                break
        old_components = {value.lower() for value in item.get("components", [])}
        component_overlap = sorted(old_components & current_components)
        if component_overlap:
            reasons.append("component:" + ",".join(component_overlap))
            score += 3
        old_risks = {value.lower() for value in item.get("risks", [])}
        risk_overlap = sorted(old_risks & current_risks)
        if risk_overlap:
            reasons.append("risk:" + ",".join(risk_overlap))
            score += 2
        if score:
            result = dict(item)
            result["match_score"] = score
            result["match_reasons"] = reasons
            matches.append(result)
    return sorted(matches, key=lambda item: (-item["match_score"], item.get("created_at", ""), item.get("id", "")))


def acceptance_criteria(root: Path, task: dict) -> list[str]:
    task_path = root / task["path"]
    if not task_path.exists():
        return []
    section = markdown_section(task_path.read_text(encoding="utf-8"), "Acceptance criteria")
    criteria: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        line = line[1:].strip()
        if line.startswith("[") and len(line) >= 3 and line[2:3] == "]":
            line = line[3:].strip()
        if line:
            criteria.append(line)
    return criteria


def _evidence_resolves(task: dict, evidence: dict) -> tuple[bool, str]:
    kind = evidence.get("type")
    ref = evidence.get("ref")
    if kind == "check":
        latest = latest_verifications(task).get(ref)
        if latest is None:
            return False, "missing check"
        result = latest.get("result")
        return result == "passed", f"latest result={result}"
    if kind == "decision":
        current = {item.get("key"): item for item in active_decisions(task)}
        return ref in current, "active decision" if ref in current else "missing decision"
    if kind == "assumption":
        active, expired = assumption_status(task)
        active_keys = {item.get("key") for item in active}
        expired_keys = {item.get("key") for item in expired}
        if ref in active_keys:
            return True, "active assumption"
        if ref in expired_keys:
            return False, "expired assumption"
        return False, "missing assumption"
    if kind == "invariant":
        exists = any(item.get("text") == ref for item in task.get("invariants", []))
        return exists, "recorded invariant" if exists else "missing invariant"
    if kind == "observation":
        return bool(ref), "recorded observation"
    return False, "unknown evidence type"


def link_criterion_evidence(
    root: Path,
    task_id: str,
    criterion_index: int,
    evidence_type: str,
    ref: str,
    note: str | None = None,
) -> dict:
    if evidence_type not in EVIDENCE_TYPES:
        raise SystemExit(f"Unsupported evidence type: {evidence_type}")
    state = load_state(root)
    task = find_task(state, task_id)
    criteria = acceptance_criteria(root, task)
    if criterion_index < 1 or criterion_index > len(criteria):
        raise SystemExit(f"Criterion index must be between 1 and {len(criteria)}")
    ref = ref.strip()
    if not ref:
        raise SystemExit("Evidence reference must be non-empty")

    evidence = {
        "criterion_index": criterion_index,
        "criterion": criteria[criterion_index - 1],
        "type": evidence_type,
        "ref": ref,
        "created_at": iso_now(),
    }
    if note:
        evidence["note"] = note.strip()
    task.setdefault("criterion_evidence", []).append(evidence)
    save_state(root, state)
    print(f"Linked {evidence_type} evidence to criterion {criterion_index} on {task_id}")
    return evidence


def lineage_report(root: Path, task_id: str) -> dict:
    task = find_task(load_state(root), task_id)
    criteria = acceptance_criteria(root, task)
    links = task.get("criterion_evidence", [])
    rows: list[dict] = []
    unsupported: list[int] = []
    orphaned_links: list[dict] = []

    for index, criterion in enumerate(criteria, start=1):
        criterion_links = [
            item for item in links
            if item.get("criterion_index") == index and item.get("criterion") == criterion
        ]
        resolved_links: list[dict] = []
        for item in criterion_links:
            valid, detail = _evidence_resolves(task, item)
            rendered = dict(item)
            rendered["valid"] = valid
            rendered["detail"] = detail
            resolved_links.append(rendered)
        supported = any(item["valid"] for item in resolved_links)
        if not supported:
            unsupported.append(index)
        rows.append(
            {
                "index": index,
                "criterion": criterion,
                "supported": supported,
                "evidence": resolved_links,
            }
        )

    for item in links:
        index = item.get("criterion_index")
        text = item.get("criterion")
        if not isinstance(index, int) or index < 1 or index > len(criteria) or criteria[index - 1] != text:
            orphaned_links.append(item)

    return {
        "task_id": task_id,
        "criteria": rows,
        "unsupported": unsupported,
        "unsupported_count": len(unsupported),
        "orphaned_links": orphaned_links,
        "complete": bool(criteria) and not unsupported,
    }


def _task_history_paths(task: dict) -> list[str]:
    paths: list[str] = []
    for audit in task.get("guard_audits", []):
        paths.extend(audit.get("changed_files", []))
    paths.extend((task.get("memory_context") or {}).get("paths", []))
    return _unique(paths)


def component_risk_report(root: Path, task_id: str) -> dict:
    state = load_state(root)
    current_task = find_task(state, task_id)
    signals = task_signals(current_task)
    current_paths = signals["paths"]
    current_components = {item.lower() for item in signals["components"]}
    score = 0
    events: list[dict] = []

    for near_miss in relevant_near_misses(root, task_id):
        score += 3
        events.append(
            {
                "kind": "near_miss",
                "weight": 3,
                "source": near_miss.get("id"),
                "detail": near_miss.get("summary"),
            }
        )

    for task in state.get("tasks", []):
        if task.get("id") == task_id:
            continue
        historical_paths = _task_history_paths(task)
        path_related = any(
            _path_matches(old, current)
            for old in historical_paths
            for current in current_paths
        ) if current_paths and historical_paths else False
        historical_components = {item.lower() for item in task_signals(task)["components"]}
        component_related = bool(current_components & historical_components)
        if not path_related and not component_related:
            continue

        latest = latest_verifications(task)
        failures = [name for name, item in latest.items() if item.get("result") == "failed"]
        for check in failures:
            score += 1
            events.append(
                {
                    "kind": "failed_check",
                    "weight": 1,
                    "source": task.get("id"),
                    "detail": check,
                }
            )

        for audit in task.get("guard_audits", []):
            for violation in audit.get("violations", []):
                if violation.startswith(("protected_path:", "outside_scope:", "max_files:", "max_lines:")):
                    score += 2
                    events.append(
                        {
                            "kind": "guard_violation",
                            "weight": 2,
                            "source": task.get("id"),
                            "detail": violation,
                        }
                    )

    if score >= 9:
        level = "critical"
    elif score >= 5:
        level = "high"
    elif score >= 2:
        level = "elevated"
    else:
        level = "low"
    return {
        "task_id": task_id,
        "level": level,
        "score": score,
        "signals": signals,
        "events": events,
    }


def record_rollback_rehearsal(
    root: Path,
    task_id: str,
    restore_state: list[str] | None = None,
    irreversible: list[str] | None = None,
    migration: list[str] | None = None,
    verify: list[str] | None = None,
    contain: list[str] | None = None,
) -> dict:
    state = load_state(root)
    task = find_task(state, task_id)
    plan = task.setdefault(
        "rollback_rehearsal",
        {
            "restore_state": [],
            "irreversible_side_effects": [],
            "migration_downgrade": [],
            "verify_after_rollback": [],
            "containment": [],
        },
    )
    additions = {
        "restore_state": restore_state or [],
        "irreversible_side_effects": irreversible or [],
        "migration_downgrade": migration or [],
        "verify_after_rollback": verify or [],
        "containment": contain or [],
    }
    for key, values in additions.items():
        plan[key] = _unique(list(plan.get(key, [])) + list(values))
    plan["updated_at"] = iso_now()
    save_state(root, state)
    print(f"Updated rollback rehearsal for {task_id}")
    return plan


def rollback_packet(root: Path, task_id: str) -> dict:
    task = find_task(load_state(root), task_id)
    plan = task.get("rollback_rehearsal") or {}
    fields = {
        "restore_state": list(plan.get("restore_state", [])),
        "irreversible_side_effects": list(plan.get("irreversible_side_effects", [])),
        "migration_downgrade": list(plan.get("migration_downgrade", [])),
        "verify_after_rollback": list(plan.get("verify_after_rollback", [])),
        "containment": list(plan.get("containment", [])),
    }
    missing = [key for key, values in fields.items() if not values]
    try:
        git_head = run_git(root, ["rev-parse", "HEAD"]).strip() or None
    except SystemExit:
        git_head = None
    audits = task.get("guard_audits", [])
    changed_paths = audits[-1].get("changed_files", []) if audits else []
    return {
        "task_id": task_id,
        "git_head": git_head,
        "changed_paths": changed_paths,
        **fields,
        "missing_sections": missing,
        "rehearsal_complete": not missing,
    }


def render_rollback_markdown(packet: dict) -> str:
    def block(values: list[str], prompt: str) -> str:
        if values:
            return "\n".join(f"- {item}" for item in values)
        return f"- UNSPECIFIED — {prompt}"

    return f"""# Rollback rehearsal

Task: `{packet['task_id']}`  
Git HEAD: `{packet['git_head'] or 'unavailable'}`  
Rehearsal complete: **{'YES' if packet['rehearsal_complete'] else 'NO'}**

## State to restore
{block(packet['restore_state'], 'describe code/data/config state that must be restored')}

## Irreversible side effects
{block(packet['irreversible_side_effects'], 'identify side effects that rollback cannot automatically undo')}

## Migration / downgrade concerns
{block(packet['migration_downgrade'], 'describe schema, data, cache, protocol, or compatibility downgrade concerns')}

## Verification after rollback
{block(packet['verify_after_rollback'], 'state checks that prove rollback restored safe operation')}

## Containment steps
{block(packet['containment'], 'state how to limit impact while rollback is running')}

## Current changed paths
{block(packet['changed_paths'], 'no changed paths were recorded by a guard audit')}

A rollback rehearsal is a planning artifact. It does not execute rollback commands or prove that rollback will succeed.
"""


def promote_finding(
    root: Path,
    task_id: str,
    finding: str,
    target: str,
    *,
    key: str | None = None,
    value: str | None = None,
    source: str | None = None,
    ttl_minutes: int | None = None,
    check: str | None = None,
    failure_class: str | None = None,
    paths: list[str] | None = None,
    components: list[str] | None = None,
    risks: list[str] | None = None,
    mitigation: str | None = None,
) -> dict:
    finding = finding.strip()
    if not finding:
        raise SystemExit("Finding must be non-empty")
    if target not in PROMOTION_TYPES:
        raise SystemExit(f"Unsupported promotion target: {target}")

    result_ref: str
    if target == "invariant":
        add_invariant(root, task_id, finding)
        result_ref = finding
    elif target == "assumption":
        if not key or value is None:
            raise SystemExit("Assumption promotion requires --key and --value")
        record_assumption(
            root,
            task_id,
            key,
            value,
            source or f"promoted counterfactual: {finding}",
            ttl_minutes,
        )
        result_ref = key
    elif target == "verification-template":
        if not check:
            raise SystemExit("Verification-template promotion requires --check")
        state = load_state(root)
        task = find_task(state, task_id)
        template = {
            "check": check.strip(),
            "rationale": finding,
            "created_at": iso_now(),
        }
        task.setdefault("verification_templates", []).append(template)
        save_state(root, state)
        result_ref = check.strip()
    else:
        near_miss = record_near_miss(
            root,
            task_id,
            failure_class or "counterfactual-risk",
            finding,
            paths,
            components,
            risks,
            evidence=finding,
            mitigation=mitigation,
        )
        result_ref = near_miss["id"]

    state = load_state(root)
    task = find_task(state, task_id)
    promotion = {
        "target": target,
        "finding": finding,
        "result_ref": result_ref,
        "created_at": iso_now(),
    }
    task.setdefault("promotions", []).append(promotion)
    save_state(root, state)
    print(f"Promoted finding to {target}: {result_ref}")
    return promotion


def _print_json_or_lines(payload, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if isinstance(payload, list):
        if not payload:
            print("none")
            return
        for item in payload:
            print(f"{item.get('id')} score={item.get('match_score')} {item.get('summary')}")
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="antigravity-memory",
        description="Local failure memory, evidence lineage, risk recall, and rollback rehearsal",
    )
    p.add_argument("--root", default=".", help="Repository root (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    context = sub.add_parser("context", help="Add path/component/risk signals to a task")
    context.add_argument("task_id")
    context.add_argument("--path", action="append", default=[])
    context.add_argument("--component", action="append", default=[])
    context.add_argument("--risk", action="append", default=[])

    near = sub.add_parser("near-miss", help="Record or recall near-miss failures")
    near_sub = near.add_subparsers(dest="near_command", required=True)
    near_add = near_sub.add_parser("add")
    near_add.add_argument("task_id")
    near_add.add_argument("failure_class")
    near_add.add_argument("summary")
    near_add.add_argument("--path", action="append", default=[])
    near_add.add_argument("--component", action="append", default=[])
    near_add.add_argument("--risk", action="append", default=[])
    near_add.add_argument("--evidence")
    near_add.add_argument("--mitigation")
    near_rel = near_sub.add_parser("relevant")
    near_rel.add_argument("task_id")
    near_rel.add_argument("--path", action="append", default=[])
    near_rel.add_argument("--component", action="append", default=[])
    near_rel.add_argument("--risk", action="append", default=[])
    near_rel.add_argument("--json", action="store_true", dest="as_json")

    lineage = sub.add_parser("lineage", help="Link acceptance criteria to evidence")
    lineage_sub = lineage.add_subparsers(dest="lineage_command", required=True)
    link = lineage_sub.add_parser("link")
    link.add_argument("task_id")
    link.add_argument("criterion_index", type=int)
    link.add_argument("--type", dest="evidence_type", choices=EVIDENCE_TYPES, required=True)
    link.add_argument("--ref", required=True)
    link.add_argument("--note")
    report = lineage_sub.add_parser("report")
    report.add_argument("task_id")
    report.add_argument("--json", action="store_true", dest="as_json")

    risk = sub.add_parser("risk", help="Show deterministic component/path risk memory")
    risk.add_argument("task_id")
    risk.add_argument("--json", action="store_true", dest="as_json")

    rollback = sub.add_parser("rollback", help="Record or render rollback rehearsal")
    rollback_sub = rollback.add_subparsers(dest="rollback_command", required=True)
    rb_record = rollback_sub.add_parser("record")
    rb_record.add_argument("task_id")
    rb_record.add_argument("--restore-state", action="append", default=[])
    rb_record.add_argument("--irreversible", action="append", default=[])
    rb_record.add_argument("--migration", action="append", default=[])
    rb_record.add_argument("--verify", action="append", default=[])
    rb_record.add_argument("--contain", action="append", default=[])
    rb_packet = rollback_sub.add_parser("packet")
    rb_packet.add_argument("task_id")
    rb_packet.add_argument("--json", action="store_true", dest="as_json")
    rb_packet.add_argument("--output", type=Path)

    promote = sub.add_parser("promote", help="Promote a counterfactual finding into durable memory")
    promote.add_argument("task_id")
    promote.add_argument("--finding", required=True)
    promote.add_argument("--to", dest="target", choices=PROMOTION_TYPES, required=True)
    promote.add_argument("--key")
    promote.add_argument("--value")
    promote.add_argument("--source")
    promote.add_argument("--ttl-minutes", type=int)
    promote.add_argument("--check")
    promote.add_argument("--failure-class")
    promote.add_argument("--path", action="append", default=[])
    promote.add_argument("--component", action="append", default=[])
    promote.add_argument("--risk", action="append", default=[])
    promote.add_argument("--mitigation")
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "context":
        set_task_context(root, args.task_id, args.path, args.component, args.risk)
    elif args.command == "near-miss":
        if args.near_command == "add":
            record_near_miss(
                root, args.task_id, args.failure_class, args.summary,
                args.path, args.component, args.risk, args.evidence, args.mitigation,
            )
        else:
            _print_json_or_lines(
                relevant_near_misses(root, args.task_id, args.path, args.component, args.risk),
                args.as_json,
            )
    elif args.command == "lineage":
        if args.lineage_command == "link":
            link_criterion_evidence(
                root, args.task_id, args.criterion_index, args.evidence_type, args.ref, args.note,
            )
        else:
            payload = lineage_report(root, args.task_id)
            _print_json_or_lines(payload, args.as_json)
            if payload["unsupported_count"]:
                raise SystemExit(4)
    elif args.command == "risk":
        _print_json_or_lines(component_risk_report(root, args.task_id), args.as_json)
    elif args.command == "rollback":
        if args.rollback_command == "record":
            record_rollback_rehearsal(
                root, args.task_id, args.restore_state, args.irreversible,
                args.migration, args.verify, args.contain,
            )
        else:
            packet = rollback_packet(root, args.task_id)
            if args.as_json:
                text = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
            else:
                text = render_rollback_markdown(packet)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(text, encoding="utf-8")
                print(args.output)
            else:
                print(text, end="")
    elif args.command == "promote":
        promote_finding(
            root, args.task_id, args.finding, args.target,
            key=args.key, value=args.value, source=args.source, ttl_minutes=args.ttl_minutes,
            check=args.check, failure_class=args.failure_class, paths=args.path,
            components=args.component, risks=args.risk, mitigation=args.mitigation,
        )


if __name__ == "__main__":
    main()
