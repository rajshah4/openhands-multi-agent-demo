"""Offline contract tests for the two patterns. No API key or network needed.

Run: python3 -m pytest -q
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_contract_parser_rejects_conflicting_status() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    with pytest.raises(oh.ContractError):
        oh.parse_contract("status: pass\nnoise\nstatus: failed\n")


def test_start_payload_shape() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    payload = oh.build_start_payload(prompt="do the thing", title="t", repository="owner/repo")
    assert payload["initial_message"]["content"][0]["text"] == "do the thing"
    assert payload["initial_message"]["run"] is True
    assert payload["selected_repository"] == "owner/repo"
    assert "llm_model" not in payload


def test_cloud_start_payload_accepts_agent_profile() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    payload = oh.build_start_payload(
        prompt="do the thing",
        title="t",
        agent_profile_id="profile-acp",
    )
    assert payload["agent_profile_id"] == "profile-acp"
    with pytest.raises(ValueError):
        oh.build_start_payload(
            prompt="do the thing",
            title="t",
            llm_model="example/model",
            agent_profile_id="profile-acp",
        )


def test_cloud_payload_accepts_explicit_sandbox_and_scoped_secrets() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    payload = oh.build_start_payload(
        prompt="do the thing",
        title="t",
        sandbox_id="sandbox-1",
        secrets={"SCOPED_TOKEN": "not-logged"},
    )
    assert payload["sandbox_id"] == "sandbox-1"
    assert payload["secrets"] == {"SCOPED_TOKEN": "not-logged"}


def test_metadata_sanitization_preserves_metrics_but_removes_secrets() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    sanitized = oh.sanitize_metadata(
        {
            "session_api_key": "secret",
            "prompt": "sensitive instructions",
            "metrics": {"prompt_tokens": 10, "accumulated_cost": 0.25},
        }
    )
    assert "session_api_key" not in sanitized
    assert sanitized["prompt"] == "<redacted-content>"
    assert sanitized["metrics"]["prompt_tokens"] == 10


def test_streaming_recovery_uses_only_the_latest_contiguous_agent_block() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    events = [
        {"source": "agent", "kind": "StreamingDeltaEvent", "content": "old"},
        {"source": "user", "kind": "MessageEvent", "content": "continue"},
        {"source": "agent", "kind": "StreamingDeltaEvent", "content": "new "},
        {"source": "agent", "kind": "StreamingDeltaEvent", "content": "result"},
    ]
    assert oh.streaming_agent_text(events) == "new result"


def test_terminal_status_recovers_from_durable_events() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    assert (
        oh.terminal_status_from_events(
            [
                {
                    "kind": "ConversationStateUpdateEvent",
                    "key": "execution_status",
                    "value": "finished",
                }
            ]
        )
        == "finished"
    )
    assert (
        oh.terminal_status_from_events(
            [{"kind": "ConversationErrorEvent", "code": "example", "detail": "failed"}]
        )
        == "error"
    )
    assert (
        oh.terminal_status_from_events(
            [
                {
                    "kind": "ConversationStateUpdateEvent",
                    "key": "full_state",
                    "value": '{"execution_status":"finished"}',
                }
            ]
        )
        == "finished"
    )


def test_capacity_snapshot_counts_active_sandboxes(monkeypatch) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")

    def requester(method, url, headers, body=None, timeout=60):
        assert method == "GET"
        if "page_id=page-2" in url:
            return {
                "items": [
                    {"id": "sandbox-3", "status": "STARTING"},
                    {"id": "sandbox-4", "status": "ERROR"},
                ]
            }
        return {
            "items": [
                {"id": "sandbox-1", "status": "RUNNING"},
                {"id": "sandbox-2", "status": "PAUSED"},
            ],
            "next_page_id": "page-2",
        }

    monkeypatch.setattr(oh, "request_json", requester)
    snapshot = oh.capacity_snapshot(
        "https://example.test",
        {},
        runtime_limit=10,
        launch_lock_at=3,
    )
    assert snapshot["active"] == 2
    assert snapshot["launch_allowed"] is True
    assert snapshot["observed_sandboxes"] == 4


def test_explicit_sandbox_create_and_poll(monkeypatch) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    calls = []

    def requester(method, url, headers, body=None, timeout=60):
        calls.append((method, url))
        if method == "POST":
            return {"id": "sandbox-1", "status": "STARTING"}
        return [{"id": "sandbox-1", "status": "RUNNING"}]

    monkeypatch.setattr(oh, "request_json", requester)
    started = oh.start_sandbox("https://example.test", {})
    ready = oh.poll_sandbox(
        base="https://example.test",
        headers={},
        sandbox_id=started["id"],
        poll_seconds=0,
    )
    assert ready["status"] == "RUNNING"
    assert calls[0] == ("POST", "https://example.test/api/v1/sandboxes")


def test_start_worker_verifies_explicit_sandbox_attachment(monkeypatch) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    monkeypatch.setattr(
        oh,
        "start_conversation",
        lambda base, headers, payload: {"id": "start-task-1"},
    )
    monkeypatch.setattr(
        oh,
        "poll_start_task",
        lambda **kwargs: {
            "app_conversation_id": "conversation-1",
            "sandbox_id": "sandbox-wrong",
        },
    )
    with pytest.raises(oh.OpenHandsAPIError, match="expected sandbox-1"):
        oh.start_worker(
            "https://example.test",
            "key",
            {"sandbox_id": "sandbox-1"},
        )


def test_reconcile_conversation_uses_durable_event_tail(monkeypatch) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")

    def requester(method, url, headers, body=None, timeout=60):
        if "/api/v1/app-conversations?" in url:
            return [{"sandbox_status": "PAUSED", "execution_status": ""}]
        if "/events/search" in url:
            assert "sort_order=TIMESTAMP_DESC" in url
            return {
                "items": [
                    {
                        "kind": "ConversationStateUpdateEvent",
                        "key": "full_state",
                        "value": {"execution_status": "finished"},
                    }
                ]
            }
        raise AssertionError(url)

    monkeypatch.setattr(oh, "request_json", requester)
    record, events, recovered = oh.reconcile_conversation(
        base="https://example.test",
        headers={},
        conversation_id="conversation-1",
    )
    assert record["execution_status"] == "finished"
    assert record["terminal_status_source"] == "events"
    assert recovered is True
    assert len(events) == 1


def test_agent_tags_idle_info_and_metrics(monkeypatch) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    agent_url = "https://runtime.example.test/api/conversations/conversation-1"
    agent_gets = 0

    def requester(method, url, headers, body=None, timeout=60):
        nonlocal agent_gets
        if "/api/v1/app-conversations?" in url:
            return [
                {
                    "conversation_url": agent_url,
                    "session_api_key": "not-logged",
                    "metrics": {
                        "accumulated_cost": 0.25,
                        "accumulated_token_usage": {"prompt_tokens": 10},
                    },
                }
            ]
        if method == "GET" and url == agent_url:
            agent_gets += 1
            return {
                "tags": (
                    {"existing": "yes"}
                    if agent_gets == 1
                    else {"existing": "yes", "campaignid": "campaign-1"}
                )
            }
        if method == "PATCH" and url == agent_url:
            assert body == {
                "tags": {"existing": "yes", "campaignid": "campaign-1"}
            }
            return {"success": True}
        if method == "GET" and url.endswith("/server_info"):
            return {
                "idle_time": 12.0,
                "runtime_idle_timeout_seconds": 3600.0,
                "session_api_key": "not-persisted",
            }
        raise AssertionError((method, url))

    monkeypatch.setattr(oh, "request_json", requester)
    assert oh.patch_agent_tags(
        "https://example.test",
        {},
        "conversation-1",
        {"campaignid": "campaign-1"},
    )["campaignid"] == "campaign-1"
    server_info = oh.get_agent_server_info(
        "https://example.test", {}, "conversation-1"
    )
    assert server_info["idle_time"] == 12.0
    assert "session_api_key" not in server_info
    metrics = oh.get_conversation_metrics(
        "https://example.test", {}, "conversation-1"
    )
    assert metrics["accumulated_cost"] == 0.25
    assert metrics["accumulated_token_usage"]["prompt_tokens"] == 10


def test_app_tags_are_polled_until_they_converge(monkeypatch) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    records = iter(
        [
            {"tags": {"campaignid": "old"}},
            {"tags": {"campaignid": "campaign-1"}},
        ]
    )
    monkeypatch.setattr(
        oh,
        "get_conversation",
        lambda base, headers, conversation_id: next(records),
    )
    observed = oh.poll_app_tags(
        base="https://example.test",
        headers={},
        conversation_id="conversation-1",
        expected_tags={"campaignid": "campaign-1"},
        poll_seconds=0,
    )
    assert observed == {"campaignid": "campaign-1"}


def test_websocket_finished_requires_full_state_confirmation() -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    assert oh.terminal_signal(
        {
            "kind": "ConversationStateUpdateEvent",
            "key": "execution_status",
            "value": "finished",
        }
    ) == ("finished", False)
    assert oh.terminal_signal(
        {
            "kind": "ConversationStateUpdateEvent",
            "key": "full_state",
            "value": {"execution_status": "finished"},
        }
    ) == ("finished", True)
    assert oh.websocket_url(
        "https://runtime.example.test/api/conversations/conversation-1"
    ) == (
        "wss://runtime.example.test/sockets/events/conversation-1"
        "?resend_mode=all"
    )


def test_cleanup_is_idempotent_when_resources_are_already_missing(
    monkeypatch,
) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")

    def requester(method, url, headers, body=None, timeout=60):
        if method == "DELETE" and "/app-conversations/" in url:
            raise oh.OpenHandsAPIError(
                "DELETE /api/v1/app-conversations/conversation-1 -> HTTP 404"
            )
        if method == "GET" and "/api/v1/sandboxes?" in url:
            return [None]
        raise AssertionError((method, url))

    monkeypatch.setattr(oh, "request_json", requester)
    result = oh.cleanup_resources(
        base="https://example.test",
        headers={},
        conversation_id="conversation-1",
        sandbox_id="sandbox-1",
    )
    assert result == {
        "mode": "delete",
        "conversation_deleted": False,
        "sandbox_cleanup": "already-missing",
    }


def test_pause_sandbox_is_idempotent(monkeypatch) -> None:
    oh = load_module(COMMON / "openhands_conversations.py")
    calls = []

    def requester(method, url, headers, body=None, timeout=60):
        calls.append((method, url))
        return [{"id": "sandbox-1", "status": "PAUSED"}]

    monkeypatch.setattr(oh, "request_json", requester)
    paused = oh.pause_sandbox(
        base="https://example.test",
        headers={},
        sandbox_id="sandbox-1",
    )
    assert paused["status"] == "PAUSED"
    assert calls == [
        (
            "GET",
            "https://example.test/api/v1/sandboxes?id=sandbox-1",
        )
    ]


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


def test_canvas_profile_payload_uses_server_side_profile() -> None:
    canvas = load_module(COMMON / "canvas_conversations.py")
    payload = canvas.build_start_payload(
        prompt="do the thing",
        title="t",
        workspace_dir="/tmp/w",
        agent_profile_id="profile-acp",
    )
    assert payload["agent_profile_id"] == "profile-acp"
    assert "secrets_encrypted" not in payload
    assert "agent_settings" not in payload


def test_canvas_rejects_direct_model_override() -> None:
    canvas = load_module(COMMON / "canvas_conversations.py")
    with pytest.raises(ValueError, match="saved agent profile"):
        canvas.build_start_payload(
            prompt="do the thing",
            title="t",
            llm_model="provider/model",
        )


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


def test_parent_child_cli_accepts_agent_profile() -> None:
    module = load_module(PARENT_CHILD / "run_supervisor.py")
    args = module.build_parser().parse_args(
        ["--dry-run", "--agent-profile-id", "profile-acp"]
    )
    assert args.agent_profile_id == "profile-acp"


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


def test_polling_cli_accepts_agent_profile() -> None:
    module = load_module(POLLING / "orchestrate_once.py")
    args = module.build_parser().parse_args(
        ["--dry-run", "--agent-profile-id", "profile-acp"]
    )
    assert args.agent_profile_id == "profile-acp"


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
