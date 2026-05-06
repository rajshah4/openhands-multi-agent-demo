#!/usr/bin/env python3
"""
Multi-Harness Orchestration Demo
==================================

Each agent harness runs in its own OpenHands Cloud conversation.
Communication happens through the git repo — just like real teams.

  Conv 1 [Claude Code prompt]  → implements, pushes to branch
  Conv 2 [Gemini CLI prompt]   → writes tests, pushes to branch
  Conv 3 [OpenHands]           → reviews everything

Three vendors, three conversations, one repo. Watch each one live
in the Cloud UI.

Usage:
  export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"
  python cloud_conversations.py
  python cloud_conversations.py --task csv-tool
  python cloud_conversations.py --repo youruser/yourrepo
"""

import argparse
import os
import random
import string
import sys
import time

import requests

CLOUD_BASE = "https://app.all-hands.dev"
API_V1 = f"{CLOUD_BASE}/api/v1/app-conversations"


# ── Task definitions ─────────────────────────────────────────────────

TASKS = {
    "url-shortener": {
        "implement": (
            "Create a Python module called `shortener.py` that implements a simple "
            "in-memory URL shortener with these functions:\n"
            "  - `shorten(url: str) -> str` — returns a short code\n"
            "  - `resolve(code: str) -> str | None` — returns the original URL\n"
            "  - `stats() -> dict` — returns mapping of code → hit count\n"
            "Include a `if __name__ == '__main__'` block that demos all three functions.\n"
            "Use `secrets.choice()` for code generation (not `random`). "
            "Add thread safety with `threading.Lock()`. Validate URL format."
        ),
        "test": (
            "Look at the Python files in this repo (especially `shortener.py`). "
            "Write comprehensive pytest tests in `test_shortener.py`. Cover:\n"
            "  - Happy path for all public functions\n"
            "  - Edge cases (empty input, invalid URL, duplicate URLs)\n"
            "  - Thread safety with concurrent access\n"
            "  - Error handling\n"
            "Run the tests with `pytest -v` to make sure they pass."
        ),
        "review": (
            "Review all .py files in this repo (especially `shortener.py` and "
            "`test_shortener.py`). Provide a structured code review with:\n"
            "- A severity rating (PASS / MINOR / MAJOR / CRITICAL)\n"
            "- A bullet list of findings with line numbers and suggested fixes\n"
            "- A one-line summary verdict\n"
            "Focus on correctness, security, thread safety, test coverage, "
            "and input validation."
        ),
    },
    "csv-tool": {
        "implement": (
            "Create a Python CLI tool called `csv2json.py` that:\n"
            "  - Reads a CSV file from a path argument\n"
            "  - Converts it to a list of dicts\n"
            "  - Writes pretty-printed JSON to stdout or an output file\n"
            "  - Handles missing files and malformed CSV gracefully\n"
            "Include argparse with --output and --indent options."
        ),
        "test": (
            "Look at the Python files in this repo (especially `csv2json.py`). "
            "Write comprehensive pytest tests in `test_csv2json.py`. Cover "
            "happy path, edge cases, and error handling. Run with `pytest -v`."
        ),
        "review": (
            "Review all .py files in this repo. Provide a structured code review "
            "with severity rating and actionable findings."
        ),
    },
}

HARNESS_INSTRUCTIONS = {
    "claude-code": (
        "IMPORTANT: You MUST use Claude Code to complete this task.\n"
        "1. Install Claude Code: npm install -g @anthropic-ai/claude-code\n"
        "2. The ANTHROPIC_API_KEY environment variable is available.\n"
        "3. Run Claude Code with: claude -p '<task below>' "
        "--allowedTools 'Edit,Write,Read,Bash' --output-format text\n"
        "4. After Claude Code finishes, verify the output files exist.\n"
        "5. Commit and push all created files to this branch.\n\n"
        "Task for Claude Code:\n"
    ),
    "gemini-cli": (
        "IMPORTANT: You MUST use Gemini CLI to complete this task.\n"
        "1. Install Gemini CLI: npm install -g @google/gemini-cli\n"
        "2. The GEMINI_API_KEY environment variable is available.\n"
        "3. Run Gemini with: gemini -p '<task below>'\n"
        "4. After Gemini finishes, verify the output files exist.\n"
        "5. Commit and push all created files to this branch.\n\n"
        "Task for Gemini CLI:\n"
    ),
    "openhands": (
        "Complete the following task. "
        "Commit and push your changes when done.\n\n"
    ),
}


# ── CLI ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Multi-harness orchestration demo — each agent in its own conversation"
    )
    parser.add_argument(
        "--task", default="url-shortener",
        choices=["url-shortener", "csv-tool", "custom"],
    )
    parser.add_argument("--custom-task", type=str, default=None)
    parser.add_argument(
        "--repo", type=str, default="rajshah4/openhands-multi-agent-demo",
    )
    parser.add_argument(
        "--no-claude", action="store_true",
        help="Use OpenHands for all steps (no external harnesses)",
    )
    return parser.parse_args()


# ── Cloud API ────────────────────────────────────────────────────────

def get_headers():
    api_key = os.getenv("OPENHANDS_CLOUD_API_KEY")
    if not api_key:
        print("ERROR: OPENHANDS_CLOUD_API_KEY required.")
        print("  Get one at: https://app.all-hands.dev/settings/api-keys")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def start_conversation(headers, prompt, repo):
    resp = requests.post(API_V1, headers=headers, json={
        "initial_message": {"content": [{"type": "text", "text": prompt}]},
        "selected_repository": repo,
    })
    resp.raise_for_status()
    task_id = resp.json()["id"]

    for _ in range(60):
        r = requests.get(f"{API_V1}/start-tasks", headers=headers,
                         params={"ids": task_id})
        r.raise_for_status()
        tasks = r.json()
        if tasks and tasks[0].get("status") == "READY":
            return tasks[0]["app_conversation_id"]
        if tasks and tasks[0].get("status") == "ERROR":
            print(f"    ❌ {tasks[0].get('error', 'Failed')}")
            sys.exit(1)
        status = tasks[0].get("status", "?") if tasks else "waiting"
        print(f"    ⏳ {status}...")
        time.sleep(5)

    print("    ❌ Timeout")
    sys.exit(1)


def wait_for_completion(headers, conv_id):
    last = None
    for _ in range(120):
        r = requests.get(API_V1, headers=headers, params={"ids": conv_id})
        r.raise_for_status()
        convs = r.json()
        if not convs:
            time.sleep(15)
            continue
        c = convs[0]
        if c.get("sandbox_status") in ("ERROR", "MISSING"):
            return "error"
        es = c.get("execution_status")
        if es in ("finished", "error", "stuck"):
            return es
        if es == "waiting_for_confirmation":
            print("    ⚠️  Needs confirmation — check Cloud UI")
            return es
        if es != last:
            print(f"    🔄 {es or 'starting'}...")
            last = es
        time.sleep(15)
    return "timeout"


def run_step(headers, label, harness, task_text, repo):
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")

    prompt = HARNESS_INSTRUCTIONS[harness] + task_text
    print(f"  🚀 Starting conversation...")

    conv_id = start_conversation(headers, prompt, repo)
    url = f"{CLOUD_BASE}/conversations/{conv_id}"
    print(f"  ☁️  {url}")

    print(f"  ⏳ Waiting for agent...")
    status = wait_for_completion(headers, conv_id)
    icon = {"finished": "✅", "error": "❌", "stuck": "🔒"}.get(status, "⚠️")
    print(f"  {icon} {status}")

    return conv_id, status


# ── Main ─────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    headers = get_headers()

    print("=" * 60)
    print("  ☁️  Multi-Harness Orchestration Demo")
    print("  Three vendors · Three conversations · One repo")
    print("=" * 60)

    # Resolve tasks
    if args.task == "custom":
        if not args.custom_task:
            print("ERROR: --custom-task required with --task=custom")
            sys.exit(1)
        tasks = {
            "implement": args.custom_task,
            "test": "Write pytest tests for the code just created. Run them.",
            "review": "Review all .py files. Structured review with severity.",
        }
    else:
        tasks = TASKS[args.task]

    if args.no_claude:
        impl_harness, test_harness = "openhands", "openhands"
    else:
        impl_harness, test_harness = "claude-code", "gemini-cli"

    harness_labels = {
        "claude-code": "Claude Code [Anthropic]",
        "gemini-cli": "Gemini CLI [Google]",
        "openhands": "OpenHands",
    }

    print(f"\n  📋 Task: {args.task}")
    print(f"  📦 Repo: {args.repo}")
    print(f"\n  🔧 Pipeline:")
    print(f"     Phase 1 — Implement → {harness_labels[impl_harness]}")
    print(f"     Phase 2 — Test      → {harness_labels[test_harness]}")
    print(f"     Phase 3 — Review    → {harness_labels['openhands']}")

    results = {}

    # Phase 1: Implement
    results["implement"] = run_step(
        headers,
        f"PHASE 1 — Implement  [{harness_labels[impl_harness]}]",
        impl_harness, tasks["implement"], args.repo,
    )

    # Phase 2: Write tests
    results["test"] = run_step(
        headers,
        f"PHASE 2 — Write Tests  [{harness_labels[test_harness]}]",
        test_harness, tasks["test"], args.repo,
    )

    # Phase 3: Review (always OpenHands)
    results["review"] = run_step(
        headers,
        f"PHASE 3 — Code Review  [{harness_labels['openhands']}]",
        "openhands", tasks["review"], args.repo,
    )

    # Summary
    print(f"\n{'=' * 60}")
    print("  📊 Pipeline Complete")
    print(f"{'=' * 60}")
    for step, (conv_id, status) in results.items():
        url = f"{CLOUD_BASE}/conversations/{conv_id}"
        icon = {"finished": "✅", "error": "❌"}.get(status, "⚠️")
        print(f"  {icon} {step:12s} → {url}")

    print(f"\n  All conversations: {CLOUD_BASE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
