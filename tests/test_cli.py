import json
from pathlib import Path

from antigravity.cli import (
    complete_task,
    create_task,
    dependency_cycle_ids,
    init_repo,
    load_state,
    record_review,
    record_verification,
    save_state,
    show_status,
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
    state = load_state(tmp_path)
    task = state["tasks"][0]
    assert task["verifications"] == []
    assert task["depends_on"] == []

    record_review(
        tmp_path,
        task["id"],
        "warning",
        "Add a regression check for the 320px layout.",
        "src/navigation.css",
    )
    record_verification(
        tmp_path,
        task["id"],
        "pytest -q",
        "passed",
        "12 tests passed.",
    )
    state = load_state(tmp_path)
    assert state["tasks"][0]["verifications"][0]["result"] == "passed"

    complete_task(tmp_path, task["id"], "Verified with recorded checks.")
    assert "**Status:** complete" in task_path.read_text(encoding="utf-8")


def test_dependency_readiness_changes_after_prerequisite_completes(tmp_path: Path, capsys):
    init_repo(tmp_path)
    create_task(tmp_path, "Prepare schema", [], [])
    state = load_state(tmp_path)
    prerequisite = state["tasks"][0]

    dependent_path = create_task(
        tmp_path,
        "Build adapter",
        [],
        [],
        [prerequisite["id"]],
    )
    state = load_state(tmp_path)
    dependent = state["tasks"][1]
    assert dependent["depends_on"] == [prerequisite["id"]]
    assert f"`{prerequisite['id']}`" in dependent_path.read_text(encoding="utf-8")

    show_status(tmp_path)
    output = capsys.readouterr().out
    assert f"blocked={prerequisite['id']}" in output

    complete_task(tmp_path, prerequisite["id"], "Schema ready.")
    show_status(tmp_path)
    output = capsys.readouterr().out
    dependent_line = next(line for line in output.splitlines() if dependent["id"] in line)
    assert "ready" in dependent_line
    assert "blocked=" not in dependent_line


def test_missing_dependency_and_cycles_are_reported(tmp_path: Path, capsys):
    init_repo(tmp_path)
    create_task(tmp_path, "First", [], [])
    create_task(tmp_path, "Second", [], [])
    state = load_state(tmp_path)
    first, second = state["tasks"]
    first["depends_on"] = [second["id"]]
    second["depends_on"] = [first["id"]]
    save_state(tmp_path, state)

    assert dependency_cycle_ids(state["tasks"]) == {first["id"], second["id"]}
    show_status(tmp_path)
    output = capsys.readouterr().out
    assert output.count("blocked=cycle") == 2

    state = load_state(tmp_path)
    state["tasks"][0]["depends_on"] = []
    state["tasks"][1]["depends_on"] = ["missing-task"]
    save_state(tmp_path, state)
    show_status(tmp_path)
    output = capsys.readouterr().out
    second_line = next(line for line in output.splitlines() if second["id"] in line)
    assert "blocked=missing:missing-task" in second_line


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
    assert state["tasks"][0]["verifications"][0]["result"] == "failed"
    show_status(tmp_path)
