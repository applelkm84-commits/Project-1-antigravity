import json
from pathlib import Path

from antigravity.cli import (
    complete_task,
    create_task,
    init_repo,
    load_state,
    record_review,
    record_verification,
    save_state,
)


def test_init_creates_policy_and_state(tmp_path: Path):
    init_repo(tmp_path)
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".antigravity" / "state.json").exists()
    state = load_state(tmp_path)
    assert state["version"] == 1
    assert state["tasks"] == []


def test_create_review_verify_and_complete_task(tmp_path: Path):
    init_repo(tmp_path)
    task_path = create_task(
        tmp_path,
        "Fix mobile navigation overlap",
        ["Do not change desktop navigation"],
        ["No overlap at 320px width"],
    )
    assert task_path.exists()
    state = load_state(tmp_path)
    assert len(state["tasks"]) == 1
    task = state["tasks"][0]
    assert task["status"] == "planned"
    assert task["verifications"] == []

    record_review(
        tmp_path,
        task["id"],
        "warning",
        "Add a regression check for the 320px layout.",
        "src/navigation.css",
    )
    record_review(
        tmp_path,
        task["id"],
        "info",
        "Document the responsive breakpoint.",
        None,
    )
    record_verification(
        tmp_path,
        task["id"],
        "pytest -q",
        "passed",
        "12 tests passed.",
    )
    record_verification(
        tmp_path,
        task["id"],
        "responsive check",
        "skipped",
        None,
    )

    state = load_state(tmp_path)
    task = state["tasks"][0]
    assert len(task["reviews"]) == 2
    assert task["reviews"][0]["severity"] == "warning"
    assert len(task["verifications"]) == 2
    assert task["verifications"][0]["check"] == "pytest -q"
    assert task["verifications"][0]["result"] == "passed"
    assert "note" not in task["verifications"][1]

    text = task_path.read_text(encoding="utf-8")
    assert text.count("## Review findings") == 1
    assert text.count("## Verification records") == 1
    assert "src/navigation.css" in text
    assert "Add a regression check" in text
    assert "**PASSED** `pytest -q` — 12 tests passed." in text
    assert "**SKIPPED** `responsive check`" in text

    complete_task(tmp_path, task["id"], "Verified with recorded checks.")
    state = json.loads((tmp_path / ".antigravity" / "state.json").read_text(encoding="utf-8"))
    assert state["tasks"][0]["status"] == "complete"
    text = task_path.read_text(encoding="utf-8")
    assert "**Status:** complete" in text
    assert "Verified with recorded checks." in text


def test_record_verification_is_backward_compatible(tmp_path: Path):
    init_repo(tmp_path)
    old_task_path = tmp_path / ".antigravity" / "tasks" / "legacy.md"
    old_task_path.write_text(
        "# Legacy\n\n## Verification\n- [ ] Relevant tests/checks executed\n\n## Completion notes\nPending.\n",
        encoding="utf-8",
    )
    state = load_state(tmp_path)
    state["tasks"] = [
        {
            "id": "legacy",
            "title": "Legacy task",
            "status": "planned",
            "path": ".antigravity/tasks/legacy.md",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    save_state(tmp_path, state)

    record_verification(
        tmp_path,
        "legacy",
        "python -m compileall .",
        "failed",
        "Syntax error",
    )

    state = load_state(tmp_path)
    verification = state["tasks"][0]["verifications"][0]
    assert verification["result"] == "failed"
    text = old_task_path.read_text(encoding="utf-8")
    assert "## Verification records" in text
    assert "**FAILED** `python -m compileall .` — Syntax error" in text
