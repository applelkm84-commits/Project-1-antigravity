from pathlib import Path

from antigravity.cli import init_repo, load_state, save_state
from antigravity.coordination import record_decision
from antigravity.memory import (
    component_risk_report,
    lineage_report,
    link_criterion_evidence,
    load_memory,
    promote_finding,
    record_near_miss,
    record_rollback_rehearsal,
    relevant_near_misses,
    rollback_packet,
    set_task_context,
)


def add_task(root: Path, task_id: str, title: str, criteria: list[str]) -> None:
    tasks = root / ".antigravity" / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    relative = f".antigravity/tasks/{task_id}.md"
    acceptance = "\n".join(f"- [ ] {item}" for item in criteria)
    (root / relative).write_text(
        f"# {title}\n\n## Objective\n{title}\n\n## Constraints\n- None\n\n"
        f"## Acceptance criteria\n{acceptance}\n\n## Review findings\nNone recorded.\n\n"
        "## Verification records\nNone recorded.\n\n## Completion notes\nPending.\n",
        encoding="utf-8",
    )
    state = load_state(root)
    state.setdefault("tasks", []).append(
        {
            "id": task_id,
            "title": title,
            "status": "planned",
            "path": relative,
            "created_at": "2026-09-17T00:00:00+00:00",
            "reviews": [],
            "verifications": [],
            "depends_on": [],
        }
    )
    save_state(root, state)


def test_near_miss_relevance_uses_paths_components_and_risks(tmp_path: Path):
    root = tmp_path / "repo"
    init_repo(root)
    add_task(root, "old", "Old payment change", ["Works"])
    add_task(root, "current", "Current payment change", ["Works"])

    set_task_context(root, "old", ["src/payments/api.py"], ["payments"], ["idempotency"])
    record_near_miss(
        root,
        "old",
        "duplicate-charge",
        "Retry path could charge twice",
        ["src/payments/api.py"],
        ["payments"],
        ["idempotency"],
        evidence="staging replay",
        mitigation="add idempotency key",
    )
    set_task_context(root, "current", ["src/payments/service.py"], ["payments"], ["idempotency"])

    matches = relevant_near_misses(root, "current")
    assert len(matches) == 1
    assert matches[0]["failure_class"] == "duplicate-charge"
    assert matches[0]["match_score"] >= 5
    assert any(reason.startswith("component:") for reason in matches[0]["match_reasons"])


def test_acceptance_lineage_reports_unsupported_until_latest_check_passes(tmp_path: Path):
    root = tmp_path / "repo"
    init_repo(root)
    add_task(root, "task", "Ship safely", ["Unit tests pass", "Rollback is verified"])

    state = load_state(root)
    task = state["tasks"][0]
    task["verifications"] = [
        {"check": "pytest -q", "result": "passed", "created_at": "2026-09-17T00:01:00+00:00"},
        {"check": "rollback-test", "result": "failed", "created_at": "2026-09-17T00:02:00+00:00"},
    ]
    save_state(root, state)

    link_criterion_evidence(root, "task", 1, "check", "pytest -q")
    link_criterion_evidence(root, "task", 2, "check", "rollback-test")
    report = lineage_report(root, "task")
    assert report["criteria"][0]["supported"] is True
    assert report["criteria"][1]["supported"] is False
    assert report["unsupported"] == [2]

    state = load_state(root)
    state["tasks"][0]["verifications"].append(
        {"check": "rollback-test", "result": "passed", "created_at": "2026-09-17T00:03:00+00:00"}
    )
    save_state(root, state)
    assert lineage_report(root, "task")["complete"] is True


def test_component_risk_memory_combines_near_misses_failed_checks_and_guard_history(tmp_path: Path):
    root = tmp_path / "repo"
    init_repo(root)
    add_task(root, "old", "Old auth work", ["Works"])
    add_task(root, "current", "New auth work", ["Works"])

    set_task_context(root, "old", ["src/auth/session.py"], ["auth"], ["session"])
    state = load_state(root)
    old = state["tasks"][0]
    old["verifications"] = [
        {"check": "auth regression", "result": "failed", "created_at": "2026-09-17T00:01:00+00:00"}
    ]
    old["guard_audits"] = [
        {
            "changed_files": ["src/auth/session.py"],
            "violations": ["outside_scope:src/auth/session.py"],
        }
    ]
    save_state(root, state)
    record_near_miss(
        root,
        "old",
        "session-leak",
        "Session survived logout",
        ["src/auth/session.py"],
        ["auth"],
        ["session"],
    )
    set_task_context(root, "current", ["src/auth/token.py"], ["auth"], ["session"])

    report = component_risk_report(root, "current")
    kinds = {event["kind"] for event in report["events"]}
    assert {"near_miss", "failed_check", "guard_violation"} <= kinds
    assert report["level"] in {"high", "critical"}
    assert report["score"] >= 6


def test_rollback_rehearsal_reports_missing_sections_then_becomes_complete(tmp_path: Path):
    root = tmp_path / "repo"
    init_repo(root)
    add_task(root, "task", "Deploy migration", ["Safe"])

    partial = record_rollback_rehearsal(root, "task", restore_state=["previous application image"])
    assert partial["restore_state"] == ["previous application image"]
    packet = rollback_packet(root, "task")
    assert packet["rehearsal_complete"] is False
    assert "migration_downgrade" in packet["missing_sections"]

    record_rollback_rehearsal(
        root,
        "task",
        irreversible=["emails already sent cannot be unsent"],
        migration=["run down migration after checking backward compatibility"],
        verify=["smoke test login and database reads"],
        contain=["disable write traffic during rollback"],
    )
    packet = rollback_packet(root, "task")
    assert packet["rehearsal_complete"] is True
    assert packet["missing_sections"] == []


def test_counterfactual_findings_can_be_promoted_to_durable_controls(tmp_path: Path):
    root = tmp_path / "repo"
    init_repo(root)
    add_task(root, "task", "Review checkout", ["Safe"])

    promote_finding(root, "task", "Never bypass payment signature validation", "invariant")
    promote_finding(
        root,
        "task",
        "Provider retry behavior may change",
        "assumption",
        key="provider-retry",
        value="retries at most 3 times",
        source="provider docs",
        ttl_minutes=60,
    )
    promote_finding(
        root,
        "task",
        "We do not test duplicate callback delivery",
        "verification-template",
        check="simulate duplicate callback",
    )
    promotion = promote_finding(
        root,
        "task",
        "A duplicate webhook could create duplicate fulfillment",
        "near-miss",
        failure_class="duplicate-fulfillment",
        paths=["src/checkout/webhook.py"],
        risks=["idempotency"],
        mitigation="persist webhook event ids",
    )

    task = load_state(root)["tasks"][0]
    assert any(item["text"] == "Never bypass payment signature validation" for item in task["invariants"])
    assert task["assumptions"][-1]["key"] == "provider-retry"
    assert task["verification_templates"][-1]["check"] == "simulate duplicate callback"
    assert len(task["promotions"]) == 4
    assert promotion["target"] == "near-miss"
    assert load_memory(root)["near_misses"][-1]["failure_class"] == "duplicate-fulfillment"


def test_decision_can_support_acceptance_criterion(tmp_path: Path):
    root = tmp_path / "repo"
    init_repo(root)
    add_task(root, "task", "Keep storage local", ["Storage choice is settled"])
    record_decision(root, "task", "storage", "sqlite", "local-first")
    link_criterion_evidence(root, "task", 1, "decision", "storage")
    assert lineage_report(root, "task")["complete"] is True
