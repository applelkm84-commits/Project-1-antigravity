import json
from pathlib import Path

from antigravity.cli import complete_task, create_task, init_repo, load_state, record_review


def test_init_creates_policy_and_state(tmp_path: Path):
    init_repo(tmp_path)
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".antigravity" / "state.json").exists()
    state = load_state(tmp_path)
    assert state["version"] == 1
    assert state["tasks"] == []


def test_create_review_and_complete_task(tmp_path: Path):
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

    record_review(
        tmp_path,
        task["id"],
        "warning",
        "Add a regression check for the 320px layout.",
        "src/navigation.css",
    )
    state = load_state(tmp_path)
    assert state["tasks"][0]["reviews"][0]["severity"] == "warning"
    text = task_path.read_text(encoding="utf-8")
    assert "src/navigation.css" in text
    assert "Add a regression check" in text

    complete_task(tmp_path, task["id"], "Verified with responsive checks.")
    state = json.loads((tmp_path / ".antigravity" / "state.json").read_text(encoding="utf-8"))
    assert state["tasks"][0]["status"] == "complete"
    text = task_path.read_text(encoding="utf-8")
    assert "**Status:** complete" in text
    assert "Verified with responsive checks." in text
