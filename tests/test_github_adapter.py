import json
from pathlib import Path

import pytest

from antigravity import github_adapter
from antigravity.cli import init_repo, load_state, record_verification


def test_run_gh_requires_cli(monkeypatch):
    monkeypatch.setattr(github_adapter.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="was not found"):
        github_adapter.run_gh(["issue", "view", "1"])


def test_run_gh_uses_argument_list_without_shell(monkeypatch):
    calls = {}

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(github_adapter.shutil, "which", lambda name: "/usr/bin/gh")

    def fake_run(args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(github_adapter.subprocess, "run", fake_run)
    assert github_adapter.run_gh(["issue", "view", "7"]) == "ok"
    assert calls["args"] == ["gh", "issue", "view", "7"]
    assert calls["kwargs"]["shell"] is False


def test_import_issue_records_source_metadata(tmp_path: Path, monkeypatch):
    init_repo(tmp_path)
    payload = {
        "number": 42,
        "title": "Fix race in release worker",
        "body": "The worker can publish the same release twice.",
        "url": "https://github.com/acme/tool/issues/42",
        "labels": [{"name": "bug"}, {"name": "release"}],
    }
    monkeypatch.setattr(github_adapter, "run_gh", lambda args: json.dumps(payload))

    task_path = github_adapter.import_issue(tmp_path, "acme/tool", 42)
    task = load_state(tmp_path)["tasks"][0]
    assert task["source"]["provider"] == "github"
    assert task["source"]["number"] == 42
    assert task["source"]["labels"] == ["bug", "release"]
    text = task_path.read_text(encoding="utf-8")
    assert "## Source" in text
    assert "https://github.com/acme/tool/issues/42" in text
    assert "The worker can publish the same release twice." in text


def test_pr_handoff_uses_local_task_state(tmp_path: Path, monkeypatch):
    init_repo(tmp_path)
    payload = {
        "number": 5,
        "title": "Improve retries",
        "body": "Retry transient failures once.",
        "url": "https://github.com/acme/tool/issues/5",
        "labels": [],
    }
    monkeypatch.setattr(github_adapter, "run_gh", lambda args: json.dumps(payload))
    github_adapter.import_issue(tmp_path, "acme/tool", 5)
    task = load_state(tmp_path)["tasks"][0]
    record_verification(tmp_path, task["id"], "pytest -q", "passed", "8 passed")

    handoff = github_adapter.pr_handoff(tmp_path, task["id"])
    assert "Improve retries" in handoff
    assert "https://github.com/acme/tool/issues/5" in handoff
    assert "**PASSED** `pytest -q` — 8 passed" in handoff
    assert "Review before using as a pull request description" in handoff
