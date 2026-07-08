#!/usr/bin/env python3
"""Supervisor pattern: one orchestrator runs a full lifecycle of child conversations, now.

One request -> plan -> build -> check -> lifecycle report.

The orchestrator starts each child conversation, waits for its final response,
parses the small status contract, and gates before starting the next cell.
All evidence must come back in the final response - the contract IS the
interface.

Run it against OpenHands Cloud/Enterprise (default) or a local Agent Canvas:

    export OPENHANDS_API_KEY=...            # and OPENHANDS_BASE_URL for self-hosted
    python3 run_supervisor.py --request "a Python function slugify(text) for URL slugs"

    python3 run_supervisor.py --runtime canvas   # local Agent Canvas at localhost:8000

    python3 run_supervisor.py --dry-run          # no API key needed: prints the payloads

The two runtimes expose different APIs (app-conversations + start tasks vs.
local conversations + agent_final_response); the pattern does not care - both
backends in ../common expose the same start/status/final surface.

This is the same pattern that runs a full software factory in
https://github.com/rajshah4/sdlc-automation-github-demo - there the cells are
story-to-pr / code-review / qa and the children work on a real repository.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import openhands_conversations as util  # noqa: E402 - runtime-independent helpers


PATTERN_ROOT = Path(__file__).resolve().parent
PROMPT_ROOT = PATTERN_ROOT / "prompts" / "workcells"
DEFAULT_CELLS = ("plan", "build", "check")

# Which child statuses allow the lifecycle to continue past each cell.
CONTINUE_STATUSES = {
    "plan": {"done"},
    "build": {"done"},
    "check": {"pass", "findings"},
}


def load_runtime(name: str):
    """Both runtime modules expose the same function surface."""
    if name == "canvas":
        import canvas_conversations as runtime
    else:
        import openhands_conversations as runtime
    return runtime


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def start_and_wait_cell(
    *,
    args: argparse.Namespace,
    runtime,
    base: str,
    key: str,
    run_dir: Path,
    cell: str,
    prior_summary: str,
) -> dict[str, Any]:
    """Run one child conversation to completion and return its gate entry."""
    prompt = util.render_prompt(
        PROMPT_ROOT / f"{cell}.md",
        {
            "run_id": args.run_id,
            "request": args.request,
            "prior_summary": prior_summary or "none - you are the first work cell",
        },
    )
    write_text(run_dir / f"{cell}.prompt.md", prompt)

    payload_extra: dict[str, Any] = {}
    if args.runtime == "canvas":
        # Canvas children share a local working tree; keep it inside the run dir.
        workspace = run_dir / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        payload_extra["workspace_dir"] = str(workspace)
    payload = runtime.build_start_payload(
        prompt=prompt,
        title=f"{args.run_id} {cell}",
        llm_model=args.child_llm_model,
        **payload_extra,
    )

    if args.dry_run:
        print(f"--- dry-run payload for cell '{cell}' ---", file=sys.stderr)
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return {"name": cell, "status": "dry-run", "final_text": "", "ui_url": None}

    worker = runtime.start_worker(base, key, payload)
    entry: dict[str, Any] = {"name": cell, **worker}
    print(f"[{cell}] child conversation: {entry['ui_url']}")

    deadline = time.monotonic() + args.cell_timeout_seconds
    status = ""
    while time.monotonic() < deadline:
        status = runtime.get_status(base, key, entry["id"])
        if status in runtime.TERMINAL_EXECUTION_STATUSES:
            break
        time.sleep(args.poll_seconds)
    else:
        entry["status"] = "failed"
        entry["error"] = f"timed out after {args.cell_timeout_seconds}s (last status: {status})"
        return entry

    final_text = runtime.get_final(base, key, entry["id"])
    contract = util.parse_contract(final_text)
    entry["execution_status"] = status
    entry["status"] = contract.get("status", status)
    entry["contract"] = contract
    entry["final_text"] = final_text
    write_text(run_dir / f"{cell}.final.md", final_text + ("\n" if final_text else ""))
    return entry


def lifecycle_report(args: argparse.Namespace, entries: list[dict[str, Any]]) -> str:
    lines = [
        "# Supervisor Lifecycle Report",
        "",
        f"- Run id: `{args.run_id}`",
        f"- Runtime: `{args.runtime}`",
        f"- Request: {args.request}",
        "",
        "## Child Conversations",
        "",
        "| Work cell | Status | Conversation | Final response |",
        "| --- | --- | --- | --- |",
    ]
    for entry in entries:
        url = entry.get("ui_url") or ""
        link = f"[{entry.get('id')}]({url})" if entry.get("id") and url else "-"
        lines.append(
            f"| `{entry['name']}` | {entry.get('status', 'unknown')} | {link} "
            f"| `runs/{args.run_id}/{entry['name']}.final.md` |"
        )
    lines.extend(["", "## Gate Decisions", ""])
    for entry in entries:
        allowed = CONTINUE_STATUSES.get(entry["name"], {"done"})
        verdict = "continue" if entry.get("status") in allowed else "stop"
        lines.append(f"- `{entry['name']}` returned `{entry.get('status')}` -> {verdict}")
    lines.extend(
        [
            "",
            "## Human Next Step",
            "",
            "Read the check cell's findings, then decide whether the result is",
            "acceptable. The supervisor reports; humans decide.",
            "",
        ]
    )
    return "\n".join(lines)


def run_supervisor(args: argparse.Namespace) -> int:
    runtime = load_runtime(args.runtime)
    if args.env_file:
        util.load_env_file(args.env_file)

    base = runtime.base_url(args.base_url)
    key = "" if args.dry_run else runtime.read_api_key()

    run_dir = PATTERN_ROOT / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    prior_summary = ""
    for cell in args.cells:
        entry = start_and_wait_cell(
            args=args,
            runtime=runtime,
            base=base,
            key=key,
            run_dir=run_dir,
            cell=cell,
            prior_summary=prior_summary,
        )
        entries.append(entry)
        write_json(run_dir / "children.json", entries)

        prior_summary += (
            f"\n\n## {cell}\nstatus: {entry.get('status')}\n{entry.get('final_text', '')}"
        )
        if not args.dry_run and entry.get("status") not in CONTINUE_STATUSES.get(cell, {"done"}):
            print(f"[{cell}] gate stopped the lifecycle (status: {entry.get('status')})")
            break

    write_text(run_dir / "lifecycle-report.md", lifecycle_report(args, entries))
    print(json.dumps({"run_dir": str(run_dir), "cells": [
        {"name": e["name"], "status": e.get("status"), "ui_url": e.get("ui_url")} for e in entries
    ]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--request",
        default="a Python function slugify(text) that converts titles into URL-safe slugs",
        help="what the lifecycle should produce",
    )
    parser.add_argument("--run-id", default=time.strftime("supervisor-%Y%m%d-%H%M%S"))
    parser.add_argument("--cells", nargs="+", choices=DEFAULT_CELLS, default=list(DEFAULT_CELLS))
    parser.add_argument(
        "--runtime",
        choices=("cloud", "canvas"),
        default="cloud",
        help="cloud = OpenHands Cloud/Enterprise app-conversations API; canvas = local Agent Canvas",
    )
    parser.add_argument("--base-url", help="override the runtime's base URL")
    parser.add_argument("--env-file", type=Path, help="optional KEY=value env file")
    parser.add_argument("--child-llm-model", help="optional model override for child conversations (cloud runtime)")
    parser.add_argument("--cell-timeout-seconds", type=int, default=1200)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true", help="print API payloads instead of calling OpenHands")
    return parser


def main() -> int:
    return run_supervisor(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
