import json
from pathlib import Path

import pytest

from antigravity.cli import (
    BUNDLE_SCHEMA_VERSION,
    complete_task,
    create_task,
    dependency_cycle_ids,
    export_task,
    import_task,
    init_repo,
    load_state,
    record_review,
    record_verification,
    save_state,
    show_status,
)


def test_init_creates_policy_and_state(tmp_path: Path):
    init_repo(tmp_path)
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
    complete_task(tmp_path, task["id"], "Verified with recorded checks.")
    assert "**Status:** complete" in task_path.read_text(encoding="utf-8")


def test_dependency_readiness_changes_after_prerequisite_completes(tmp_path: Path, capsys):
    init_repo(tmp_path)
    create_task(tmp_path, "Prepare schema", [], [])
    state = load_state(tmp_path)
    prerequisite = state["tasks"][0]
    create_task(tmp_path, "Build adapter", [], [], [prerequisite["id"]])
    dependent = load_state(tmp_path)["tasks"][1]

    show_status(tmp_path)
    assert f"blocked={prerequisite['id']}" in capsys.readouterr().out

    complete_task(tmp_path, prerequisite["id"], "Schema ready.")
    show_status(tmp_path)
    dependent_line = next(line for line in capsys.readouterr().out.splitlines() if dependent["id"] in line)
    assert "ready" in dependent_line


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
    assert capsys.readouterr().out.count("blocked=cycle") == 2


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
    assert load_state(tmp_path)["tasks"][0]["verifications"][0]["result"] == "failed"


def test_task_bundle_round_trip(tmp_path: Path):
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    init_repo(source_root)
    init_repo(target_root)

    task_path = create_task(
        source_root,
        "Portable task",
        ["Keep it local"],
        ["Round trip succeeds"],
        ["upstream-task"],
    )
    task = load_state(source_root)["tasks"][0]
    record_review(source_root, task["id"], "info", "Portable review", None)
    record_verification(source_root, task["id"], "pytest -q", "passed", "5 passed")

    bundle_path = tmp_path / "bundle.json"
    export_task(source_root, task["id"], bundle_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == BUNDLE_SCHEMA_VERSION

    imported_path = import_task(target_root, bundle_path)
    imported = load_state(target_root)["tasks"][0]
    original = load_state(source_root)["tasks"][0]
    assert imported["id"] == original["id"]
    assert imported["depends_on"] == ["upstream-task"]
    assert imported["reviews"] == original["reviews"]
    assert imported["verifications"] == original["verifications"]
    assert imported_path.read_text(encoding="utf-8") == task_path.read_text(encoding="utf-8")

    with pytest.raises(SystemExit, match="Task already exists"):
        import_task(target_root, bundle_path)


def test_task_bundle_rejects_unsafe_id_and_unknown_schema(tmp_path: Path):
    root = tmp_path / "target"
    init_repo(root)
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "schema_version": BUNDLE_SCHEMA_VERSION,
                "task": {"id": "../escape", "title": "Bad", "status": "planned"},
                "markdown": "# Bad\n",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="unsafe task id"):
        import_task(root, bundle)

    bundle.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "task": {"id": "safe", "title": "Safe", "status": "planned"},
                "markdown": "# Safe\n",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="Unsupported task bundle schema"):
        import_task(root, bundle)
