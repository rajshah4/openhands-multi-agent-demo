#!/usr/bin/env python3
"""
Multi-Harness Orchestration Demo
==================================

Starts an OpenHands Cloud conversation that runs the multi-agent
pipeline INSIDE the sandbox — using real ACP for Claude Code.

What happens:
  1. Cloud API creates a conversation + sandbox
  2. The OH agent inside the sandbox installs deps + Claude Code ACP
  3. Runs pipeline.py which uses ACPAgent (real ACP protocol) for Claude Code
  4. OpenHands agents handle review and fix

The entire pipeline — including real ACP communication — runs inside
the Cloud sandbox and is visible in the Cloud UI.

Usage:
  export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"
  python demo.py
  python demo.py --task csv-tool
  python demo.py --repo youruser/yourrepo
"""

import argparse
import os
import sys
import time

import requests

CLOUD_BASE = "https://app.all-hands.dev"
API_V1 = f"{CLOUD_BASE}/api/v1/app-conversations"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Cloud-native multi-harness demo using ACP"
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
        help="Custom task description (use with --task custom)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="rajshah4/openhands-multi-agent-demo",
        help="GitHub repo for the conversation",
    )
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Skip Claude Code — use OpenHands agents only (no ACP)",
    )
    return parser.parse_args()


def get_headers():
    api_key = os.getenv("OPENHANDS_CLOUD_API_KEY")
    if not api_key:
        print("ERROR: OPENHANDS_CLOUD_API_KEY is required.")
        print("  1. Go to https://app.all-hands.dev -> Settings -> API Keys")
        print("  2. Create a key and export it:")
        print("     export OPENHANDS_CLOUD_API_KEY='your-key'")
        sys.exit(1)
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def start_conversation(headers, task, repo):
    """Start a Cloud conversation and return its ID."""
    print("  🚀 Starting Cloud conversation...")
    resp = requests.post(API_V1, headers=headers, json={
        "initial_message": {
            "content": [{"type": "text", "text": task}],
        },
        "selected_repository": repo,
    })
    resp.raise_for_status()
    task_id = resp.json()["id"]

    # Poll until sandbox is ready
    for _ in range(60):
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
            print(f"    ❌ Failed: {tasks[0].get('error', 'Unknown')}")
            sys.exit(1)

        status = tasks[0].get("status", "unknown") if tasks else "waiting"
        print(f"    ⏳ {status}...")
        time.sleep(5)

    print("    ❌ Timeout waiting for sandbox")
    sys.exit(1)


def wait_for_completion(headers, conversation_id):
    """Poll until the conversation finishes."""
    last_status = None
    for _ in range(120):
        resp = requests.get(API_V1, headers=headers, params={"ids": conversation_id})
        resp.raise_for_status()
        conversations = resp.json()

        if not conversations:
            time.sleep(15)
            continue

        conv = conversations[0]
        sandbox_status = conv.get("sandbox_status")
        exec_status = conv.get("execution_status")

        if sandbox_status in ("ERROR", "MISSING"):
            return "error"

        if exec_status in ("finished", "error", "stuck"):
            return exec_status

        if exec_status == "waiting_for_confirmation":
            print("    ⚠️  Agent needs confirmation — check the Cloud UI")
            return "waiting_for_confirmation"

        if exec_status != last_status:
            print(f"    🔄 {exec_status or 'starting'}...")
            last_status = exec_status

        time.sleep(15)

    return "timeout"


def build_task_prompt(args):
    """Build the prompt that the Cloud agent will execute."""

    if args.task == "custom":
        if not args.custom_task:
            print("ERROR: --custom-task required with --task=custom")
            sys.exit(1)
        task_flag = f'--task custom --custom-task "{args.custom_task}"'
    else:
        task_flag = f"--task {args.task}"

    if args.no_claude:
        pipeline_cmd = f"python pipeline.py --no-claude {task_flag}"
        harness_desc = "OpenHands agents only (no ACP)"
    else:
        pipeline_cmd = f"python pipeline.py {task_flag}"
        harness_desc = "Claude Code (ACP) + OpenHands"

    prompt = f"""Run the multi-agent orchestration pipeline from this repo.

This pipeline uses multiple agent harnesses: {harness_desc}.

Steps:
1. Install the OpenHands SDK and tools:
   pip install openhands-sdk openhands-tools

2. Install Node.js dependencies for Claude Code ACP server:
   npm install -g @agentclientprotocol/claude-agent-acp

3. Set up environment variables:
   - ANTHROPIC_API_KEY should already be available as a secret
   - Set LLM_API_KEY=$ANTHROPIC_API_KEY
   - Set LLM_MODEL=anthropic/claude-sonnet-4-5-20250929

4. Run the pipeline:
   {pipeline_cmd}

5. After the pipeline completes, show me:
   - What files were created
   - The review findings (if any)
   - The total cost

IMPORTANT: pipeline.py uses ACPAgent which spawns Claude Code via the
Agent Client Protocol. This is a real ACP integration, not just a CLI
wrapper. Let the script run to completion — it manages its own sub-agents
internally."""

    return prompt, harness_desc


def main():
    args = parse_args()
    headers = get_headers()

    print("=" * 60)
    print("  ☁️  Cloud Multi-Harness Demo (ACP)")
    print("=" * 60)

    prompt, harness_desc = build_task_prompt(args)

    print(f"\n  📋 Task: {args.task}")
    print(f"  📦 Repo: {args.repo}")
    print(f"  🔧 Harnesses: {harness_desc}")

    conversation_id = start_conversation(headers, prompt, args.repo)
    url = f"{CLOUD_BASE}/conversations/{conversation_id}"

    print(f"\n  ☁️  Conversation: {url}")
    print(f"\n  ⏳ Agent is running the multi-harness pipeline...")
    print(f"     (Claude Code via ACP + OpenHands review)")
    print(f"     Watch live at: {url}\n")

    status = wait_for_completion(headers, conversation_id)
    status_icon = {"finished": "✅", "error": "❌", "stuck": "🔒"}.get(status, "⚠️")

    print(f"\n{'=' * 60}")
    print(f"  {status_icon} Pipeline {status}")
    print(f"  ☁️  {url}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
