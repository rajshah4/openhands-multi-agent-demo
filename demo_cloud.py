#!/usr/bin/env python3
"""
Cloud-Native Multi-Agent Orchestration Demo
============================================

Every agent harness runs as its own OpenHands Cloud conversation —
fully visible, auditable, and observable in the Cloud UI.

Architecture:
  Your Laptop (orchestrator)
  │
  ├─► ☁️ Conversation 1: Implement (write the code)
  │
  ├─► ☁️ Conversation 2: Review   (find issues)
  │
  └─► ☁️ Conversation 3: Fix      (address findings)

Each conversation appears independently in https://app.all-hands.dev

Usage:
  export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"
  python demo_cloud.py
  python demo_cloud.py --task csv-tool
  python demo_cloud.py --task custom --custom-task "Build a rate limiter"
  python demo_cloud.py --repo youruser/yourrepo
"""

import argparse
import os
import sys
import time

import requests

# ── Constants ────────────────────────────────────────────────────────

CLOUD_BASE = "https://app.all-hands.dev"
API_V1 = f"{CLOUD_BASE}/api/v1/app-conversations"
POLL_INTERVAL_START = 5     # seconds between start-task polls
POLL_INTERVAL_RUN = 15      # seconds between execution polls
START_TIMEOUT = 300          # 5 min to provision sandbox
RUN_TIMEOUT = 600            # 10 min per conversation


# ── Task definitions ─────────────────────────────────────────────────

CLAUDE_CODE_PREAMBLE = (
    "IMPORTANT: For this task, you MUST use Claude Code as the implementation tool.\n"
    "Steps:\n"
    "1. Install Claude Code: npm install -g @anthropic-ai/claude-code\n"
    "2. Run Claude Code with the task below using: "
    "claude -p '<task>' --allowedTools 'Edit,Write,Read,Bash' "
    "--output-format text\n"
    "3. The ANTHROPIC_API_KEY environment variable is already available.\n"
    "4. After Claude Code finishes, verify the output files exist.\n\n"
    "The task for Claude Code:\n"
)

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
        "review": (
            "Review the file `shortener.py` in this repo. Provide a structured "
            "code review with:\n"
            "- A severity rating (PASS / MINOR / MAJOR / CRITICAL)\n"
            "- A bullet list of findings with line numbers and suggested fixes\n"
            "- A one-line summary verdict\n"
            "Focus on correctness, security, thread safety, and input validation."
        ),
        "fix": (
            "Read the code review findings that were left as comments or in any "
            "review files. Fix all MAJOR and CRITICAL issues found in `shortener.py`. "
            "Run the module afterwards to verify it works."
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
        "review": (
            "Review the file `csv2json.py` in this repo. Provide a structured "
            "code review with severity rating and actionable findings."
        ),
        "fix": (
            "Fix all MAJOR and CRITICAL issues found in the code review of "
            "`csv2json.py`. Run the tool with a sample CSV to verify it works."
        ),
    },
}


# ── CLI ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Cloud-native multi-agent orchestration demo"
    )
    parser.add_argument(
        "--task",
        default="url-shortener",
        choices=["url-shortener", "csv-tool", "custom"],
        help="Which demo task to run (default: url-shortener)",
    )
    parser.add_argument(
        "--custom-task",
        type=str,
        default=None,
        help="Custom implementation task (use with --task custom)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="rajshah4/openhands-multi-agent-demo",
        help="GitHub repo for the conversations (default: rajshah4/openhands-multi-agent-demo)",
    )
    parser.add_argument(
        "--use-claude",
        action="store_true",
        help="Use Claude Code as the implementation harness "
             "(requires ANTHROPIC_API_KEY in OpenHands Cloud secrets)",
    )
    parser.add_argument(
        "--skip-fix",
        action="store_true",
        help="Skip the fix step (only implement + review)",
    )
    return parser.parse_args()


# ── Cloud API helpers ────────────────────────────────────────────────

def get_headers():
    api_key = os.getenv("OPENHANDS_CLOUD_API_KEY")
    if not api_key:
        print("ERROR: OPENHANDS_CLOUD_API_KEY is required.")
        print("  1. Go to https://app.all-hands.dev → Settings → API Keys")
        print("  2. Create a key and export it:")
        print("     export OPENHANDS_CLOUD_API_KEY='your-key'")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def start_conversation(headers: dict, task: str, repo: str) -> str:
    """Start a Cloud conversation and return its app_conversation_id."""
    resp = requests.post(API_V1, headers=headers, json={
        "initial_message": {
            "content": [{"type": "text", "text": task}],
        },
        "selected_repository": repo,
    })
    resp.raise_for_status()
    task_id = resp.json()["id"]

    # Poll start task until sandbox is ready
    elapsed = 0
    while elapsed < START_TIMEOUT:
        status_resp = requests.get(
            f"{API_V1}/start-tasks",
            headers=headers,
            params={"ids": task_id},
        )
        status_resp.raise_for_status()
        tasks = status_resp.json()

        if tasks and tasks[0].get("status") == "READY":
            return tasks[0]["app_conversation_id"]
        elif tasks and tasks[0].get("status") == "ERROR":
            error = tasks[0].get("error", "Unknown error")
            print(f"    ❌ Start failed: {error}")
            sys.exit(1)
        else:
            status = tasks[0].get("status", "unknown") if tasks else "no response"
            print(f"    ⏳ {status}...")

        time.sleep(POLL_INTERVAL_START)
        elapsed += POLL_INTERVAL_START

    print("    ❌ Timeout waiting for sandbox")
    sys.exit(1)


def wait_for_completion(headers: dict, conversation_id: str) -> str:
    """Poll until the conversation finishes. Returns the final status."""
    elapsed = 0
    last_status = None

    while elapsed < RUN_TIMEOUT:
        resp = requests.get(
            API_V1,
            headers=headers,
            params={"ids": conversation_id},
        )
        resp.raise_for_status()
        conversations = resp.json()

        if not conversations:
            time.sleep(POLL_INTERVAL_RUN)
            elapsed += POLL_INTERVAL_RUN
            continue

        conv = conversations[0]
        sandbox_status = conv.get("sandbox_status")
        exec_status = conv.get("execution_status")

        # Sandbox-level failures
        if sandbox_status in ("ERROR", "MISSING"):
            print(f"    ❌ Sandbox failed: {sandbox_status}")
            return "error"

        # Terminal execution states
        if exec_status in ("finished", "error", "stuck"):
            return exec_status

        if exec_status == "waiting_for_confirmation":
            print(f"    ⚠️  Agent needs confirmation — visit the Cloud UI")
            return "waiting_for_confirmation"

        # Progress indicator
        if exec_status != last_status:
            print(f"    🔄 {exec_status or 'starting'}...")
            last_status = exec_status

        time.sleep(POLL_INTERVAL_RUN)
        elapsed += POLL_INTERVAL_RUN

    print("    ❌ Timeout waiting for completion")
    return "timeout"


def run_step(headers: dict, label: str, task: str, repo: str) -> str:
    """Run one pipeline step as a Cloud conversation. Returns conversation_id."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    print(f"  📝 Task: {task[:100]}...")

    print(f"\n  🚀 Starting conversation...")
    conversation_id = start_conversation(headers, task, repo)
    url = f"{CLOUD_BASE}/conversations/{conversation_id}"
    print(f"  ☁️  {url}")

    print(f"\n  ⏳ Waiting for agent to finish...")
    status = wait_for_completion(headers, conversation_id)

    status_icon = {"finished": "✅", "error": "❌", "stuck": "🔒"}.get(status, "⚠️")
    print(f"\n  {status_icon} Status: {status}")

    return conversation_id


# ── Main ─────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    headers = get_headers()

    print("=" * 60)
    print("  ☁️  Cloud-Native Multi-Agent Orchestration Demo")
    print("  Each harness = its own Cloud conversation")
    print("=" * 60)

    # Resolve tasks
    if args.task == "custom":
        if not args.custom_task:
            print("ERROR: --custom-task is required when --task=custom")
            sys.exit(1)
        tasks = {
            "implement": args.custom_task,
            "review": (
                "Review all .py files in this repo that were just created. "
                "Provide a structured code review with severity rating and findings."
            ),
            "fix": (
                "Fix all MAJOR and CRITICAL issues found in the code review. "
                "Run the code afterwards to verify it works."
            ),
        }
    else:
        tasks = dict(TASKS[args.task])  # copy so we can modify

    # If --use-claude, wrap the implementation task with Claude Code instructions
    if args.use_claude:
        impl_harness = "Claude Code (via OpenHands sandbox)"
        tasks["implement"] = CLAUDE_CODE_PREAMBLE + tasks["implement"]
    else:
        impl_harness = "OpenHands Agent"

    print(f"\n  📋 Task: {args.task}")
    print(f"  📦 Repo: {args.repo}")
    print(f"\n  🔧 Harnesses:")
    print(f"     Implement → {impl_harness}")
    print(f"     Review    → OpenHands Agent (file-based code-reviewer)")
    print(f"     Fix       → OpenHands Agent")

    conversations = {}

    # Step 1: Implement
    label = "STEP 1 — Implement"
    if args.use_claude:
        label += " (Claude Code)"
    conversations["implement"] = run_step(
        headers,
        label,
        tasks["implement"],
        args.repo,
    )

    # Step 2: Review (always OpenHands)
    conversations["review"] = run_step(
        headers,
        "STEP 2 — Code Review (OpenHands)",
        tasks["review"],
        args.repo,
    )

    # Step 3: Fix (optional, always OpenHands)
    if not args.skip_fix:
        conversations["fix"] = run_step(
            headers,
            "STEP 3 — Fix Issues (OpenHands)",
            tasks["fix"],
            args.repo,
        )

    # Summary
    harness_labels = {
        "implement": impl_harness,
        "review": "OpenHands Agent",
        "fix": "OpenHands Agent",
    }

    print(f"\n{'=' * 60}")
    print("  📊 Pipeline Summary")
    print(f"{'=' * 60}")
    for step, conv_id in conversations.items():
        url = f"{CLOUD_BASE}/conversations/{conv_id}"
        harness = harness_labels.get(step, "")
        print(f"  {step:12s} [{harness}]")
        print(f"               → {url}")

    print(f"\n  All conversations visible at: {CLOUD_BASE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
