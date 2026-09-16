from datetime import timedelta
from pathlib import Path

import pytest

from antigravity.cli import create_task, find_task, init_repo, load_state, record_review, record_verification, save_state
from antigravity.coordination import (
    active_approvals,
    active_decisions,
    active_lease,
    check_context,
    claim_task,
    context_fingerprint,
    coordination_prompt,
    now_utc,
    reality_report,
    record_approval,
    record_decision,
    release_task,
    revoke_approval,
)


def make_task(root: Path) -> str:
    init_repo(root)
    create_task(root, "Ship safe release", ["Do not change the public API"], ["Tests pass"])
    return load_state(root)["tasks"][0]["id"]


def test_keyed_decisions_keep_history_but_latest_value_is_active(tmp_path: Path):
    task_id = make_task(tmp_path)
    record_decision(tmp_path, task_id, "database", "sqlite", "Small local state")
    record_decision(tmp_path, task_id, "database", "postgres", "Multi-user requirement")

    task = find_task(load_state(tmp_path), task_id)
    assert len(task["decisions"]) == 2
    active = active_decisions(task)
    assert len(active) == 1
    assert active[0]["key"] == "database"
    assert active[0]["value"] == "postgres"


def test_approval_receipts_expire_and_can_be_revoked(tmp_path: Path):
    task_id = make_task(tmp_path)
    record_approval(tmp_path, task_id, "publish release", "maintainer", 60, "Approved after review")
    task = find_task(load_state(tmp_path), task_id)
    assert len(active_approvals(task)) == 1

    revoke_approval(tmp_path, task_id, "publish release", "maintainer")
    task = find_task(load_state(tmp_path), task_id)
    assert active_approvals(task) == []

    record_approval(tmp_path, task_id, "temporary", "maintainer", 5, None)
    state = load_state(tmp_path)
    task = find_task(state, task_id)
    task["approvals"][-1]["expires_at"] = (now_utc() - timedelta(minutes=1)).isoformat()
    save_state(tmp_path, state)
    task = find_task(load_state(tmp_path), task_id)
    assert active_approvals(task) == []


def test_expiring_lease_prevents_agent_collision_and_allows_reclaim(tmp_path: Path):
    task_id = make_task(tmp_path)
    claim_task(tmp_path, task_id, "builder-a", 30)
    task = find_task(load_state(tmp_path), task_id)
    assert active_lease(task)["owner"] == "builder-a"

    with pytest.raises(SystemExit, match="already claimed"):
        claim_task(tmp_path, task_id, "builder-b", 30)

    state = load_state(tmp_path)
    task = find_task(state, task_id)
    task["lease"]["expires_at"] = (now_utc() - timedelta(minutes=1)).isoformat()
    save_state(tmp_path, state)

    claim_task(tmp_path, task_id, "builder-b", 30)
    task = find_task(load_state(tmp_path), task_id)
    assert active_lease(task)["owner"] == "builder-b"
    release_task(tmp_path, task_id, "builder-b")
    task = find_task(load_state(tmp_path), task_id)
    assert active_lease(task) is None
    assert task["lease_history"]


def test_fingerprint_detects_stale_context(tmp_path: Path):
    task_id = make_task(tmp_path)
    task = find_task(load_state(tmp_path), task_id)
    before = context_fingerprint(task)
    assert check_context(tmp_path, task_id, before)

    record_decision(tmp_path, task_id, "strategy", "minimal patch", None)
    task = find_task(load_state(tmp_path), task_id)
    after = context_fingerprint(task)
    assert after != before
    assert not check_context(tmp_path, task_id, before)


def test_reality_report_exposes_evidence_debt_and_latest_failed_checks(tmp_path: Path):
    task_id = make_task(tmp_path)
    state = load_state(tmp_path)
    task = find_task(state, task_id)
    report = reality_report(state, task)
    assert report["finish_ready"] is False
    assert "no_verification_records" in report["evidence_debt"]

    record_verification(tmp_path, task_id, "pytest -q", "failed", "1 failed")
    state = load_state(tmp_path)
    task = find_task(state, task_id)
    report = reality_report(state, task)
    assert "failed_check=pytest -q" in report["blockers"]

    record_verification(tmp_path, task_id, "pytest -q", "passed", "9 passed")
    state = load_state(tmp_path)
    task = find_task(state, task_id)
    report = reality_report(state, task)
    assert report["finish_ready"] is True
    assert report["blockers"] == []
    assert report["evidence_debt"] == []

    record_review(tmp_path, task_id, "error", "Security regression", "src/auth.py")
    state = load_state(tmp_path)
    task = find_task(state, task_id)
    report = reality_report(state, task)
    assert report["finish_ready"] is False
    assert "error_review_findings=1" in report["blockers"]


def test_coordination_prompt_includes_receipts_lease_reality_and_fingerprint(tmp_path: Path):
    task_id = make_task(tmp_path)
    record_decision(tmp_path, task_id, "strategy", "smallest reversible change", "Limit blast radius")
    record_approval(tmp_path, task_id, "edit source files", "maintainer", None, None)
    claim_task(tmp_path, task_id, "builder-a", 30)
    record_verification(tmp_path, task_id, "pytest -q", "passed", "9 passed")

    task = find_task(load_state(tmp_path), task_id)
    fingerprint = context_fingerprint(task)
    prompt = coordination_prompt(tmp_path, task_id, "builder")
    assert fingerprint in prompt
    assert "`strategy` = smallest reversible change" in prompt
    assert "edit source files — approved by maintainer" in prompt
    assert "Owned by builder-a" in prompt
    assert "Finish ready: yes" in prompt
    assert "Do not re-ask" in prompt
