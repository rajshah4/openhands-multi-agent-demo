"""Offline contract tests for the two patterns. No API key or network needed.

Run: python3 -m pytest -q
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "patterns" / "common"
PARENT_CHILD = ROOT / "patterns" / "parent-child"
POLLING = ROOT / "patterns" / "polling"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(COMMON))
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def test_contract_parser_reads_status_lines() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    text = "Long analysis here.\n\n```text\nstatus: done\nsummary: all criteria met\nnext_gate: check\n```\n"
    contract = oh.parse_contract(text)
    assert contract["status"] == "done"
    assert contract["summary"] == "all criteria met"
    assert contract["next_gate"] == "check"


def test_contract_parser_keeps_first_status() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    contract = oh.parse_contract("status: pass\nnoise\nstatus: failed\n")
    assert contract["status"] == "pass"


def test_start_payload_shape() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    payload = oh.build_start_payload(prompt="do the thing", title="t", repository="owner/repo")
    assert payload["initial_message"]["content"][0]["text"] == "do the thing"
    assert payload["initial_message"]["run"] is True
    assert payload["selected_repository"] == "owner/repo"
    assert "llm_model" not in payload


# ---------------------------------------------------------------------------
# Runtime parity: cloud and canvas backends expose the same surface
# ---------------------------------------------------------------------------

RUNTIME_SURFACE = (
    "base_url",
    "read_api_key",
    "build_start_payload",
    "start_worker",
    "get_status",
    "get_final",
    "conversation_url",
    "TERMINAL_EXECUTION_STATUSES",
)


def test_runtime_modules_expose_the_same_surface() -> None:
    cloud = load_module(COMMON / "openhands_conversations.py")
    canvas = load_module(COMMON / "canvas_conversations.py")
    for name in RUNTIME_SURFACE:
        assert hasattr(cloud, name), f"cloud runtime missing {name}"
        assert hasattr(canvas, name), f"canvas runtime missing {name}"


def test_canvas_payload_shape() -> None:
    canvas = load_module(COMMON / "canvas_conversations.py")
    payload = canvas.build_start_payload(prompt="do the thing", title="t", workspace_dir="/tmp/w")
    assert payload["initial_message"]["content"][0]["text"] == "do the thing"
    assert payload["secrets_encrypted"] is True
    assert payload["worktree"] is False
    assert payload["workspace"] == {"kind": "LocalWorkspace", "working_dir": "/tmp/w"}


# ---------------------------------------------------------------------------
# Parent-child pattern
# ---------------------------------------------------------------------------

def test_parent_child_workcell_prompts_have_contract_sections() -> None:
    prompts = sorted((PARENT_CHILD / "prompts" / "workcells").glob("*.md"))
    assert {path.stem for path in prompts} == {"plan", "build", "check"}
    for path in prompts:
        text = path.read_text(encoding="utf-8")
        assert "## Inputs" in text
        assert "## What You Do" in text
        assert "## Boundaries" in text
        assert "## Output Contract" in text
        assert "status:" in text
        assert "{{run_id}}" in text
        assert "final response" in text.lower()  # the sandbox/state-model teaching point


def test_parent_child_gate_vocabulary_matches_prompts() -> None:
    module = load_module(PARENT_CHILD / "run_supervisor.py")
    assert module.DEFAULT_CELLS == ("plan", "build", "check")
    assert module.CONTINUE_STATUSES["check"] == {"pass", "findings"}


def test_parent_child_dry_run_writes_run_dir(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(PARENT_CHILD / "run_supervisor.py"), "--dry-run", "--run-id", "test-dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "dry-run"' in result.stdout
    run_dir = PARENT_CHILD / "runs" / "test-dry-run"
    assert (run_dir / "lifecycle-report.md").exists()
    assert (run_dir / "plan.prompt.md").exists()
    # cleanup
    for path in sorted(run_dir.glob("*")):
        path.unlink()
    run_dir.rmdir()


# ---------------------------------------------------------------------------
# Polling-loop pattern
# ---------------------------------------------------------------------------

def test_polling_backlog_seed_is_valid() -> None:
    seed = json.loads((POLLING / "backlog.json").read_text(encoding="utf-8"))
    assert len(seed["tasks"]) >= 3
    for task in seed["tasks"]:
        assert task["id"] and task["prompt"]


def test_polling_worker_prompt_has_contract() -> None:
    text = (POLLING / "prompts" / "worker.md").read_text(encoding="utf-8")
    assert "{{task_id}}" in text
    assert "{{task_prompt}}" in text
    assert "status: done | failed" in text
    assert "final response" in text.lower()


def test_polling_dry_run_mutates_nothing() -> None:
    state_file = POLLING / "state.json"
    worklog = POLLING / "WORKLOG.md"
    state_before = state_file.read_text(encoding="utf-8") if state_file.exists() else None
    worklog_before = worklog.read_text(encoding="utf-8") if worklog.exists() else None
    result = subprocess.run(
        [sys.executable, str(POLLING / "orchestrate_once.py"), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert outcome["action"] in {"dry-run", "quiet", "needs-human"}
    state_after = state_file.read_text(encoding="utf-8") if state_file.exists() else None
    worklog_after = worklog.read_text(encoding="utf-8") if worklog.exists() else None
    assert state_after == state_before, "--dry-run must not mutate state.json"
    assert worklog_after == worklog_before, "--dry-run must not append to WORKLOG.md"
