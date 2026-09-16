from datetime import timedelta
from pathlib import Path
import subprocess

from antigravity.cli import create_task, find_task, init_repo, load_state, record_verification, save_state
from antigravity.coordination import record_approval, record_decision
from antigravity.guard import add_invariant, record_assumption, set_change_policy
from antigravity.proof import (
    build_release_proof,
    counterfactual_prompt,
    reproducibility_recipe,
    render_proof_markdown,
)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def make_task(root: Path, *, acceptance: str = "Release proof is reviewable") -> str:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Antigravity Test")
    init_repo(root)
    create_task(root, "Prove a release", ["Keep it local"], [acceptance])
    task_id = load_state(root)["tasks"][0]["id"]
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    return task_id


def test_release_proof_collects_coordination_guard_and_fresh_evidence(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_task(root)
    record_decision(root, task_id, "storage", "json", "portable local state")
    record_approval(root, task_id, "publish release notes", "maintainer", 60, "release prep")
    record_assumption(root, task_id, "api-contract", "stable", "contract docs", 60)
    add_invariant(root, task_id, "Core CLI remains local-first")
    set_change_policy(root, task_id, ["src/**"], ["config/prod/**"], 3, 50)
    git(root, "add", ".")
    git(root, "commit", "-m", "record release context")
    record_verification(root, task_id, "pytest -q", "passed", "all tests passed")

    proof = build_release_proof(root, task_id)
    assert proof["release_ready"] is True
    assert proof["verification_evidence"][0]["freshness"] == "fresh"
    assert proof["coordination"]["decisions"][0]["key"] == "storage"
    assert proof["coordination"]["active_approvals"][0]["scope"] == "publish release notes"
    assert proof["assumptions"]["active"][0]["key"] == "api-contract"
    assert proof["guard_audit"]["clean"] is True
    assert proof["context"]["git_head"]
    markdown = render_proof_markdown(proof)
    assert "Release ready: **YES**" in markdown
    assert "Proof digest" in markdown


def test_verification_becomes_stale_after_later_relevant_context_change(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_task(root)
    record_verification(root, task_id, "pytest -q", "passed", None)

    state = load_state(root)
    task = find_task(state, task_id)
    check_time = task["verifications"][-1]["created_at"]
    later = __import__("datetime").datetime.fromisoformat(check_time) + timedelta(seconds=2)
    task.setdefault("decisions", []).append(
        {
            "key": "database",
            "value": "sqlite",
            "reason": "changed after verification",
            "created_at": later.isoformat(),
        }
    )
    save_state(root, state)

    proof = build_release_proof(root, task_id)
    evidence = proof["verification_evidence"][0]
    assert evidence["freshness"] == "stale"
    assert "decision" in evidence["invalidators"]
    assert "stale_check:pytest -q" in proof["blockers"]
    assert proof["release_ready"] is False


def test_counterfactual_prompt_challenges_green_checks(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_task(root)
    record_verification(root, task_id, "pytest -q", "passed", "green")

    prompt = counterfactual_prompt(root, task_id, None, None)
    assert "Counterfactual release review" in prompt
    assert "False-green tests" in prompt
    assert "Missing negative cases" in prompt
    assert "Cheapest test or observation" in prompt
    assert "Do not invent test results" in prompt


def test_reproduction_recipe_redacts_credentials_and_secret_assignments(tmp_path: Path):
    root = tmp_path / "repo"
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    task_id = make_task(root, acceptance=f"Never expose API_KEY={secret}")
    record_assumption(root, task_id, "auth-token", secret, "TOKEN=github_pat_abcdefghijklmnopqrstuvwxyz", 60)
    record_verification(root, task_id, f"tool --token {secret}", "passed", f"Bearer {secret}")

    recipe = reproducibility_recipe(root, task_id)
    serialized = str(recipe)
    assert secret not in serialized
    assert "github_pat_abcdefghijklmnopqrstuvwxyz" not in serialized
    assert "[REDACTED]" in serialized
    assert all("value" not in item for item in recipe["assumptions"])


def test_guard_violation_blocks_release_proof(tmp_path: Path):
    root = tmp_path / "repo"
    task_id = make_task(root)
    set_change_policy(root, task_id, ["src/**"], ["src/app.py"], 2, 20)
    git(root, "add", ".")
    git(root, "commit", "-m", "record policy")
    record_verification(root, task_id, "pytest -q", "passed", None)
    (root / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")

    proof = build_release_proof(root, task_id)
    assert proof["release_ready"] is False
    assert any(item.startswith("guard:protected_path:src/app.py") for item in proof["blockers"])
