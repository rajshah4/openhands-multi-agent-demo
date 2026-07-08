#!/usr/bin/env python3
"""Polling continuation workflow pattern.

Run this from cron or an OpenHands scheduled automation every 15 minutes. Each
wake-up checks durable state, takes at most one action, appends a stable worklog
marker, and exits. The next wake-up observes the new state and continues.

This mirrors the "fire and forget" shape used by workflow plugins such as the
OHTV example: the orchestrator does not wait for workers forever; it keeps the
system moving through repeated state checks.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


SPAWN_MARKER = "<!-- orchestrator-status: spawn -->"
QUIET_MARKER = "<!-- orchestrator-status: quiet -->"


def default_state() -> dict[str, Any]:
    return {
        "quiet_count": 0,
        "active_workers": [],
        "issues": [
            {"id": "ISSUE-1", "state": "new", "priority": None},
            {"id": "ISSUE-2", "state": "ready", "priority": "high"},
        ],
        "prs": [
            {"id": "PR-1", "state": "needs-docs"},
        ],
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state()
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def choose_action(state: dict[str, Any]) -> tuple[str, str]:
    active = state.get("active_workers", [])
    if active:
        return "quiet", f"Workers still active: {', '.join(active)}"

    for issue in state.get("issues", []):
        if issue.get("state") == "new":
            issue["state"] = "expanding"
            state["active_workers"] = [f"expansion:{issue['id']}"]
            return "spawn", f"Spawn expansion worker for {issue['id']}"

    for issue in state.get("issues", []):
        if issue.get("state") == "ready" and not issue.get("priority"):
            issue["priority"] = "medium"
            return "spawn", f"Assess priority for {issue['id']}"

    ready = [
        issue for issue in state.get("issues", [])
        if issue.get("state") == "ready" and issue.get("priority") in {"critical", "high", "medium"}
    ]
    if ready:
        issue = sorted(ready, key=lambda item: {"critical": 0, "high": 1, "medium": 2}[item["priority"]])[0]
        issue["state"] = "in-progress"
        state["active_workers"] = [f"implementation:{issue['id']}"]
        return "spawn", f"Spawn implementation worker for {issue['id']}"

    for pr in state.get("prs", []):
        if pr.get("state") == "needs-docs":
            pr["state"] = "docs-running"
            state["active_workers"] = [f"docs:{pr['id']}"]
            return "spawn", f"Spawn documentation worker for {pr['id']}"
        if pr.get("state") == "needs-test":
            pr["state"] = "testing-running"
            state["active_workers"] = [f"testing:{pr['id']}"]
            return "spawn", f"Spawn testing worker for {pr['id']}"
        if pr.get("state") == "ready-for-review":
            pr["state"] = "review-running"
            state["active_workers"] = [f"review:{pr['id']}"]
            return "spawn", f"Spawn review worker for {pr['id']}"

    return "quiet", "No work is ready"


def append_worklog(path: Path, status: str, message: str) -> None:
    marker = SPAWN_MARKER if status == "spawn" else QUIET_MARKER
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {timestamp}\n\n{marker}\n\n{message}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=Path(".workflow-state.json"))
    parser.add_argument("--worklog", type=Path, default=Path("WORKLOG.md"))
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--quiet-limit", type=int, default=2)
    parser.add_argument("--clear-active-workers", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = load_state(args.state_file)
    if args.clear_active_workers:
        state["active_workers"] = []

    status, message = choose_action(state)
    if status == "spawn":
        state["quiet_count"] = 0
    else:
        state["quiet_count"] = int(state.get("quiet_count", 0)) + 1

    should_disable = status == "quiet" and state["quiet_count"] >= args.quiet_limit
    if should_disable:
        message += f"; quiet for {state['quiet_count']} wake-ups, automation can disable itself"

    if not args.dry_run:
        save_state(args.state_file, state)
        append_worklog(args.worklog, status, message)

    print(
        json.dumps(
            {
                "status": status,
                "message": message,
                "next_wake_minutes": args.interval_minutes,
                "quiet_count": state.get("quiet_count", 0),
                "should_disable": should_disable,
                "active_workers": state.get("active_workers", []),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
