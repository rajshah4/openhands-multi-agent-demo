#!/usr/bin/env python3
"""Start and observe conversations on a LOCAL Agent Canvas (OpenHands Agent Server).

Agent Canvas exposes a different API than OpenHands Cloud/Enterprise:

| | Cloud/Enterprise (`openhands_conversations.py`) | Agent Canvas (this module) |
| --- | --- | --- |
| Create | POST /api/v1/app-conversations -> start task -> poll | POST /api/conversations -> id immediately |
| Auth | Authorization: Bearer <api key> | X-Session-API-Key from the Canvas environment or persisted key |
| Settings | Held server-side in the secret store | Client round-trips encrypted settings |
| Final response | Reconstructed from the events search | GET /api/conversations/{id}/agent_final_response |
| Worker state | Selected by Enterprise configuration | Local folder or per-conversation worktree |

This module exposes the same function surface as `openhands_conversations.py`
(`build_start_payload`, `start_worker`, `get_status`, `get_final`,
`conversation_url`, `TERMINAL_EXECUTION_STATUSES`), so the pattern scripts can
swap runtimes with a flag and stay otherwise identical.

Adapted from the live-validated helper in
https://github.com/rajshah4/sdlc-automation-github-demo (agent-canvas/scripts/agent_canvas_delegate.py).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000"
TERMINAL_EXECUTION_STATUSES = {"finished", "error", "stuck", "stopped"}

DEFAULT_TOOLS = [
    {"name": "terminal", "params": {}},
    {"name": "file_editor", "params": {}},
    {"name": "task_tracker", "params": {}},
]


class CanvasAPIError(RuntimeError):
    """Raised when the local Agent Canvas API cannot satisfy a request."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def base_url(explicit: str | None = None) -> str:
    return (
        explicit
        or os.getenv("AGENT_CANVAS_BASE_URL")
        or os.getenv("AGENT_CANVAS_BACKEND")
        or os.getenv("AGENT_CANVAS_BASE")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def read_api_key() -> str:
    for env_name in (
        "AGENT_CANVAS_API_KEY",
        "SESSION_API_KEY",
        "OH_SESSION_API_KEYS_0",
        "LOCAL_BACKEND_API_KEY",
    ):
        value = os.getenv(env_name)
        if value:
            return value.strip()
    for key_file in (
        Path.home() / ".openhands" / "agent-canvas" / "session-api-key.txt",
        Path.home() / ".openhands" / "agent-canvas" / "api-key.txt",
    ):
        if key_file.exists():
            value = key_file.read_text(encoding="utf-8").strip()
            if value:
                return value
    raise CanvasAPIError(
        "No Agent Canvas API key found. Set AGENT_CANVAS_API_KEY or start local "
        "Agent Canvas so its persisted session key exists."
    )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def request_json(
    method: str,
    url: str,
    key: str,
    body: dict[str, Any] | None = None,
    expose_encrypted_secrets: bool = False,
    timeout: int = 120,
) -> Any:
    headers = {"Accept": "application/json", "X-Session-API-Key": key}
    if expose_encrypted_secrets:
        headers["X-Expose-Secrets"] = "encrypted"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise CanvasAPIError(f"{method} {url} -> HTTP {exc.code}: {raw[:2000]}") from exc
    except urllib.error.URLError as exc:
        raise CanvasAPIError(f"{method} {url} failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

def _agent_settings(base: str, key: str) -> dict[str, Any]:
    """Round-trip the local encrypted settings, as the Canvas API requires."""
    settings = request_json(
        "GET", f"{base}/api/settings", key, expose_encrypted_secrets=True
    )
    agent_settings = dict(settings.get("agent_settings") or {})
    agent_settings.pop("schema_version", None)
    agent_settings.pop("mcp_config", None)
    tools = {tool.get("name"): tool for tool in (agent_settings.get("tools") or []) if tool.get("name")}
    for tool in DEFAULT_TOOLS:
        tools.setdefault(tool["name"], tool)
    agent_settings["tools"] = list(tools.values())
    return agent_settings


def build_start_payload(
    *,
    prompt: str,
    title: str,  # noqa: ARG001 - Canvas autotitles; kept for surface parity
    llm_model: str | None = None,  # noqa: ARG001 - profile selection is a Canvas-side concern
    run: bool = True,
    workspace_dir: str | None = None,
    max_iterations: int = 100,
    agent_profile_id: str | None = None,
) -> dict[str, Any]:
    """The static part of the payload (dry-run printable, no server needed)."""
    if llm_model:
        raise ValueError(
            "Canvas does not accept a direct llm_model override; select a saved agent profile"
        )
    payload: dict[str, Any] = {
        "workspace": {
            "kind": "LocalWorkspace",
            "working_dir": workspace_dir or str(Path.cwd()),
        },
        "worktree": False,
        "confirmation_policy": {"kind": "NeverConfirm"},
        "max_iterations": max_iterations,
        "stuck_detection": True,
        "autotitle": True,
        "initial_message": {
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
            "run": run,
        },
    }
    if agent_profile_id:
        payload["agent_profile_id"] = agent_profile_id
    else:
        # Inline OpenHands settings are encrypted by the Canvas settings API.
        # Profile-backed conversations, including ACP profiles, are resolved
        # server-side and must not be forced through this encrypted-settings path.
        payload["secrets_encrypted"] = True
    return payload


# ---------------------------------------------------------------------------
# The runtime surface shared with openhands_conversations.py
# ---------------------------------------------------------------------------

def start_worker(
    base: str,
    key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a conversation; unlike Cloud, the id comes back immediately."""
    full_payload = dict(payload)
    if "agent_profile_id" not in full_payload:
        full_payload["agent_settings"] = _agent_settings(base, key)
    response = request_json("POST", f"{base}/api/conversations", key, full_payload)
    conversation_id = response.get("id")
    if not conversation_id:
        raise CanvasAPIError("Agent Canvas returned no conversation id")
    return {"id": conversation_id, "ui_url": conversation_url(base, conversation_id)}


def get_status(base: str, key: str, conversation_id: str) -> str:
    record = request_json("GET", f"{base}/api/conversations/{conversation_id}", key)
    return str(record.get("execution_status", "")).lower()


def get_final(base: str, key: str, conversation_id: str, *, retries: int = 4, retry_seconds: int = 5) -> str:
    """Canvas has a dedicated final-response endpoint; retry briefly if empty."""
    for attempt in range(retries + 1):
        response = request_json(
            "GET", f"{base}/api/conversations/{conversation_id}/agent_final_response", key
        )
        text = str((response or {}).get("response") or "").strip()
        if text or attempt == retries:
            return text
        time.sleep(retry_seconds)
    return ""


def conversation_url(base: str, conversation_id: str) -> str:
    return f"{base.rstrip('/')}/conversations/{conversation_id}"
