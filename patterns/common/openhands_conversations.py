#!/usr/bin/env python3
"""Start and observe OpenHands conversations over the V1 app-conversation API.

This helper is dependency-free (Python stdlib only) so any orchestrator — a
laptop script, a cron automation, or a parent OpenHands conversation — can use
it without installing packages.

It works against OpenHands Cloud (https://app.all-hands.dev), Enterprise, and
self-hosted/Replicated instances: set OPENHANDS_BASE_URL and OPENHANDS_API_KEY.

Conversation creation follows the instance sandbox-grouping configuration
unless the controller first calls `start_sandbox`, waits with `poll_sandbox`,
and passes that ID through `build_start_payload(sandbox_id=...)`.

The explicit placement, correlation, event, idle, metrics, and cleanup controls
were verified against OpenHands Enterprise 0.24.0 in:
https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-workflow-primitives
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://app.all-hands.dev"
TERMINAL_EXECUTION_STATUSES = {"finished", "error", "stuck", "stopped", "waiting_for_confirmation"}
RUNNING_EXECUTION_STATUSES = {"running", "starting"}
TERMINAL_SANDBOX_STATUSES = {"DELETED", "ERROR", "MISSING"}
ACTIVE_SANDBOX_STATUSES = {"RUNNING", "STARTING", "PENDING", "CREATING"}
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "session_api_key",
}
CONTENT_KEYS = {"initial_message", "messages", "prompt", "system_prompt"}


class OpenHandsAPIError(RuntimeError):
    """Raised when the OpenHands API cannot satisfy a request."""


class ContractError(ValueError):
    """Raised when a worker returns an ambiguous output contract."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def base_url(explicit: str | None = None) -> str:
    return (
        explicit
        or os.getenv("OPENHANDS_BASE_URL")
        or os.getenv("OPENHANDS_HOST")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def read_api_key() -> str:
    for env_name in (
        "OPENHANDS_API_KEY",
        "OPENHANDS_API_KEY_ORG",
        "OH_API_KEY",
        "OPENHANDS_CLOUD_API_KEY",
    ):
        value = os.getenv(env_name)
        if value:
            return value.strip()
    raise OpenHandsAPIError(
        "Missing OpenHands API key. Set OPENHANDS_API_KEY "
        "(or OPENHANDS_API_KEY_ORG / OH_API_KEY)."
    )


def build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def load_env_file(path: Path) -> None:
    """Load KEY=value lines into the environment without overwriting existing values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key.replace("_", "").isalnum():
            os.environ.setdefault(key, value.strip().strip("'").strip('"'))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def endpoint(base: str, path: str, query: dict[str, Any] | None = None) -> str:
    url = base.rstrip("/") + path
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    return url


def sanitize_metadata(value: Any) -> Any:
    """Remove secret-bearing fields while retaining lifecycle and usage data."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in SENSITIVE_KEYS or normalized.endswith("_password"):
                continue
            if (
                normalized == "token"
                or normalized.endswith("_token")
                or normalized.endswith("_api_key")
                or normalized.endswith("_secret")
            ):
                continue
            if normalized in CONTENT_KEYS:
                sanitized[str(key)] = "<redacted-content>"
                continue
            sanitized[str(key)] = sanitize_metadata(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    return value


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    timeout: int = 60,
) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.dumps(sanitize_metadata(json.loads(raw)), sort_keys=True)
        except (json.JSONDecodeError, TypeError, ValueError):
            detail = "<non-json response omitted>"
        path = urllib.parse.urlsplit(url).path
        raise OpenHandsAPIError(
            f"{method} {path} -> HTTP {exc.code}: {detail[:1000]}"
        ) from exc
    except urllib.error.URLError as exc:
        path = urllib.parse.urlsplit(url).path
        raise OpenHandsAPIError(f"{method} {path} failed: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Prompts and contracts
# ---------------------------------------------------------------------------

def render_prompt(path: Path, variables: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def parse_contract(final_text: str) -> dict[str, str]:
    """Parse `key: value` lines from a worker's final response.

    Workers end their final response with a small machine-readable contract
    (status / summary / next_gate / ...). The orchestrator gates on this
    instead of reading the whole event log.
    """
    contract: dict[str, str] = {}
    for line in final_text.splitlines():
        stripped = line.strip().strip("`")
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().lower()
        if key not in {"status", "summary", "next_gate", "artifact", "result"}:
            continue
        value = value.strip()
        if key in {"status", "next_gate"}:
            value = value.lower()
        if key in contract and contract[key] != value:
            raise ContractError(f"conflicting values for contract field {key!r}")
        contract[key] = value
    return contract


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def build_start_payload(
    *,
    prompt: str,
    title: str,
    repository: str | None = None,
    branch: str | None = None,
    llm_model: str | None = None,
    agent_profile_id: str | None = None,
    sandbox_id: str | None = None,
    secrets: dict[str, str] | None = None,
    run: bool = True,
) -> dict[str, Any]:
    if llm_model and agent_profile_id:
        raise ValueError("Choose either llm_model or agent_profile_id, not both")
    payload: dict[str, Any] = {
        "title": title,
        "trigger": "openhands_api",
        "initial_message": {
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
            "run": run,
        },
    }
    if repository:
        payload["selected_repository"] = repository
    if branch:
        payload["selected_branch"] = branch
    if llm_model:
        payload["llm_model"] = llm_model
    if agent_profile_id:
        payload["agent_profile_id"] = agent_profile_id
    if sandbox_id:
        payload["sandbox_id"] = sandbox_id
    if secrets:
        payload["secrets"] = dict(secrets)
    return payload


def start_conversation(base: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", endpoint(base, "/api/v1/app-conversations"), headers, payload, timeout=120)


def search_sandboxes(
    base: str,
    headers: dict[str, str],
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return every sandbox visible to the authenticated Enterprise user."""
    sandboxes: list[dict[str, Any]] = []
    page_id: str | None = None
    while True:
        query: dict[str, Any] = {"limit": limit}
        if page_id:
            query["page_id"] = page_id
        page = request_json(
            "GET",
            endpoint(base, "/api/v1/sandboxes/search", query),
            headers,
            timeout=60,
        )
        if isinstance(page, list):
            sandboxes.extend(item for item in page if isinstance(item, dict))
            break
        if not isinstance(page, dict):
            break
        sandboxes.extend(
            item for item in page.get("items", []) if isinstance(item, dict)
        )
        page_id = page.get("next_page_id")
        if not page_id:
            break
    return [sanitize_metadata(record) for record in sandboxes]


def capacity_snapshot(
    base: str,
    headers: dict[str, str],
    *,
    runtime_limit: int,
    launch_lock_at: int,
) -> dict[str, Any]:
    """Count active sandboxes and close admission before the runtime limit."""
    if runtime_limit < 1:
        raise ValueError("runtime_limit must be at least 1")
    if not 1 <= launch_lock_at <= runtime_limit:
        raise ValueError("launch_lock_at must be between 1 and runtime_limit")
    sandboxes = search_sandboxes(base, headers)
    status_counts: dict[str, int] = {}
    for sandbox in sandboxes:
        status = str(sandbox.get("status", "UNKNOWN")).upper()
        status_counts[status] = status_counts.get(status, 0) + 1
    active = sum(
        count
        for status, count in status_counts.items()
        if status in ACTIVE_SANDBOX_STATUSES
    )
    return {
        "scope": "authenticated-user-visible-sandboxes",
        "active": active,
        "runtime_limit": runtime_limit,
        "launch_lock_at": launch_lock_at,
        "launch_allowed": active < launch_lock_at,
        "available_before_limit": max(runtime_limit - active, 0),
        "status_counts": dict(sorted(status_counts.items())),
        "observed_sandboxes": len(sandboxes),
    }


def start_sandbox(
    base: str,
    headers: dict[str, str],
    *,
    sandbox_spec_id: str | None = None,
) -> dict[str, Any]:
    """Create a sandbox without starting a conversation."""
    query = {"sandbox_spec_id": sandbox_spec_id} if sandbox_spec_id else None
    response = request_json(
        "POST",
        endpoint(base, "/api/v1/sandboxes", query),
        headers,
        timeout=120,
    )
    if not isinstance(response, dict) or not response.get("id"):
        raise OpenHandsAPIError("sandbox create returned no sandbox id")
    return sanitize_metadata(response)


def get_sandbox(
    base: str,
    headers: dict[str, str],
    sandbox_id: str,
) -> dict[str, Any]:
    records = request_json(
        "GET",
        endpoint(base, "/api/v1/sandboxes", {"id": sandbox_id}),
        headers,
        timeout=60,
    )
    record = records[0] if isinstance(records, list) and records else {}
    return record if isinstance(record, dict) else {}


def poll_sandbox(
    *,
    base: str,
    headers: dict[str, str],
    sandbox_id: str,
    desired_status: str = "RUNNING",
    timeout_seconds: int = 600,
    poll_seconds: int = 5,
) -> dict[str, Any]:
    """Wait for a prepared sandbox to reach the requested lifecycle state."""
    deadline = time.monotonic() + timeout_seconds
    expected = desired_status.upper()
    while time.monotonic() < deadline:
        record = get_sandbox(base, headers, sandbox_id)
        status = str(record.get("status", "")).upper()
        if status == expected:
            return sanitize_metadata(record)
        if not record or status in TERMINAL_SANDBOX_STATUSES:
            raise OpenHandsAPIError(
                f"sandbox {sandbox_id} reached {status or 'MISSING'}, expected {expected}"
            )
        time.sleep(poll_seconds)
    raise TimeoutError(
        f"Timed out waiting for sandbox {sandbox_id} to reach {expected}"
    )


def poll_start_task(
    *,
    base: str,
    headers: dict[str, str],
    task_id: str,
    timeout_seconds: int = 600,
    poll_seconds: int = 10,
) -> dict[str, Any]:
    """Wait until the start task yields a conversation id (or fails)."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        tasks = request_json(
            "GET",
            endpoint(base, "/api/v1/app-conversations/start-tasks", {"ids": task_id}),
            headers,
            timeout=60,
        )
        task = tasks[0] if isinstance(tasks, list) and tasks else {}
        status = str(task.get("status", "")).upper()
        if task.get("app_conversation_id") or status in {"READY", "ERROR", "FAILED", "STOPPED"}:
            return task
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for OpenHands start task {task_id}")


def get_conversation(base: str, headers: dict[str, str], conversation_id: str) -> dict[str, Any]:
    conversations = request_json(
        "GET",
        endpoint(base, "/api/v1/app-conversations", {"ids": conversation_id}),
        headers,
        timeout=60,
    )
    record = conversations[0] if isinstance(conversations, list) and conversations else {}
    return record if isinstance(record, dict) else {}


def poll_conversation(
    *,
    base: str,
    headers: dict[str, str],
    conversation_id: str,
    timeout_seconds: int = 1800,
    poll_seconds: int = 20,
) -> dict[str, Any]:
    """Wait for terminal state using the app record and durable REST events."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        conversation, _, _ = reconcile_conversation(
            base=base,
            headers=headers,
            conversation_id=conversation_id,
        )
        execution_status = str(conversation.get("execution_status", "")).lower()
        if execution_status in TERMINAL_EXECUTION_STATUSES:
            return conversation
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for OpenHands conversation {conversation_id}")


def fetch_events(
    *,
    base: str,
    headers: dict[str, str],
    conversation_id: str,
    limit: int = 100,
    sort_order: str = "TIMESTAMP",
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    if sort_order not in {"TIMESTAMP", "TIMESTAMP_DESC"}:
        raise ValueError(f"unknown event sort order: {sort_order}")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    items: list[dict[str, Any]] = []
    page_id: str | None = None
    pages = 0
    while True:
        query: dict[str, Any] = {"sort_order": sort_order, "limit": limit}
        if page_id:
            query["page_id"] = page_id
        page = request_json(
            "GET",
            endpoint(base, f"/api/v1/conversation/{conversation_id}/events/search", query),
            headers,
            timeout=60,
        )
        if not isinstance(page, dict):
            return items
        items.extend(
            item for item in page.get("items", []) if isinstance(item, dict)
        )
        pages += 1
        page_id = page.get("next_page_id")
        if not page_id or (max_pages is not None and pages >= max_pages):
            return list(reversed(items)) if sort_order == "TIMESTAMP_DESC" else items


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks = [
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type", "text") == "text"
    ]
    return "\n".join(chunk for chunk in chunks if chunk)


def latest_agent_text(events: list[dict[str, Any]]) -> str:
    """The worker's final response: FinishAction message, else last agent text."""
    for event in reversed(events):
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        action_kind = str(action.get("kind", event.get("kind", "")))
        if action_kind == "FinishAction" and action.get("message"):
            return str(action.get("message", "")).strip()
    for event in reversed(events):
        if str(event.get("source", "")).lower() not in {"agent", "assistant"}:
            continue
        if str(event.get("kind", "")) != "MessageEvent":
            continue
        for key in ("llm_message", "message"):
            message = event.get(key)
            if isinstance(message, dict):
                text = _content_text(message.get("content"))
                if text:
                    return text.strip()
        if isinstance(event.get("content"), (str, list)):
            text = _content_text(event["content"])
            if text:
                return text.strip()
    return ""


def streaming_agent_text(events: list[dict[str, Any]]) -> str:
    """Recover only the newest contiguous terminal streaming block."""
    chunks: list[str] = []
    latest_chunks: list[str] = []
    for event in events:
        if (
            str(event.get("source", "")).lower() not in {"agent", "assistant"}
            or str(event.get("kind", "")) != "StreamingDeltaEvent"
        ):
            if chunks:
                latest_chunks = chunks
                chunks = []
            continue
        content = event.get("content")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            chunks.append(_content_text(content))
    if chunks:
        latest_chunks = chunks
    return "".join(latest_chunks).strip()


def terminal_status_from_events(events: list[dict[str, Any]]) -> str:
    """Recover terminal execution state when the app record is incomplete."""
    for event in reversed(events):
        kind = str(event.get("kind", ""))
        if kind in {"ConversationErrorEvent", "AgentErrorEvent", "ErrorEvent"}:
            return "error"
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        if kind == "FinishAction" or action.get("kind") == "FinishAction":
            return "finished"
        if kind != "ConversationStateUpdateEvent":
            continue
        key = str(event.get("key", "")).lower()
        value = event.get("value")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        if key == "execution_status":
            status = str(value or "").lower()
            if status in TERMINAL_EXECUTION_STATUSES:
                return status
        if key == "full_state" and isinstance(value, dict):
            status = str(value.get("execution_status", "")).lower()
            if status in TERMINAL_EXECUTION_STATUSES:
                return status
    return ""


def reconcile_conversation(
    *,
    base: str,
    headers: dict[str, str],
    conversation_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """Reconcile an app snapshot with the durable REST event tail."""
    record = get_conversation(base, headers, conversation_id)
    status = str(record.get("execution_status", "")).lower()
    if status in TERMINAL_EXECUTION_STATUSES:
        events = fetch_events(
            base=base,
            headers=headers,
            conversation_id=conversation_id,
            sort_order="TIMESTAMP_DESC",
            max_pages=2,
        )
        return record, events, False

    sandbox_status = str(record.get("sandbox_status", "")).upper()
    if sandbox_status in {"PAUSED", "ERROR", "MISSING"}:
        events = fetch_events(
            base=base,
            headers=headers,
            conversation_id=conversation_id,
            sort_order="TIMESTAMP_DESC",
            max_pages=2,
        )
        recovered = terminal_status_from_events(events)
        if recovered:
            reconciled = dict(record)
            reconciled["execution_status"] = recovered
            reconciled["terminal_status_source"] = "events"
            return reconciled, events, True
        if sandbox_status in TERMINAL_SANDBOX_STATUSES:
            raise OpenHandsAPIError(
                f"conversation {conversation_id} sandbox is {sandbox_status}"
            )
    return record, [], False


def final_response(
    base: str,
    headers: dict[str, str],
    conversation_id: str,
    *,
    retries: int = 4,
    retry_seconds: int = 5,
) -> str:
    """Fetch the final response, retrying briefly if it is not yet indexed.

    The events search index can lag a few seconds behind a conversation
    flipping to `finished`; fetching immediately can return no agent text.
    """
    for attempt in range(retries + 1):
        events = fetch_events(
            base=base,
            headers=headers,
            conversation_id=conversation_id,
            sort_order="TIMESTAMP_DESC",
            max_pages=2,
        )
        text = latest_agent_text(events)
        if text:
            return text
        streamed_text = streaming_agent_text(events)
        if streamed_text:
            return streamed_text
        if attempt == retries:
            return ""
        time.sleep(retry_seconds)
    return ""


def conversation_metrics(record: dict[str, Any]) -> dict[str, Any]:
    """Return sanitized app-record usage metrics for an attempt ledger."""
    metrics = record.get("metrics")
    return sanitize_metadata(metrics) if isinstance(metrics, dict) else {}


def get_conversation_metrics(
    base: str,
    headers: dict[str, str],
    conversation_id: str,
) -> dict[str, Any]:
    return conversation_metrics(get_conversation(base, headers, conversation_id))


def conversation_url(base: str, conversation_id: str) -> str:
    return f"{base.rstrip('/')}/conversations/{conversation_id}"


def conversation_summary(
    base: str,
    conversation_id: str,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = record or {}
    return {
        "id": conversation_id,
        "ui_url": conversation_url(base, conversation_id),
        "title": record.get("title"),
        "execution_status": record.get("execution_status"),
        "terminal_status_source": record.get("terminal_status_source"),
        "sandbox_id": record.get("sandbox_id"),
    }


def agent_connection(
    base: str,
    headers: dict[str, str],
    conversation_id: str,
) -> tuple[str, dict[str, str]]:
    """Return the agent URL and session headers; callers must not log headers."""
    record = get_conversation(base, headers, conversation_id)
    agent_url = str(record.get("conversation_url") or "")
    session_api_key = str(record.get("session_api_key") or "")
    if not agent_url.startswith(("https://", "http://")):
        raise OpenHandsAPIError(
            f"conversation {conversation_id} has no agent conversation URL"
        )
    if not session_api_key:
        raise OpenHandsAPIError(
            f"conversation {conversation_id} has no agent session key"
        )
    return agent_url, {
        "X-Session-API-Key": session_api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def patch_agent_tags(
    base: str,
    headers: dict[str, str],
    conversation_id: str,
    tags: dict[str, str],
) -> dict[str, str]:
    """Read, merge, replace, and verify short agent-side correlation tags."""
    for key, value in tags.items():
        if not key.isalnum() or key.lower() != key:
            raise ValueError("conversation tag keys must be lowercase alphanumeric")
        if len(value) > 256:
            raise ValueError("conversation tag values must be at most 256 chars")
    agent_url, agent_headers = agent_connection(base, headers, conversation_id)
    current = request_json("GET", agent_url, agent_headers, timeout=60)
    current_tags = (
        dict(current.get("tags") or {}) if isinstance(current, dict) else {}
    )
    current_tags.update(tags)
    request_json(
        "PATCH",
        agent_url,
        agent_headers,
        {"tags": current_tags},
        timeout=60,
    )
    updated = request_json("GET", agent_url, agent_headers, timeout=60)
    observed = (
        dict(updated.get("tags") or {}) if isinstance(updated, dict) else {}
    )
    for key, value in tags.items():
        if observed.get(key) != value:
            raise OpenHandsAPIError(
                f"agent conversation did not retain tag {key!r}"
            )
    return observed


def poll_app_tags(
    *,
    base: str,
    headers: dict[str, str],
    conversation_id: str,
    expected_tags: dict[str, str],
    timeout_seconds: int = 30,
    poll_seconds: int = 1,
) -> dict[str, str]:
    """Wait for agent-side correlation tags to appear on the app record."""
    deadline = time.monotonic() + timeout_seconds
    observed: dict[str, str] = {}
    while time.monotonic() < deadline:
        record = get_conversation(base, headers, conversation_id)
        observed = (
            dict(record.get("tags") or {}) if isinstance(record, dict) else {}
        )
        if all(observed.get(key) == value for key, value in expected_tags.items()):
            return observed
        time.sleep(poll_seconds)
    missing = sorted(
        key for key, value in expected_tags.items() if observed.get(key) != value
    )
    raise TimeoutError(
        f"Timed out waiting for conversation {conversation_id} tags: "
        + ", ".join(missing)
    )


def get_agent_server_info(
    base: str,
    headers: dict[str, str],
    conversation_id: str,
) -> dict[str, Any]:
    """Return sanitized sandbox-wide idle and server metadata."""
    agent_url, agent_headers = agent_connection(base, headers, conversation_id)
    marker = "/api/conversations/"
    if marker not in agent_url:
        raise OpenHandsAPIError("unrecognized agent conversation URL")
    server_base = agent_url.split(marker, 1)[0]
    record = request_json(
        "GET",
        f"{server_base}/server_info",
        agent_headers,
        timeout=60,
    )
    return sanitize_metadata(record or {})


def terminal_signal(event: dict[str, Any]) -> tuple[str | None, bool]:
    """Return a WebSocket terminal status and whether it is authoritative."""
    if str(event.get("kind", "")) != "ConversationStateUpdateEvent":
        return None, False
    key = str(event.get("key", "")).lower()
    value = event.get("value")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    if key == "full_state" and isinstance(value, dict):
        status = str(value.get("execution_status", "")).lower()
        if status in {"finished", "error", "stuck"}:
            return status, True
    if key == "execution_status":
        status = str(value).lower()
        if status in {"error", "stuck"}:
            return status, True
        if status == "finished":
            return status, False
    return None, False


def websocket_url(agent_conversation_url: str) -> str:
    parsed = urllib.parse.urlsplit(agent_conversation_url)
    marker = "/api/conversations/"
    if marker not in parsed.path:
        raise ValueError("unrecognized agent conversation URL")
    conversation_id = parsed.path.split(marker, 1)[1].split("/", 1)[0]
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urllib.parse.urlunsplit(
        (
            scheme,
            parsed.netloc,
            f"/sockets/events/{conversation_id}",
            "resend_mode=all",
            "",
        )
    )


async def wait_for_terminal_websocket(
    agent_conversation_url: str,
    session_api_key: str,
    *,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Wait for authoritative agent-server terminal state over WebSocket."""
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise RuntimeError(
            "WebSocket monitoring requires the optional 'websockets' package"
        ) from exc

    async def watch() -> dict[str, Any]:
        provisional_finished = False
        event_count = 0
        async with connect(websocket_url(agent_conversation_url)) as socket:
            await socket.send(
                json.dumps(
                    {"type": "auth", "session_api_key": session_api_key}
                )
            )
            async for raw in socket:
                event_count += 1
                try:
                    event = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(event, dict):
                    continue
                status, confirmed = terminal_signal(event)
                provisional_finished = provisional_finished or (
                    status == "finished" and not confirmed
                )
                if status and confirmed:
                    return {
                        "status": status,
                        "confirmed": True,
                        "provisional_finished_observed": provisional_finished,
                        "event_count": event_count,
                    }
        raise RuntimeError("WebSocket closed before a terminal state")

    return await asyncio.wait_for(watch(), timeout=timeout_seconds)


def _is_missing_error(exc: OpenHandsAPIError) -> bool:
    return "HTTP 404" in str(exc)


def delete_conversation(
    base: str,
    headers: dict[str, str],
    conversation_id: str,
) -> bool:
    """Delete a conversation; return False when it was already absent."""
    try:
        request_json(
            "DELETE",
            endpoint(
                base,
                "/api/v1/app-conversations/"
                + urllib.parse.quote(conversation_id, safe=""),
            ),
            headers,
            timeout=120,
        )
        return True
    except OpenHandsAPIError as exc:
        if _is_missing_error(exc):
            return False
        raise


def delete_sandbox(
    base: str,
    headers: dict[str, str],
    sandbox_id: str,
) -> bool:
    """Delete a sandbox; return False for an absent resource or tombstone."""
    try:
        current = get_sandbox(base, headers, sandbox_id)
    except OpenHandsAPIError as exc:
        if _is_missing_error(exc):
            return False
        raise
    if not current or str(current.get("status", "")).upper() in {"DELETED", "MISSING"}:
        return False
    try:
        request_json(
            "DELETE",
            endpoint(
                base,
                "/api/v1/sandboxes/" + urllib.parse.quote(sandbox_id, safe=""),
                {"sandbox_id": sandbox_id},
            ),
            headers,
            timeout=120,
        )
        return True
    except OpenHandsAPIError as exc:
        if _is_missing_error(exc):
            return False
        raise


def pause_sandbox(
    *,
    base: str,
    headers: dict[str, str],
    sandbox_id: str,
    timeout_seconds: int = 120,
    poll_seconds: int = 2,
) -> dict[str, Any]:
    """Idempotently pause a sandbox and wait for the PAUSED state."""
    current = get_sandbox(base, headers, sandbox_id)
    if str(current.get("status", "")).upper() == "PAUSED":
        return sanitize_metadata(current)
    if not current:
        raise OpenHandsAPIError(f"sandbox {sandbox_id} is missing")
    response = request_json(
        "POST",
        endpoint(
            base,
            "/api/v1/sandboxes/"
            + urllib.parse.quote(sandbox_id, safe="")
            + "/pause",
        ),
        headers,
        timeout=60,
    )
    if isinstance(response, dict) and response.get("success") is False:
        raise OpenHandsAPIError(f"sandbox {sandbox_id} rejected pause request")
    return poll_sandbox(
        base=base,
        headers=headers,
        sandbox_id=sandbox_id,
        desired_status="PAUSED",
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )


def cleanup_resources(
    *,
    base: str,
    headers: dict[str, str],
    conversation_id: str,
    sandbox_id: str | None,
    mode: str = "delete",
) -> dict[str, Any]:
    """Pause or idempotently delete tracked Enterprise worker resources."""
    if mode not in {"pause", "delete"}:
        raise ValueError("cleanup mode must be 'pause' or 'delete'")
    if mode == "pause":
        if not sandbox_id:
            raise ValueError("sandbox_id is required for pause cleanup")
        paused = pause_sandbox(
            base=base,
            headers=headers,
            sandbox_id=sandbox_id,
        )
        return {
            "mode": "pause",
            "conversation_deleted": False,
            "sandbox_cleanup": "paused",
            "sandbox_status": paused.get("status"),
        }

    conversation_deleted = delete_conversation(
        base, headers, conversation_id
    )
    sandbox_cleanup = "not-requested"
    if sandbox_id:
        sandbox_cleanup = (
            "explicit-delete"
            if delete_sandbox(base, headers, sandbox_id)
            else "already-missing"
        )
    return {
        "mode": "delete",
        "conversation_deleted": conversation_deleted,
        "sandbox_cleanup": sandbox_cleanup,
    }


# ---------------------------------------------------------------------------
# The runtime surface shared with canvas_conversations.py
#
# Both modules expose build_start_payload / start_worker / get_status /
# get_final / conversation_url / TERMINAL_EXECUTION_STATUSES, so the pattern
# scripts can swap runtimes with a --runtime flag and stay otherwise identical.
# ---------------------------------------------------------------------------

def start_worker(
    base: str,
    key: str,
    payload: dict[str, Any],
    *,
    start_timeout_seconds: int = 600,
    poll_seconds: int = 10,
) -> dict[str, Any]:
    """Create a conversation; on this API the id arrives via a start task."""
    headers = build_headers(key)
    start = start_conversation(base, headers, payload)
    task_id = start.get("id")
    if not task_id:
        raise OpenHandsAPIError("OpenHands returned no start task id")
    task = poll_start_task(
        base=base,
        headers=headers,
        task_id=task_id,
        timeout_seconds=start_timeout_seconds,
        poll_seconds=poll_seconds,
    )
    conversation_id = task.get("app_conversation_id")
    if not conversation_id:
        detail = task.get("detail") or task.get("error") or task.get("status")
        raise OpenHandsAPIError(
            f"start task {task_id} returned no conversation id ({detail or 'unknown failure'})"
        )
    requested_sandbox_id = payload.get("sandbox_id")
    attached_sandbox_id = task.get("sandbox_id")
    if requested_sandbox_id and attached_sandbox_id != requested_sandbox_id:
        raise OpenHandsAPIError(
            f"conversation attached to {attached_sandbox_id or 'no sandbox'}, "
            f"expected {requested_sandbox_id}"
        )
    return {
        "id": conversation_id,
        "start_task_id": task_id,
        "sandbox_id": attached_sandbox_id,
        "ui_url": conversation_url(base, conversation_id),
    }


def get_status(base: str, key: str, conversation_id: str) -> str:
    headers = build_headers(key)
    record, _, _ = reconcile_conversation(
        base=base,
        headers=headers,
        conversation_id=conversation_id,
    )
    return str(record.get("execution_status", "")).lower()


def get_final(base: str, key: str, conversation_id: str, *, retries: int = 4, retry_seconds: int = 5) -> str:
    return final_response(
        base, build_headers(key), conversation_id, retries=retries, retry_seconds=retry_seconds
    )


# ---------------------------------------------------------------------------
# CLI for ad-hoc use
# ---------------------------------------------------------------------------

def _command_start(args: argparse.Namespace) -> int:
    if args.env_file:
        load_env_file(args.env_file)
    base = base_url(args.base_url)
    headers = build_headers(read_api_key())
    prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")
    payload = build_start_payload(
        prompt=prompt,
        title=args.title,
        repository=args.repository,
        branch=args.branch,
        llm_model=args.llm_model,
        agent_profile_id=args.agent_profile_id,
        sandbox_id=args.sandbox_id,
    )
    start = start_conversation(base, headers, payload)
    task_id = start.get("id")
    summary: dict[str, Any] = {"start_task_id": task_id}
    if task_id and not args.no_wait_start:
        task = poll_start_task(base=base, headers=headers, task_id=task_id)
        conversation_id = task.get("app_conversation_id")
        if conversation_id:
            summary.update(conversation_summary(base, conversation_id))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _command_status(args: argparse.Namespace) -> int:
    if args.env_file:
        load_env_file(args.env_file)
    base = base_url(args.base_url)
    headers = build_headers(read_api_key())
    record = get_conversation(base, headers, args.conversation_id)
    print(json.dumps(conversation_summary(base, args.conversation_id, record), indent=2, sort_keys=True))
    return 0


def _command_final(args: argparse.Namespace) -> int:
    if args.env_file:
        load_env_file(args.env_file)
    base = base_url(args.base_url)
    headers = build_headers(read_api_key())
    text = final_response(base, headers, args.conversation_id)
    print(json.dumps({"final_text": text, "contract": parse_contract(text)}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="OpenHands base URL (default: OPENHANDS_BASE_URL or app.all-hands.dev)")
    parser.add_argument("--env-file", type=Path, help="optional KEY=value env file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="start a conversation")
    start.add_argument("--title", required=True)
    group = start.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt")
    group.add_argument("--prompt-file", type=Path)
    start.add_argument("--repository", help="optional owner/repo to clone into the sandbox")
    start.add_argument("--branch")
    start.add_argument("--llm-model")
    start.add_argument(
        "--agent-profile-id",
        help="optional OpenHands or ACP agent profile id (mutually exclusive with --llm-model)",
    )
    start.add_argument(
        "--sandbox-id",
        help="optional prepared Enterprise sandbox id for explicit attachment",
    )
    start.add_argument("--no-wait-start", action="store_true")
    start.set_defaults(func=_command_start)

    status = subparsers.add_parser("status", help="get conversation status")
    status.add_argument("conversation_id")
    status.set_defaults(func=_command_status)

    final = subparsers.add_parser("final", help="get final response and parsed contract")
    final.add_argument("conversation_id")
    final.set_defaults(func=_command_final)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OpenHandsAPIError, TimeoutError) as exc:
        print(f"openhands_conversations: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
