#!/usr/bin/env python3
"""
Pattern 2: Isolated Multi-Agent Orchestration
==============================================

Run multiple agents in ISOLATED workspaces with MANUAL orchestration.

Architecture:
    multi_server_isolation.py (your laptop)
    │
    ├─► Agent 1 [Claude Code]  → /tmp/workspace_claude/
    │     └─ Implements shortener.py → git push
    │
    ├─► Agent 2 [Gemini CLI]   → /tmp/workspace_gemini/
    │     └─ git pull → writes tests → git push
    │
    └─► Agent 3 [OpenHands]    → /tmp/workspace_reviewer/
          └─ git pull → reviews code

Key Differences from Pattern 1:
- Each agent has its OWN isolated workspace
- You manually orchestrate git push/pull between agents
- More complex, but provides full isolation

Usage:
    python multi_server_isolation.py                    # Run full pipeline
    python multi_server_isolation.py --no-claude        # Skip Claude (OpenHands only)
    python multi_server_isolation.py --task csv-tool    # Different task
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

try:
    from openhands_ai import Agent, AgentConfig, Runtime, RuntimeConfig
except ImportError:
    print("❌ OpenHands SDK not installed")
    print("\nInstall with:")
    print("  pip install openhands-ai")
    print("\nOr run Pattern 3 (cloud_conversations.py) which uses Cloud API instead")
    sys.exit(1)


# ============================================================================
# Configuration
# ============================================================================

REPO_URL = "https://github.com/rajshah4/openhands-demo-repo.git"
BRANCH_NAME = f"multi-agent-{int(time.time())}"

TASKS = {
    "url-shortener": {
        "implement": "Create a file shortener.py with shorten(url), resolve(short_code), and stats() functions. Use in-memory dict storage.",
        "test": "Write comprehensive pytest tests for shortener.py. Cover all three functions with edge cases.",
        "review": "Review all Python files. Check for bugs, security vulnerabilities, and code quality issues. Be thorough.",
    },
    "csv-tool": {
        "implement": "Create csv_to_json.py with a convert(csv_path, json_path) function. Handle headers and types.",
        "test": "Write pytest tests for csv_to_json.py. Test empty files, headers, type conversion.",
        "review": "Review all Python files for bugs, errors, and quality issues.",
    },
}


# ============================================================================
# Git Helper Functions
# ============================================================================

def setup_git_workspace(workspace: Path, repo_url: str, branch: str) -> None:
    """Clone repo and create branch in isolated workspace."""
    print(f"  📦 Setting up workspace: {workspace.name}")
    
    # Clone repo
    subprocess.run(
        ["git", "clone", repo_url, str(workspace)],
        check=True,
        capture_output=True,
        text=True
    )
    
    # Configure git
    subprocess.run(
        ["git", "config", "user.name", "openhands"],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "openhands@all-hands.dev"],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    
    # Create and checkout branch
    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    
    print(f"  ✅ Workspace ready on branch: {branch}")


def git_push_changes(workspace: Path, branch: str, agent_name: str) -> bool:
    """Commit and push all changes from workspace."""
    print(f"  📤 Pushing changes from {agent_name}...")
    
    # Stage all changes
    subprocess.run(
        ["git", "add", "."],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    
    # Check if there are changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=workspace,
        capture_output=True
    )
    
    if result.returncode != 0:  # There are changes
        subprocess.run(
            ["git", "commit", "-m", f"Changes from {agent_name}"],
            cwd=workspace,
            check=True,
            capture_output=True
        )
        
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=workspace,
            check=True,
            capture_output=True
        )
        print(f"  ✅ Changes pushed to {branch}")
        return True
    else:
        print(f"  ℹ️  No changes to push")
        return False


def git_pull_changes(workspace: Path, branch: str, agent_name: str) -> None:
    """Pull latest changes into workspace."""
    print(f"  📥 Pulling latest changes for {agent_name}...")
    
    subprocess.run(
        ["git", "pull", "origin", branch],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    
    print(f"  ✅ Changes synced from {branch}")


# ============================================================================
# Agent Runner
# ============================================================================

def run_agent(
    workspace: Path,
    task: str,
    agent_name: str,
    llm_config: Optional[dict] = None
) -> None:
    """
    Run a single agent in an isolated workspace.
    
    Args:
        workspace: Path to isolated workspace
        task: Task description for the agent
        agent_name: Display name for logs
        llm_config: LLM configuration (provider, model, api_key)
    """
    print(f"\n{'='*60}")
    print(f"  {agent_name}")
    print(f"{'='*60}")
    print(f"  Workspace: {workspace}")
    print(f"  Task: {task}")
    print(f"{'─'*60}")
    
    # Create runtime with isolated workspace
    runtime_config = RuntimeConfig(
        workspace_dir=str(workspace),
        sandbox_type="local",
    )
    runtime = Runtime(config=runtime_config)
    
    # Create agent
    agent_config = AgentConfig(llm_config=llm_config) if llm_config else AgentConfig()
    agent = Agent(config=agent_config, runtime=runtime)
    
    try:
        # Send task and wait for completion
        print(f"  🤖 Starting agent...")
        response = agent.run(task)
        
        print(f"  ✅ Agent completed")
        
        # Show any files created
        py_files = list(workspace.glob("*.py"))
        if py_files:
            print(f"  📄 Files created/modified:")
            for f in py_files:
                print(f"     • {f.name}")
    
    finally:
        runtime.cleanup()


# ============================================================================
# Main Pipeline
# ============================================================================

def run_multi_agent_pipeline(task_name: str = "url-shortener", use_claude: bool = True):
    """
    Run the multi-agent pipeline with full isolation.
    
    This is the complex orchestration that Pattern 2 requires.
    Each agent gets its own workspace and you manually coordinate via git.
    """
    print("="*60)
    print("  Pattern 2: Isolated Multi-Agent Orchestration")
    print("  Multiple Workspaces · Full Isolation · Manual Git Coordination")
    print("="*60)
    
    if task_name not in TASKS:
        print(f"\n❌ Unknown task: {task_name}")
        print(f"Available tasks: {', '.join(TASKS.keys())}")
        sys.exit(1)
    
    tasks = TASKS[task_name]
    
    # Create isolated workspaces
    print(f"\n{'─'*60}")
    print("  PHASE 0: Setup Isolated Workspaces")
    print(f"{'─'*60}")
    
    workspaces = {
        "claude": Path(tempfile.mkdtemp(prefix="workspace_claude_")),
        "gemini": Path(tempfile.mkdtemp(prefix="workspace_gemini_")),
        "reviewer": Path(tempfile.mkdtemp(prefix="workspace_reviewer_")),
    }
    
    try:
        # Setup each workspace with git
        for name, workspace in workspaces.items():
            setup_git_workspace(workspace, REPO_URL, BRANCH_NAME)
            print()
        
        # ================================================================
        # Phase 1: Implementation
        # ================================================================
        print(f"\n{'─'*60}")
        if use_claude:
            print("  PHASE 1: Claude Code → Implementation")
        else:
            print("  PHASE 1: OpenHands → Implementation")
        print(f"{'─'*60}")
        
        if use_claude:
            claude_config = {
                "provider": "anthropic",
                "model": "claude-3-7-sonnet-20250219",
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
            }
            if not claude_config["api_key"]:
                print("⚠️  ANTHROPIC_API_KEY not set, falling back to OpenHands")
                use_claude = False
        
        if use_claude:
            run_agent(
                workspaces["claude"],
                tasks["implement"],
                "Claude Code (Implementer)",
                llm_config=claude_config
            )
            git_push_changes(workspaces["claude"], BRANCH_NAME, "Claude")
        else:
            run_agent(
                workspaces["claude"],
                tasks["implement"],
                "OpenHands (Implementer)",
                llm_config=None
            )
            git_push_changes(workspaces["claude"], BRANCH_NAME, "OpenHands")
        
        # ================================================================
        # Phase 2: Testing
        # ================================================================
        print(f"\n{'─'*60}")
        print("  PHASE 2: Gemini CLI → Write Tests")
        print(f"{'─'*60}")
        
        # Pull implementation into Gemini's isolated workspace
        git_pull_changes(workspaces["gemini"], BRANCH_NAME, "Gemini")
        
        gemini_config = {
            "provider": "google",
            "model": "gemini-2.0-flash-exp",
            "api_key": os.getenv("GEMINI_API_KEY"),
        }
        
        if gemini_config["api_key"]:
            run_agent(
                workspaces["gemini"],
                tasks["test"],
                "Gemini CLI (Tester)",
                llm_config=gemini_config
            )
        else:
            print("⚠️  GEMINI_API_KEY not set, falling back to OpenHands")
            run_agent(
                workspaces["gemini"],
                tasks["test"],
                "OpenHands (Tester)",
                llm_config=None
            )
        
        git_push_changes(workspaces["gemini"], BRANCH_NAME, "Gemini")
        
        # ================================================================
        # Phase 3: Review
        # ================================================================
        print(f"\n{'─'*60}")
        print("  PHASE 3: OpenHands → Code Review")
        print(f"{'─'*60}")
        
        # Pull all changes into reviewer's isolated workspace
        git_pull_changes(workspaces["reviewer"], BRANCH_NAME, "Reviewer")
        
        run_agent(
            workspaces["reviewer"],
            tasks["review"],
            "OpenHands (Reviewer)",
            llm_config=None
        )
        
        # ================================================================
        # Summary
        # ================================================================
        print(f"\n{'='*60}")
        print("  ✅ Pipeline Complete")
        print(f"{'='*60}")
        
        print(f"\n  Branch: {BRANCH_NAME}")
        print(f"  Repo: {REPO_URL}")
        
        print("\n  Isolated Workspaces:")
        print(f"    • Claude:   {workspaces['claude']}")
        print(f"    • Gemini:   {workspaces['gemini']}")
        print(f"    • Reviewer: {workspaces['reviewer']}")
        
        print("\n  💡 Each agent had its own isolated workspace.")
        print("     Git was used to manually coordinate changes.")
        print("\n  🧹 Workspaces preserved for inspection.")
        print("     Delete manually when done:")
        for workspace in workspaces.values():
            print(f"       rm -rf {workspace}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        print(f"\n{'─'*60}")
        print("  Note: Workspaces NOT auto-cleaned for inspection")
        print(f"{'─'*60}")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Pattern 2: Isolated multi-agent orchestration with manual git coordination"
    )
    parser.add_argument(
        "--task",
        default="url-shortener",
        choices=list(TASKS.keys()),
        help="Which task to run"
    )
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Use OpenHands for all phases (no Claude)"
    )
    
    args = parser.parse_args()
    
    print("\n⚠️  PATTERN 2: ISOLATED MULTI-AGENT")
    print("="*60)
    print("This pattern requires ~300 lines of orchestration code.")
    print("Each agent runs in an isolated workspace.")
    print("You manually coordinate with git push/pull.")
    print()
    print("Complexity: HIGH (~300 lines of orchestration)")
    print()
    print("Consider simpler alternatives:")
    print("  • Pattern 1 (shared_workspace.py) — Shared workspace, simple")
    print("  • Pattern 3 (cloud_conversations.py) — Cloud-managed, automatic")
    print("="*60)
    print()
    
    response = input("Continue with Pattern 2? [y/N]: ")
    if response.lower() != 'y':
        print("Exiting.")
        sys.exit(0)
    
    run_multi_agent_pipeline(
        task_name=args.task,
        use_claude=not args.no_claude
    )


if __name__ == "__main__":
    main()
