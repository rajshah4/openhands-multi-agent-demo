#!/usr/bin/env python3
"""
Multi-Agent Orchestration Demo
===============================

Demonstrates OpenHands as an orchestration layer that delegates work to
multiple agent harnesses — including external ones like Claude Code (ACP).

Enterprise value proposition:
  OpenHands isn't just one agent — it's the control plane that can spawn,
  delegate to, and coordinate ANY agent harness your org uses.

Architecture:
  ┌─────────────────────────────────────────────────┐
  │              Orchestrator (OpenHands)            │
  │                                                 │
  │  ┌───────────┐  ┌────────────┐  ┌────────────┐ │
  │  │ Claude    │  │ File-Based │  │ Built-in   │ │
  │  │ Code      │  │ Reviewer   │  │ Bash       │ │
  │  │ (ACP)     │  │ (.md)      │  │ Runner     │ │
  │  └───────────┘  └────────────┘  └────────────┘ │
  └─────────────────────────────────────────────────┘

Usage:
  # With Claude Code (requires ANTHROPIC_API_KEY):
  export LLM_API_KEY="your-key"
  export ANTHROPIC_API_KEY="your-anthropic-key"
  python demo.py

  # Without Claude Code (uses OpenHands agents only):
  export LLM_API_KEY="your-key"
  python demo.py --no-claude
"""

import argparse
import os
import sys
import time

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    AgentContext,
    Conversation,
    Tool,
)
from openhands.sdk.context import Skill
from openhands.sdk.agent import ACPAgent
from openhands.sdk.subagent import register_agent, register_file_agents
from openhands.tools.delegate import DelegateTool, DelegationVisualizer
from openhands.tools.preset.default import register_builtins_agents
from openhands.tools.task import TaskToolSet


# ── CLI ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Multi-Agent Orchestration Demo")
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Skip Claude Code harness (use OpenHands agents only)",
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Run on OpenHands Cloud (requires OPENHANDS_CLOUD_API_KEY). "
             "Conversations will appear in the Cloud UI.",
    )
    parser.add_argument(
        "--task",
        default="url-shortener",
        choices=["url-shortener", "csv-tool", "custom"],
        help="Which demo task to run",
    )
    parser.add_argument(
        "--custom-task",
        type=str,
        default=None,
        help="Custom task description (use with --task custom)",
    )
    return parser.parse_args()


# ── Task definitions ─────────────────────────────────────────────────

TASKS = {
    "url-shortener": (
        "Create a Python module called `shortener.py` that implements a simple "
        "in-memory URL shortener with these functions:\n"
        "  - `shorten(url: str) -> str` — returns a short code\n"
        "  - `resolve(code: str) -> str | None` — returns the original URL\n"
        "  - `stats() -> dict` — returns mapping of code → hit count\n"
        "Include a `if __name__ == '__main__'` block that demos all three functions."
    ),
    "csv-tool": (
        "Create a Python CLI tool called `csv2json.py` that:\n"
        "  - Reads a CSV file from a path argument\n"
        "  - Converts it to a list of dicts\n"
        "  - Writes pretty-printed JSON to stdout or an output file\n"
        "  - Handles missing files and malformed CSV gracefully\n"
        "Include argparse with --output and --indent options."
    ),
}


# ── Harness setup ────────────────────────────────────────────────────

def setup_cloud_workspace():
    """Set up OpenHandsCloudWorkspace. Returns (workspace, llm) or exits."""
    from openhands.workspace import OpenHandsCloudWorkspace

    cloud_api_key = os.getenv("OPENHANDS_CLOUD_API_KEY")
    if not cloud_api_key:
        print("ERROR: OPENHANDS_CLOUD_API_KEY is required for --cloud mode.")
        print("  1. Go to https://app.all-hands.dev → Settings → API Keys")
        print("  2. Create a key and export it:")
        print("     export OPENHANDS_CLOUD_API_KEY='your-key'")
        sys.exit(1)

    cloud_url = os.getenv("OPENHANDS_CLOUD_API_URL", "https://app.all-hands.dev")
    print(f"  ☁️  Connecting to OpenHands Cloud: {cloud_url}")

    workspace = OpenHandsCloudWorkspace(
        cloud_api_url=cloud_url,
        cloud_api_key=cloud_api_key,
        keep_alive=True,  # Keep sandbox alive so you can inspect in Cloud UI
    )
    workspace.__enter__()

    # Try to inherit LLM from your Cloud account settings
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        llm = LLM(
            model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929"),
            api_key=SecretStr(api_key),
            base_url=os.getenv("LLM_BASE_URL", None),
            usage_id="orchestrator-demo",
            drop_params=True,
        )
    else:
        print("  ☁️  Inheriting LLM config from your Cloud account...")
        llm = workspace.get_llm()

    print(f"  ☁️  Cloud sandbox ready — model: {llm.model}")
    return workspace, llm


def setup_llm() -> LLM:
    """Configure the LLM for OpenHands agents (local mode)."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("ERROR: LLM_API_KEY environment variable is required.")
        print("  export LLM_API_KEY='your-api-key'")
        sys.exit(1)

    return LLM(
        model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929"),
        api_key=SecretStr(api_key),
        base_url=os.getenv("LLM_BASE_URL", None),
        usage_id="orchestrator-demo",
        drop_params=True,
    )


def setup_claude_code_agent() -> ACPAgent | None:
    """Set up Claude Code as an ACP harness. Returns None if unavailable."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        return None

    print("  ✓ Claude Code (ACP) — spawning via npx...")
    return ACPAgent(
        acp_command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
        acp_env={
            "ANTHROPIC_API_KEY": anthropic_key,
            # If you use a proxy / LiteLLM, set ANTHROPIC_BASE_URL too
        },
    )


def register_implementer_agent(llm: LLM):
    """Register a fallback implementer agent (used when Claude Code is unavailable)."""
    def factory(llm: LLM) -> Agent:
        return Agent(
            llm=llm,
            tools=[
                Tool(name="file_editor"),
                Tool(name="terminal"),
            ],
            agent_context=AgentContext(
                skills=[
                    Skill(
                        name="implementer",
                        content=(
                            "You are a senior software engineer. Write clean, "
                            "well-structured Python code. Include error handling, "
                            "type hints, and a brief module docstring. "
                            "Create the file(s) in the current working directory."
                        ),
                        trigger=None,
                    )
                ],
                system_message_suffix="Write production-quality code. Be concise.",
            ),
        )

    register_agent(
        name="implementer",
        factory_func=factory,
        description="Writes clean Python implementations from specifications.",
    )


# ── Demo runner ──────────────────────────────────────────────────────

def run_demo(args):
    print("=" * 70)
    print("  Multi-Agent Orchestration Demo")
    print("  OpenHands as the enterprise agent control plane")
    print("=" * 70)

    # 1. Configure workspace + LLM
    workspace = None
    if args.cloud:
        print("\n☁️  Cloud mode — conversations will appear in OpenHands Cloud UI")
        workspace, llm = setup_cloud_workspace()
    else:
        print("\n💻 Local mode — running in-process on this machine")
        llm = setup_llm()

    # 2. Resolve the task
    if args.task == "custom":
        if not args.custom_task:
            print("ERROR: --custom-task is required when --task=custom")
            sys.exit(1)
        task_description = args.custom_task
    else:
        task_description = TASKS[args.task]

    print(f"\n📋 Task: {args.task}")
    print(f"   {task_description[:80]}...\n")

    # 3. Set up agent harnesses
    print("🔧 Registering agent harnesses:")

    # Harness A: Claude Code (ACP) or fallback implementer
    claude_agent = None
    use_claude = not args.no_claude

    if use_claude:
        claude_agent = setup_claude_code_agent()

    if claude_agent:
        implementer_label = "Claude Code (ACP)"
    else:
        if use_claude:
            print("  ⚠ ANTHROPIC_API_KEY not set — falling back to OpenHands implementer")
        register_implementer_agent(llm)
        implementer_label = "OpenHands Implementer"
    print(f"  ✓ {implementer_label}")

    # Harness B: File-based code reviewer (.agents/agents/code-reviewer.md)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    registered = register_file_agents(project_dir)
    print(f"  ✓ File-based agents: {registered}")

    # Harness C: Built-in agents (bash-runner, code-explorer, etc.)
    register_builtins_agents(enable_browser=False)
    print("  ✓ Built-in agents (bash-runner, code-explorer, general-purpose)")

    # 4. Build the orchestrator
    print("\n🎯 Starting orchestration...\n")

    # Use cloud workspace if available, otherwise local project dir
    work_dir = workspace if workspace else project_dir

    try:
        if claude_agent:
            # ── Path A: Claude Code writes, OpenHands reviews ────────────
            run_with_claude_code(claude_agent, llm, task_description, work_dir)
        else:
            # ── Path B: Pure OpenHands delegation ────────────────────────
            run_with_delegation(llm, task_description, work_dir)
    finally:
        if workspace:
            print("\n☁️  Cloud sandbox kept alive — check OpenHands Cloud UI for conversations")
            workspace.__exit__(None, None, None)


def run_with_claude_code(claude_agent: ACPAgent, llm: LLM, task: str, workspace: str):
    """
    Path A: Claude Code implements, then OpenHands reviews.
    Shows ACPAgent + TaskToolSet working together.
    """
    print("─" * 70)
    print("  PHASE 1: Claude Code (ACP) → Implementation")
    print("─" * 70)

    try:
        # Claude Code implements the task
        cc_conversation = Conversation(agent=claude_agent, workspace=workspace)
        cc_conversation.send_message(
            f"Please implement the following:\n\n{task}\n\n"
            "Create the file(s) in the current working directory."
        )
        cc_conversation.run()

        cc_cost = claude_agent.llm.metrics.accumulated_cost
        print(f"\n  💰 Claude Code cost: ${cc_cost:.4f}")

    finally:
        claude_agent.close()

    print()
    print("─" * 70)
    print("  PHASE 2: OpenHands Code Reviewer → Review")
    print("─" * 70)

    # Now use OpenHands orchestrator with TaskToolSet to review
    orchestrator = Agent(
        llm=llm,
        tools=[Tool(name=TaskToolSet.name)],
    )
    review_conversation = Conversation(
        agent=orchestrator,
        workspace=workspace,
        visualizer=DelegationVisualizer(name="Orchestrator"),
    )
    review_conversation.send_message(
        "Use the task tool to delegate to the 'code-reviewer' sub-agent. "
        "Ask it to review all .py files in the current directory that were "
        "just created. It should provide a structured code review with "
        "severity rating and actionable findings."
    )
    review_conversation.run()

    review_cost = review_conversation.conversation_stats.get_combined_metrics().accumulated_cost
    print(f"\n  💰 Review cost: ${review_cost:.4f}")
    print(f"  💰 Total cost:  ${cc_cost + review_cost:.4f}")

    print("\n" + "=" * 70)
    print("  ✅ Demo complete — Claude Code wrote it, OpenHands reviewed it")
    print("=" * 70)


def run_with_delegation(llm: LLM, task: str, workspace: str):
    """
    Path B: Pure OpenHands multi-agent delegation.
    Shows DelegateTool spawning implementer + reviewer in parallel.
    """
    orchestrator = Agent(
        llm=llm,
        tools=[Tool(name=DelegateTool.name)],
    )
    conversation = Conversation(
        agent=orchestrator,
        workspace=workspace,
        visualizer=DelegationVisualizer(name="Orchestrator"),
    )

    conversation.send_message(
        f"I need you to coordinate two sub-agents to complete this task:\n\n"
        f"**Task:** {task}\n\n"
        f"**Step 1 — Implement:** Spawn an 'implementer' sub-agent and delegate "
        f"the implementation task above. It should create the file(s) in the "
        f"current working directory.\n\n"
        f"**Step 2 — Review:** After implementation is done, spawn a 'code-reviewer' "
        f"sub-agent and ask it to review all .py files just created. It should "
        f"provide a structured review with severity and findings.\n\n"
        f"**Step 3 — Report:** Summarize what was built and the review findings. "
        f"If the review found MAJOR or CRITICAL issues, ask the implementer to "
        f"fix them.\n\n"
        f"Use the delegate tool to coordinate these agents."
    )
    conversation.run()

    cost = conversation.conversation_stats.get_combined_metrics().accumulated_cost
    print(f"\n  💰 Total cost: ${cost:.4f}")

    print("\n" + "=" * 70)
    print("  ✅ Demo complete — OpenHands orchestrated implement → review")
    print("=" * 70)


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    run_demo(args)
