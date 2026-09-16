from datetime import timedelta
from pathlib import Path
import subprocess

from antigravity.cli import create_task, find_task, init_repo, load_state, save_state
from antigravity.guard import (
    add_invariant,
    assumption_status,
    audit_git,
    guard_packet,
    now_utc,
    record_assumption,
    set_change_policy,
)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def make_git_task(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Antigravity Test")
    init_repo(root)
    create_task(root, "Guard a small change", [], ["Stay inside declared scope"])
    task_id = load_state(root)["tasks"][0]["id"]
    (root / "src").mkdir()
    (root / "config" / "prod").mkdir(parents=True)
    (root / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    (root / "config" / "prod" / "settings.yml").write_text("safe: true\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    return task_id


def test_latest_assumption_expires_instead_of_falling_back_to_old_value(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_git_task(root)
    record_assumption(root, task_id, "api-version", "v1", "old docs", None)
    record_assumption(root, task_id, "api-version", "v2", "new docs", 30)

    state = load_state(root)
    task = find_task(state, task_id)
    task["assumptions"][-1]["expires_at"] = (now_utc() - timedelta(minutes=1)).isoformat()
    save_state(root, state)

    task = find_task(load_state(root), task_id)
    active, expired = assumption_status(task)
    assert active == []
    assert [item["key"] for item in expired] == ["api-version"]
    assert expired[0]["value"] == "v2"


def test_invariants_and_guard_packet_are_durable(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_git_task(root)
    add_invariant(root, task_id, "Public API remains backward-compatible")
    set_change_policy(root, task_id, ["src/**"], ["config/prod/**"], 2, 20)
    record_assumption(root, task_id, "schema", "v3", "schema docs", 60)

    packet = guard_packet(root, task_id)
    assert "Public API remains backward-compatible" in packet
    assert "`schema` = v3" in packet
    assert "src/**" in packet
    assert "config/prod/**" in packet


def test_clean_git_audit_ignores_antigravity_state(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_git_task(root)
    set_change_policy(root, task_id, ["src/**"], ["config/prod/**"], 2, 10)
    git(root, "add", ".")
    git(root, "commit", "-m", "record policy")

    (root / "src" / "app.py").write_text("print('v2')\nprint('ok')\n", encoding="utf-8")
    report = audit_git(root, task_id)
    assert report["clean"] is True
    assert report["changed_files"] == ["src/app.py"]
    assert report["violations"] == []

    # The audit wrote .antigravity/state.json, but a second audit should still ignore it.
    report2 = audit_git(root, task_id, record=False)
    assert report2["changed_files"] == ["src/app.py"]


def test_audit_flags_protected_out_of_scope_and_budget_changes(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_git_task(root)
    set_change_policy(root, task_id, ["src/**"], ["config/prod/**"], 2, 3)
    git(root, "add", ".")
    git(root, "commit", "-m", "record policy")

    (root / "src" / "app.py").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    (root / "config" / "prod" / "settings.yml").write_text("safe: false\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "extra.md").write_text("scope creep\n", encoding="utf-8")

    report = audit_git(root, task_id, record=False)
    assert report["clean"] is False
    assert "config/prod/settings.yml" in report["protected_changes"]
    assert "docs/extra.md" in report["outside_scope"]
    assert any(item.startswith("protected_path:") for item in report["violations"])
    assert any(item.startswith("outside_scope:") for item in report["violations"])
    assert any(item.startswith("max_files:") for item in report["violations"])
    assert any(item.startswith("max_lines:") for item in report["violations"])


def test_expired_assumption_makes_audit_non_clean(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_git_task(root)
    record_assumption(root, task_id, "remote-api", "supports-v2", "vendor docs", 5)
    state = load_state(root)
    task = find_task(state, task_id)
    task["assumptions"][-1]["expires_at"] = (now_utc() - timedelta(minutes=1)).isoformat()
    save_state(root, state)
    git(root, "add", ".")
    git(root, "commit", "-m", "record assumption")

    report = audit_git(root, task_id, record=False)
    assert report["clean"] is False
    assert "expired_assumption:remote-api" in report["violations"]
