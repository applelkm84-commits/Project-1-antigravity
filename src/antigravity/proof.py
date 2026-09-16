from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .cli import (
    dependency_cycle_ids,
    find_task,
    load_state,
    markdown_section,
    readiness_label,
)
from .coordination import (
    active_approvals,
    active_decisions,
    active_lease,
    context_fingerprint,
    latest_verifications,
    parse_time,
    reality_report,
)
from .guard import assumption_status, audit_git, run_git

PROOF_SCHEMA_VERSION = 1
SECRET_KEY_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|private[_-]?key)"
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{10,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{10,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{12,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
)
ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|private[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def redact_text(value: str) -> str:
    redacted = ASSIGNMENT_SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_value(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if SECRET_KEY_RE.search(str(key)):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact_value(item)
        return result
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def relevant_context_events(task: dict) -> list[tuple[datetime, str]]:
    events: list[tuple[datetime, str]] = []
    collections = (
        ("reviews", "review"),
        ("decisions", "decision"),
        ("assumptions", "assumption"),
        ("invariants", "invariant"),
    )
    for field, label in collections:
        for item in task.get(field, []):
            created_at = item.get("created_at")
            if isinstance(created_at, str):
                try:
                    events.append((parse_time(created_at), label))
                except ValueError:
                    continue
    policy = task.get("change_policy")
    if isinstance(policy, dict) and isinstance(policy.get("updated_at"), str):
        try:
            events.append((parse_time(policy["updated_at"]), "change_policy"))
        except ValueError:
            pass
    return sorted(events, key=lambda item: item[0])


def changed_file_mtimes(root: Path, files: list[str]) -> list[tuple[datetime, str]]:
    events: list[tuple[datetime, str]] = []
    for relative in files:
        path = root / relative
        try:
            if path.is_file():
                events.append((datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc), f"file:{relative}"))
        except OSError:
            continue
    return sorted(events, key=lambda item: item[0])


def verification_evidence(root: Path, task: dict, changed_files: list[str]) -> list[dict]:
    now = now_utc()
    context_events = relevant_context_events(task)
    file_events = changed_file_mtimes(root, changed_files)
    evidence: list[dict] = []
    for check, item in sorted(latest_verifications(task).items()):
        created_raw = item.get("created_at")
        try:
            created = parse_time(created_raw) if isinstance(created_raw, str) else None
        except ValueError:
            created = None
        invalidators: list[str] = []
        if created is not None:
            invalidators.extend(label for when, label in context_events if when > created)
            invalidators.extend(label for when, label in file_events if when > created)
            age_seconds = max(0, int((now - created).total_seconds()))
        else:
            age_seconds = None
            invalidators.append("missing_or_invalid_timestamp")
        freshness = "stale" if invalidators else "fresh"
        evidence.append(
            {
                "check": check,
                "result": item.get("result"),
                "created_at": created_raw,
                "age_seconds": age_seconds,
                "freshness": freshness,
                "invalidators": sorted(set(invalidators)),
                "note": item.get("note"),
            }
        )
    return evidence


def current_git_head(root: Path) -> str | None:
    try:
        value = run_git(root, ["rev-parse", "HEAD"]).strip()
    except SystemExit:
        return None
    return value or None


def proof_digest(payload: dict) -> str:
    stable = dict(payload)
    stable.pop("generated_at", None)
    stable.pop("proof_digest", None)
    encoded = json.dumps(stable, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_release_proof(root: Path, task_id: str, base: str | None = None) -> dict:
    state = load_state(root)
    task = find_task(state, task_id)
    task_path = root / task["path"]
    if not task_path.exists():
        raise SystemExit(f"Task Markdown is missing: {task['path']}")
    markdown = task_path.read_text(encoding="utf-8")
    task_by_id = {item.get("id"): item for item in state.get("tasks", []) if item.get("id")}
    readiness = readiness_label(task, task_by_id, dependency_cycle_ids(state.get("tasks", []))) or "complete"
    reality = reality_report(state, task)
    active_assumptions, expired_assumptions = assumption_status(task)

    try:
        guard = audit_git(root, task_id, base, record=False)
    except SystemExit as exc:
        guard = {
            "task_id": task_id,
            "base": base or "HEAD",
            "clean": False,
            "changed_files": [],
            "changed_file_count": 0,
            "changed_line_count": 0,
            "violations": [f"guard_audit_unavailable:{exc}"],
            "protected_changes": [],
            "outside_scope": [],
            "expired_assumptions": [item.get("key") for item in expired_assumptions],
        }

    verifications = verification_evidence(root, task, list(guard.get("changed_files", [])))
    stale_checks = [item["check"] for item in verifications if item["freshness"] != "fresh"]
    non_passing = [item["check"] for item in verifications if item.get("result") != "passed"]

    blockers = list(reality.get("blockers", []))
    evidence_debt = list(reality.get("evidence_debt", []))
    blockers.extend(f"guard:{item}" for item in guard.get("violations", []))
    blockers.extend(f"stale_check:{name}" for name in stale_checks)
    blockers.extend(f"non_passing_check:{name}" for name in non_passing)
    blockers = list(dict.fromkeys(blockers))
    evidence_debt = list(dict.fromkeys(evidence_debt))

    payload = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "generated_at": now_utc().isoformat(),
        "task": {
            "id": task_id,
            "title": task.get("title"),
            "status": task.get("status", "planned"),
            "objective": markdown_section(markdown, "Objective") or task.get("title", ""),
            "constraints": markdown_section(markdown, "Constraints") or "None recorded.",
            "acceptance_criteria": markdown_section(markdown, "Acceptance criteria") or "None recorded.",
            "readiness": readiness,
            "source": redact_value(task.get("source")),
        },
        "coordination": {
            "decisions": redact_value(active_decisions(task)),
            "active_approvals": redact_value(active_approvals(task)),
            "active_lease": redact_value(active_lease(task)),
            "lease_history": redact_value(task.get("lease_history", [])),
        },
        "assumptions": {
            "active": redact_value(active_assumptions),
            "expired": redact_value(expired_assumptions),
        },
        "invariants": redact_value(task.get("invariants", [])),
        "verification_evidence": redact_value(verifications),
        "guard_audit": redact_value(guard),
        "reality": redact_value(reality),
        "context": {
            "coordination_fingerprint": context_fingerprint(task),
            "git_head": current_git_head(root),
        },
        "release_ready": not blockers and not evidence_debt,
        "blockers": blockers,
        "evidence_debt": evidence_debt,
    }
    payload["proof_digest"] = proof_digest(payload)
    return payload


def render_proof_markdown(proof: dict) -> str:
    task = proof["task"]
    checks = proof["verification_evidence"]
    decisions = proof["coordination"]["decisions"]
    approvals = proof["coordination"]["active_approvals"]
    active_assumptions = proof["assumptions"]["active"]
    expired_assumptions = proof["assumptions"]["expired"]
    invariants = proof["invariants"]
    guard = proof["guard_audit"]

    def lines(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "- None"

    check_lines = []
    for item in checks:
        age = f"{item['age_seconds']}s" if item.get("age_seconds") is not None else "unknown"
        suffix = ""
        if item.get("invalidators"):
            suffix = f" — invalidated by: {', '.join(item['invalidators'])}"
        check_lines.append(
            f"`{item['check']}` — {item.get('result')} — {item['freshness']} — age {age}{suffix}"
        )
    decision_lines = [f"`{item.get('key')}` = {item.get('value')}" for item in decisions]
    approval_lines = [f"{item.get('scope')} — by {item.get('approved_by')}" for item in approvals]
    assumption_lines = [
        f"`{item.get('key')}` = {item.get('value')}" + (f" — source: {item.get('source')}" if item.get("source") else "")
        for item in active_assumptions
    ]
    expired_lines = [f"`{item.get('key')}` expired at {item.get('expires_at')}" for item in expired_assumptions]
    invariant_lines = [item.get("text", "") for item in invariants]

    return f"""# Antigravity Release Proof

Task: `{task['id']}` — {task.get('title') or ''}  
Generated: {proof['generated_at']}  
Release ready: **{'YES' if proof['release_ready'] else 'NO'}**  
Proof digest: `{proof['proof_digest']}`  
Context fingerprint: `{proof['context']['coordination_fingerprint']}`  
Git HEAD: `{proof['context']['git_head'] or 'unavailable'}`

## Objective
{task.get('objective') or 'None recorded.'}

## Acceptance criteria
{task.get('acceptance_criteria') or 'None recorded.'}

## Release blockers
{lines(proof['blockers'])}

## Evidence debt
{lines(proof['evidence_debt'])}

## Verification freshness
{lines(check_lines)}

## Guard / blast radius
- Clean: {'yes' if guard.get('clean') else 'no'}
- Changed files: {guard.get('changed_file_count', 0)}
- Changed lines: {guard.get('changed_line_count', 0)}
- Violations: {', '.join(guard.get('violations', [])) or 'none'}

### Changed paths
{lines(list(guard.get('changed_files', [])))}

## Settled decisions
{lines(decision_lines)}

## Active approval receipts
{lines(approval_lines)}

## Active assumptions
{lines(assumption_lines)}

## Expired assumptions
{lines(expired_lines)}

## Protected invariants
{lines(invariant_lines)}

## Lease state
{json.dumps(proof['coordination']['active_lease'], ensure_ascii=False) if proof['coordination']['active_lease'] else 'No active lease'}

## Interpretation
This artifact proves only what is recorded here. A green proof is evidence of consistency, freshness, and declared-scope checks; it is not a guarantee that the software is correct or secure.
"""


def write_release_proof(
    root: Path,
    task_id: str,
    json_output: Path | None,
    markdown_output: Path | None,
    base: str | None,
) -> dict:
    proof = build_release_proof(root, task_id, base)
    markdown = render_proof_markdown(proof)
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(proof, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json_output)
    if markdown_output:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown, encoding="utf-8")
        print(markdown_output)
    if not json_output and not markdown_output:
        print(markdown, end="")
    return proof


def counterfactual_prompt(root: Path, task_id: str, output: Path | None, base: str | None) -> str:
    proof = build_release_proof(root, task_id, base)
    checks = "\n".join(
        f"- `{item['check']}`: {item.get('result')} / {item.get('freshness')}"
        for item in proof["verification_evidence"]
    ) or "- None recorded"
    changed = "\n".join(f"- {path}" for path in proof["guard_audit"].get("changed_files", [])) or "- None"
    assumptions = "\n".join(
        f"- `{item.get('key')}` from {item.get('source') or 'unspecified source'}"
        for item in proof["assumptions"]["active"]
    ) or "- None"
    invariants = "\n".join(f"- {item.get('text')}" for item in proof["invariants"]) or "- None"

    prompt = f"""# Counterfactual release review

You are the skeptical reviewer for task `{task_id}`.
Assume every currently green recorded check is truthful and passed. Your job is **not** to repeat those checks. Your job is to find plausible ways the release could still be wrong despite them.

Proof digest: {proof['proof_digest']}
Release-ready according to recorded evidence: {'yes' if proof['release_ready'] else 'no'}
Current blockers: {', '.join(proof['blockers']) or 'none'}
Evidence debt: {', '.join(proof['evidence_debt']) or 'none'}

## Objective
{proof['task']['objective']}

## Acceptance criteria
{proof['task']['acceptance_criteria']}

## Recorded checks
{checks}

## Changed paths
{changed}

## Active assumptions by source
{assumptions}

## Protected invariants
{invariants}

## Attack the green result
Look specifically for:
1. **False-green tests** — a check can pass while asserting the wrong thing, using the wrong fixture, or skipping a path.
2. **Missing negative cases** — malformed input, retries, partial failure, empty state, concurrency, timeout, rollback, cancellation, idempotency.
3. **Assumption failure** — an external fact, API behavior, environment property, or requirement may be wrong or expired.
4. **Trust-boundary/security blind spots** — untrusted text, path handling, subprocess arguments, credentials, serialization, privilege boundaries.
5. **State/migration/rollback risk** — new state may be readable but old state, downgrade, replay, duplicate execution, or partial write may fail.
6. **Scope drift** — a change may be technically correct but violate an invariant or alter behavior outside the requested area.
7. **Stale coordination** — the implementation may have been based on an older decision, approval, task snapshot, or dependency state.

## Required output
Return 3-7 **specific falsifiable hypotheses**, ordered by potential impact. For each:
- Failure hypothesis
- Why current green evidence might miss it
- Cheapest test or observation that would falsify the hypothesis
- Likely affected path/component
- Rollback or containment consideration

Then finish with:
- Highest-value missing test
- Highest-value manual inspection
- Release recommendation: `proceed`, `proceed-with-known-risk`, or `hold`

Do not invent test results. Treat this as a pre-mortem, not a confidence speech.
"""
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(prompt, encoding="utf-8")
        print(output)
    else:
        print(prompt, end="")
    return prompt


def reproducibility_recipe(root: Path, task_id: str, base: str | None = None) -> dict:
    proof = build_release_proof(root, task_id, base)
    checks = [redact_text(str(item["check"])) for item in proof["verification_evidence"]]
    assumptions = [
        {
            "key": redact_text(str(item.get("key", ""))),
            "source": redact_text(str(item.get("source", ""))) if item.get("source") else None,
            "expires_at": item.get("expires_at"),
        }
        for item in proof["assumptions"]["active"]
    ]
    recipe = {
        "schema_version": 1,
        "task_id": task_id,
        "title": redact_text(str(proof["task"].get("title") or "")),
        "git_head": proof["context"].get("git_head"),
        "objective": redact_text(str(proof["task"].get("objective") or "")),
        "constraints": redact_text(str(proof["task"].get("constraints") or "")),
        "acceptance_criteria": redact_text(str(proof["task"].get("acceptance_criteria") or "")),
        "changed_files": [redact_text(path) for path in proof["guard_audit"].get("changed_files", [])],
        "assumptions": assumptions,
        "invariants": [redact_text(str(item.get("text", ""))) for item in proof["invariants"]],
        "verification_commands": checks,
        "steps": [
            "Checkout the commit/ref under review in an isolated working tree.",
            "Use the project's documented runtime/toolchain; for Antigravity itself: python -m pip install -e .",
            "Recreate only the non-secret preconditions named in the assumptions list; obtain credentials separately from your normal secret store if a test genuinely requires them.",
            "Run each verification command exactly as recorded, reviewing the command before execution.",
            f"Run: antigravity-guard audit {task_id} --base {base or 'HEAD'} --no-record",
            "Compare observed behavior against the acceptance criteria and protected invariants.",
        ],
        "redaction_notice": "Known secret-like assignments and common credential/token formats are omitted or replaced with [REDACTED]. The recipe intentionally does not export credential material.",
    }
    return redact_value(recipe)


def render_recipe_markdown(recipe: dict) -> str:
    assumptions = "\n".join(
        f"- `{item['key']}`" + (f" — source: {item['source']}" if item.get("source") else "")
        for item in recipe["assumptions"]
    ) or "- None"
    checks = "\n".join(f"- `{item}`" for item in recipe["verification_commands"]) or "- None"
    files = "\n".join(f"- `{item}`" for item in recipe["changed_files"]) or "- None"
    steps = "\n".join(f"{index}. {item}" for index, item in enumerate(recipe["steps"], 1))
    return f"""# Minimal Reproduction Recipe

Task: `{recipe['task_id']}` — {recipe['title']}  
Git HEAD: `{recipe.get('git_head') or 'unavailable'}`

## Objective
{recipe['objective']}

## Acceptance criteria
{recipe['acceptance_criteria']}

## Changed files
{files}

## Non-secret assumptions to recreate
{assumptions}

## Recorded verification commands
{checks}

## Steps
{steps}

## Redaction
{recipe['redaction_notice']}
"""


def write_recipe(root: Path, task_id: str, output: Path | None, as_json: bool, base: str | None) -> dict:
    recipe = reproducibility_recipe(root, task_id, base)
    text = json.dumps(recipe, indent=2, ensure_ascii=False) + "\n" if as_json else render_recipe_markdown(recipe)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(output)
    else:
        print(text, end="")
    return recipe


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="antigravity-proof",
        description="Release proof bundles, evidence freshness, counterfactual review, and reproducibility recipes",
    )
    p.add_argument("--root", default=".", help="Repository root (default: current directory)")
    sub = p.add_subparsers(dest="command", required=True)

    bundle = sub.add_parser("bundle", help="Build a release proof from current local evidence")
    bundle.add_argument("task_id")
    bundle.add_argument("--base", help="Git base ref for the local blast-radius audit (default: HEAD)")
    bundle.add_argument("--json-out", type=Path)
    bundle.add_argument("--markdown-out", type=Path)

    counter = sub.add_parser("counterfactual", help="Generate a skeptical review prompt for apparently-green work")
    counter.add_argument("task_id")
    counter.add_argument("--base")
    counter.add_argument("--output", type=Path)

    recipe = sub.add_parser("repro", help="Generate a redacted minimal reproduction recipe")
    recipe.add_argument("task_id")
    recipe.add_argument("--base")
    recipe.add_argument("--json", action="store_true", dest="as_json")
    recipe.add_argument("--output", type=Path)
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "bundle":
        proof = write_release_proof(root, args.task_id, args.json_out, args.markdown_out, args.base)
        if not proof["release_ready"]:
            raise SystemExit(4)
    elif args.command == "counterfactual":
        counterfactual_prompt(root, args.task_id, args.output, args.base)
    elif args.command == "repro":
        write_recipe(root, args.task_id, args.output, args.as_json, args.base)


if __name__ == "__main__":
    main()
