#!/usr/bin/env python3
"""Start and observe OpenHands conversations over the V1 app-conversation API.

This helper is dependency-free (Python stdlib only) so any orchestrator — a
laptop script, a cron automation, or a parent OpenHands conversation — can use
it without installing packages.

It works against OpenHands Cloud (https://app.all-hands.dev), Enterprise, and
self-hosted/Replicated instances: set OPENHANDS_BASE_URL and OPENHANDS_API_KEY.

Adapted from the live-validated helper in
https://github.com/rajshah4/sdlc-automation-github-demo (scripts/openhands_v1_delegate.py).
"""

from __future__ import annotations

import argparse
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


class OpenHandsAPIError(RuntimeError):
    """Raised when the OpenHands API cannot satisfy a request."""


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
    for env_name in ("OPENHANDS_API_KEY", "OPENHANDS_API_KEY_ORG", "OH_API_KEY"):
        value = os.getenv(env_name)
        if value:
            return value.strip()
    raise OpenHandsAPIError(
        "Missing OpenHands API key. Set OPENHANDS_API_KEY (or OPENHANDS_API_KEY_ORG / OH_API_KEY)."
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
        raise OpenHandsAPIError(f"{method} {url} -> HTTP {exc.code}: {raw[:2000]}") from exc
    except urllib.error.URLError as exc:
        raise OpenHandsAPIError(f"{method} {url} failed: {exc}") from exc


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
        if key in {"status", "summary", "next_gate", "artifact", "result"} and key not in contract:
            contract[key] = value.strip()
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
    run: bool = True,
) -> dict[str, Any]:
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
    return payload


def start_conversation(base: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", endpoint(base, "/api/v1/app-conversations"), headers, payload, timeout=120)


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
    return conversations[0] if isinstance(conversations, list) and conversations else {}


def poll_conversation(
    *,
    base: str,
    headers: dict[str, str],
    conversation_id: str,
    timeout_seconds: int = 1800,
    poll_seconds: int = 20,
) -> dict[str, Any]:
    """Wait until the conversation reaches a terminal execution status."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        conversation = get_conversation(base, headers, conversation_id)
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
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_id: str | None = None
    while True:
        query: dict[str, Any] = {"sort_order": "TIMESTAMP", "limit": limit}
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
        items.extend(page.get("items", []))
        page_id = page.get("next_page_id")
        if not page_id:
            return items


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
        if action.get("kind") == "FinishAction" and action.get("message"):
            return str(action.get("message", "")).strip()
    for event in reversed(events):
        if event.get("source") != "agent":
            continue
        llm_message = event.get("llm_message") if isinstance(event.get("llm_message"), dict) else {}
        text = _content_text(llm_message.get("content"))
        if text:
            return text.strip()
    return ""


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
        text = latest_agent_text(fetch_events(base=base, headers=headers, conversation_id=conversation_id))
        if text or attempt == retries:
            return text
        time.sleep(retry_seconds)
    return ""


def conversation_url(base: str, conversation_id: str) -> str:
    return f"{base.rstrip('/')}/conversations/{conversation_id}"


def conversation_summary(base: str, conversation_id: str, record: dict[str, Any] | None = None) -> dict[str, Any]:
    record = record or {}
    return {
        "id": conversation_id,
        "ui_url": conversation_url(base, conversation_id),
        "title": record.get("title"),
        "execution_status": record.get("execution_status"),
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
        raise OpenHandsAPIError(f"start task {task_id} returned no conversation id")
    return {"id": conversation_id, "ui_url": conversation_url(base, conversation_id)}


def get_status(base: str, key: str, conversation_id: str) -> str:
    record = get_conversation(base, build_headers(key), conversation_id)
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
