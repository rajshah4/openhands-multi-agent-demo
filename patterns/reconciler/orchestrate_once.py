#!/usr/bin/env python3
"""Reconciler pattern: a stateless orchestrator tick that keeps a backlog moving, forever.

Each run of this script is ONE wake-up (a "tick"). A tick:

1. checks INSTRUCTIONS.md - a human note pauses the loop (needs-human)
2. checks the in-flight worker conversation, if any
   - still running  -> log a quiet tick and exit
   - finished       -> record its result, mark the task done, exit
3. otherwise claims the next pending backlog task and spawns ONE real
   OpenHands worker conversation - fire and forget - and exits
4. if there is no work at all, counts quiet ticks; after two, reports that a
   scheduled automation would disable itself

The orchestrator holds no memory between ticks. Everything it knows lives in
durable state on disk (state.json + WORKLOG.md), so any tick can crash and the
next one recovers. That is the reconciliation-loop idea: observe state, take at
most one convergent action, exit.

Run ticks by hand to watch the state machine advance:

    export OPENHANDS_API_KEY=...            # and OPENHANDS_BASE_URL for self-hosted
    python3 orchestrate_once.py             # tick 1: claims task-1, spawns worker
    python3 orchestrate_once.py             # tick 2: worker running -> quiet
    python3 orchestrate_once.py             # tick 3: worker done -> records result
    ...
    python3 orchestrate_once.py --watch     # or loop locally every 60s

    python3 orchestrate_once.py --runtime canvas   # workers on local Agent Canvas
    python3 orchestrate_once.py --dry-run          # no API key: prints the decision + payload

In production the tick runs on a schedule (cron automation) instead of a local
loop - see the README. Pattern credit: the production reference is the
ohtv-workflow plugin (github.com/jpshackelford/.openhands), which runs its own
project this way with GitHub issues and labels as the durable state.
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
BACKLOG_SEED = PATTERN_ROOT / "backlog.json"
WORKER_PROMPT = PATTERN_ROOT / "prompts" / "worker.md"
QUIET_LIMIT = 2


def load_runtime(name: str):
    """Both runtime modules expose the same function surface."""
    if name == "canvas":
        import canvas_conversations as runtime
    else:
        import openhands_conversations as runtime
    return runtime


# ---------------------------------------------------------------------------
# Durable state
# ---------------------------------------------------------------------------

def load_state(state_path: Path) -> dict[str, Any]:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    seed = json.loads(BACKLOG_SEED.read_text(encoding="utf-8"))
    return {
        "tasks": [
            {"id": task["id"], "prompt": task["prompt"], "status": "pending"}
            for task in seed["tasks"]
        ],
        "in_flight": None,
        "quiet_ticks": 0,
        "tick_count": 0,
    }


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_worklog(worklog_path: Path, tick: int, action: str, detail: str) -> None:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = f"\n## Tick {tick} - {timestamp}\n\n- action: **{action}**\n- {detail}\n"
    with worklog_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def pending_instruction(instructions_path: Path) -> str:
    if instructions_path.exists():
        text = instructions_path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return ""


# ---------------------------------------------------------------------------
# One tick
# ---------------------------------------------------------------------------

def tick_outcome(action: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"action": action, "detail": detail, **extra}


def check_in_flight(state: dict[str, Any], args: argparse.Namespace, results_dir: Path) -> dict[str, Any]:
    """The in-flight branch: observe the worker, record its result if done."""
    in_flight = state["in_flight"]
    # Observe through the runtime that spawned the worker, not today's flag.
    runtime = load_runtime(in_flight.get("runtime", args.runtime))
    base = runtime.base_url(args.base_url)
    key = runtime.read_api_key()
    conversation_id = in_flight["conversation_id"]

    execution_status = runtime.get_status(base, key, conversation_id)
    if execution_status not in runtime.TERMINAL_EXECUTION_STATUSES:
        return tick_outcome(
            "quiet",
            f"worker for `{in_flight['task_id']}` still {execution_status or 'starting'}: {in_flight['ui_url']}",
        )

    final_text = runtime.get_final(base, key, conversation_id)
    contract = util.parse_contract(final_text)
    task_status = "done" if contract.get("status") == "done" and execution_status == "finished" else "failed"

    results_dir.mkdir(parents=True, exist_ok=True)
    result_path = results_dir / f"{in_flight['task_id']}.md"
    result_path.write_text(final_text + ("\n" if final_text else ""), encoding="utf-8")

    for task in state["tasks"]:
        if task["id"] == in_flight["task_id"]:
            task["status"] = task_status
            task["conversation_url"] = in_flight["ui_url"]
            task["result_file"] = str(result_path.relative_to(PATTERN_ROOT))
    state["in_flight"] = None
    return tick_outcome(
        "recorded",
        f"worker for `{in_flight['task_id']}` finished ({execution_status}); "
        f"task marked `{task_status}`; result: `{result_path.name}`",
    )


def claim_and_spawn(state: dict[str, Any], task: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """The dispatch branch: spawn one worker, fire and forget."""
    runtime = load_runtime(args.runtime)
    prompt = util.render_prompt(WORKER_PROMPT, {"task_id": task["id"], "task_prompt": task["prompt"]})

    payload_extra: dict[str, Any] = {}
    if args.runtime == "canvas":
        # Canvas workers share a local working tree; keep it out of the repo.
        workspace = PATTERN_ROOT / "results" / "canvas-workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        payload_extra["workspace_dir"] = str(workspace)
    payload = runtime.build_start_payload(
        prompt=prompt, title=f"reconciler worker {task['id']}", **payload_extra
    )

    if args.dry_run:
        print(f"--- dry-run payload for `{task['id']}` ---", file=sys.stderr)
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return tick_outcome("dry-run", f"would spawn worker for `{task['id']}`", mutate=False)

    base = runtime.base_url(args.base_url)
    key = runtime.read_api_key()
    worker = runtime.start_worker(base, key, payload)

    task["status"] = "in-flight"
    state["in_flight"] = {
        "task_id": task["id"],
        "conversation_id": worker["id"],
        "ui_url": worker["ui_url"],
        "runtime": args.runtime,
    }
    return tick_outcome("spawned", f"worker for `{task['id']}`: {worker['ui_url']}")


def run_tick(args: argparse.Namespace) -> dict[str, Any]:
    state_path = PATTERN_ROOT / args.state_file
    worklog_path = PATTERN_ROOT / args.worklog
    instructions_path = PATTERN_ROOT / "INSTRUCTIONS.md"
    results_dir = PATTERN_ROOT / "results"

    state = load_state(state_path)
    state["tick_count"] += 1
    tick = state["tick_count"]

    instruction = pending_instruction(instructions_path)
    if instruction:
        outcome = tick_outcome(
            "needs-human",
            f"INSTRUCTIONS.md is non-empty; pausing until a human clears it. Instruction: {instruction[:200]}",
        )
    elif state["in_flight"]:
        outcome = check_in_flight(state, args, results_dir)
    else:
        next_task = next((t for t in state["tasks"] if t["status"] == "pending"), None)
        if next_task:
            outcome = claim_and_spawn(state, next_task, args)
        else:
            state["quiet_ticks"] += 1
            detail = f"backlog drained; quiet tick {state['quiet_ticks']}/{QUIET_LIMIT}"
            if state["quiet_ticks"] >= QUIET_LIMIT:
                detail += " - a scheduled automation would disable itself now"
            outcome = tick_outcome("quiet", detail)

    if outcome["action"] in {"spawned", "recorded"}:
        state["quiet_ticks"] = 0

    if outcome.pop("mutate", True) and not args.dry_run:
        save_state(state_path, state)
        append_worklog(worklog_path, tick, outcome["action"], outcome["detail"])

    outcome["tick"] = tick
    outcome["tasks"] = {t["id"]: t["status"] for t in state["tasks"]}
    return outcome


def reset(args: argparse.Namespace) -> None:
    for name in (args.state_file, args.worklog):
        path = PATTERN_ROOT / name
        if path.exists():
            path.unlink()
    results_dir = PATTERN_ROOT / "results"
    if results_dir.exists():
        for path in results_dir.iterdir():
            if path.is_file():
                path.unlink()
    print("state reset; next tick starts from the seed backlog")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime",
        choices=("cloud", "canvas"),
        default="cloud",
        help="cloud = OpenHands Cloud/Enterprise app-conversations API; canvas = local Agent Canvas",
    )
    parser.add_argument("--base-url", help="override the runtime's base URL")
    parser.add_argument("--env-file", type=Path, help="optional KEY=value env file")
    parser.add_argument("--state-file", default="state.json")
    parser.add_argument("--worklog", default="WORKLOG.md")
    parser.add_argument("--watch", action="store_true", help="loop locally instead of running one tick")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true", help="print the decision and payload; mutate nothing")
    parser.add_argument("--reset", action="store_true", help="clear state and results, keep the seed backlog")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.env_file:
        util.load_env_file(args.env_file)
    if args.reset:
        reset(args)
        return 0

    while True:
        try:
            outcome = run_tick(args)
        except (util.OpenHandsAPIError, TimeoutError) as exc:
            outcome = {"action": "error", "detail": str(exc)}
        except Exception as exc:  # canvas runtime raises its own error type
            if type(exc).__name__ != "CanvasAPIError":
                raise
            outcome = {"action": "error", "detail": str(exc)}
        print(json.dumps(outcome, indent=2, sort_keys=True))
        if not args.watch:
            return 0 if outcome["action"] != "error" else 2
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
