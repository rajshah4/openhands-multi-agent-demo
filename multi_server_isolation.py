#!/usr/bin/env python3
"""
Pattern 2: Isolated Multi-Agent Orchestration
==============================================

Run multiple isolated OpenHands SDK conversations with manual git orchestration.

Architecture:
    multi_server_isolation.py (your laptop)
    │
    ├─► Agent 1 [OpenHands SDK + Anthropic LLM]  → /tmp/workspace_claude/
    │     └─ Implements shortener.py → git push
    │
    ├─► Agent 2 [OpenHands SDK + Gemini LLM]     → /tmp/workspace_gemini/
    │     └─ git pull → writes tests → git push
    │
    └─► Agent 3 [OpenHands SDK reviewer]         → /tmp/workspace_reviewer/
          └─ git pull → review, with local pytest verification earlier in the flow

Key Differences from Pattern 1:
- Each agent has its OWN isolated workspace
- The orchestrator mirrors the local repo into a temporary bare origin
- You manually orchestrate git push/pull between agents
- The tester workspace is verified with local pytest, with one repair retry

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

from pydantic import SecretStr

try:
    from openhands.sdk import Agent, Conversation, LLM
    from openhands.tools.preset.default import get_default_tools
except ImportError:
    print("❌ OpenHands SDK not installed")
    print("\nInstall with:")
    print("  pip install openhands-ai")
    print("\nOr run Pattern 3 (cloud_conversations.py) which uses Cloud API instead")
    sys.exit(1)


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_REPO_SOURCE = Path(__file__).resolve().parent
BRANCH_NAME = f"multi-agent-{int(time.time())}"
DEFAULT_ANTHROPIC_MODEL = "anthropic/claude-sonnet-4-5-20250929"
DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"

TASKS = {
    "url-shortener": {
        "implement": "Create or update shortener.py so it provides shorten(url), resolve(short_code), and stats() functions. Use in-memory dict storage.",
        "test": "Write comprehensive pytest tests for shortener.py. Cover all three functions with edge cases. Leave the test file in place and do not delete it. Do not create a virtual environment or install packages; the orchestrator will run pytest separately.",
        "review": "Review all Python files. Check for bugs, security vulnerabilities, and code quality issues. Be thorough.",
    },
    "csv-tool": {
        "implement": "Create csv_to_json.py with a convert(csv_path, json_path) function. Handle headers and types.",
        "test": "Write pytest tests for csv_to_json.py. Test empty files, headers, type conversion. Leave the test file in place and do not delete it. Do not create a virtual environment or install packages; the orchestrator will run pytest separately.",
        "review": "Review all Python files for bugs, errors, and quality issues.",
    },
}


# ============================================================================
# Git Helper Functions
# ============================================================================

def create_origin_repo(repo_source: str) -> Path:
    """Create a local bare git repo that acts as the shared origin."""
    repo_path = Path(repo_source).expanduser().resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository source does not exist: {repo_path}")

    origin_root = Path(tempfile.mkdtemp(prefix="pattern2_origin_"))
    origin_repo = origin_root / "origin.git"

    print(f"  🗃️  Creating local origin from: {repo_path}")
    subprocess.run(
        ["git", "clone", "--bare", str(repo_path), str(origin_repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"  ✅ Local origin ready: {origin_repo}")
    return origin_repo


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
            ["git", "push", "-u", "origin", branch],
            cwd=workspace,
            check=True,
            capture_output=True
        )
        print(f"  ✅ Changes pushed to {branch}")
        return True
    else:
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=workspace,
            check=True,
            capture_output=True,
        )
        print(f"  ℹ️  No changes to commit; published branch {branch}")
        return False


def git_pull_changes(workspace: Path, branch: str, agent_name: str) -> None:
    """Pull latest changes into workspace."""
    print(f"  📥 Pulling latest changes for {agent_name}...")
    
    subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ["git", "merge", "--ff-only", "FETCH_HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    
    print(f"  ✅ Changes synced from {branch}")


def run_pytest(workspace: Path) -> tuple[bool, str]:
    """Run pytest in the isolated workspace using the current interpreter."""
    print("  🧪 Running pytest...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())

    combined_output = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    )

    if result.returncode != 0:
        return False, combined_output

    print("  ✅ pytest passed")
    return True, combined_output


# ============================================================================
# Agent Runner
# ============================================================================

def run_agent(
    workspace: Path,
    task: str,
    agent_name: str,
    llm: LLM,
) -> None:
    """
    Run a single agent in an isolated workspace.
    
    Args:
        workspace: Path to isolated workspace
        task: Task description for the agent
        agent_name: Display name for logs
        llm: Configured LLM for the agent
    """
    print(f"\n{'='*60}")
    print(f"  {agent_name}")
    print(f"{'='*60}")
    print(f"  Workspace: {workspace}")
    print(f"  Task: {task}")
    print(f"{'─'*60}")
    
    agent = Agent(
        llm=llm,
        tools=get_default_tools(enable_browser=False),
    )
    conversation = Conversation(agent=agent, workspace=workspace)
    
    try:
        # Send task and wait for completion
        print(f"  🤖 Starting agent...")
        conversation.send_message(task)
        conversation.run()
        
        print(f"  ✅ Agent completed")
        
        # Show any files created
        py_files = list(workspace.glob("*.py"))
        if py_files:
            print(f"  📄 Files created/modified:")
            for f in py_files:
                print(f"     • {f.name}")
    
    finally:
        conversation.close()


def build_llm(
    *,
    api_key_env: str,
    default_model: str,
    usage_id: str,
    model_env: Optional[str] = None,
) -> LLM:
    """Build an OpenHands LLM config from environment variables."""
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"{api_key_env} is not set")

    model = os.getenv(model_env, default_model) if model_env else default_model
    base_url = os.getenv("LLM_BASE_URL")

    return LLM(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        usage_id=usage_id,
        drop_params=True,
    )


def build_reviewer_llm() -> LLM:
    """Prefer generic LLM config, then fall back to Anthropic/Gemini keys."""
    llm_api_key = os.getenv("LLM_API_KEY")
    if llm_api_key:
        return LLM(
            model=os.getenv("LLM_MODEL", DEFAULT_ANTHROPIC_MODEL),
            api_key=SecretStr(llm_api_key),
            base_url=os.getenv("LLM_BASE_URL"),
            usage_id="pattern2-reviewer",
            drop_params=True,
        )

    if os.getenv("GEMINI_API_KEY"):
        return build_llm(
            api_key_env="GEMINI_API_KEY",
            default_model=DEFAULT_GEMINI_MODEL,
            model_env="GEMINI_MODEL",
            usage_id="pattern2-reviewer",
        )

    if os.getenv("ANTHROPIC_API_KEY"):
        return build_llm(
            api_key_env="ANTHROPIC_API_KEY",
            default_model=DEFAULT_ANTHROPIC_MODEL,
            model_env="ANTHROPIC_MODEL",
            usage_id="pattern2-reviewer",
        )

    raise RuntimeError(
        "No reviewer LLM credentials found. Set LLM_API_KEY, "
        "ANTHROPIC_API_KEY, or GEMINI_API_KEY."
    )


# ============================================================================
# Main Pipeline
# ============================================================================

def run_multi_agent_pipeline(
    task_name: str = "url-shortener",
    use_claude: bool = True,
    repo_source: str = str(DEFAULT_REPO_SOURCE),
):
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
    
    origin_repo = create_origin_repo(repo_source)

    workspaces = {
        "claude": Path(tempfile.mkdtemp(prefix="workspace_claude_")),
        "gemini": Path(tempfile.mkdtemp(prefix="workspace_gemini_")),
        "reviewer": Path(tempfile.mkdtemp(prefix="workspace_reviewer_")),
    }
    
    try:
        # Setup each workspace with git
        for name, workspace in workspaces.items():
            setup_git_workspace(workspace, str(origin_repo), BRANCH_NAME)
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
            if not os.getenv("ANTHROPIC_API_KEY"):
                print("⚠️  ANTHROPIC_API_KEY not set, falling back to OpenHands")
                use_claude = False
        
        if use_claude:
            run_agent(
                workspaces["claude"],
                tasks["implement"],
                "Claude Code (Implementer)",
                llm=build_llm(
                    api_key_env="ANTHROPIC_API_KEY",
                    default_model=DEFAULT_ANTHROPIC_MODEL,
                    model_env="ANTHROPIC_MODEL",
                    usage_id="pattern2-claude",
                ),
            )
            git_push_changes(workspaces["claude"], BRANCH_NAME, "Claude")
        else:
            run_agent(
                workspaces["claude"],
                tasks["implement"],
                "OpenHands (Implementer)",
                llm=build_reviewer_llm(),
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
        
        tester_name = "Gemini CLI (Tester)"
        if os.getenv("GEMINI_API_KEY"):
            tester_llm = build_llm(
                api_key_env="GEMINI_API_KEY",
                default_model=DEFAULT_GEMINI_MODEL,
                model_env="GEMINI_MODEL",
                usage_id="pattern2-gemini",
            )
            run_agent(
                workspaces["gemini"],
                tasks["test"],
                tester_name,
                llm=tester_llm,
            )
        else:
            print("⚠️  GEMINI_API_KEY not set, falling back to OpenHands")
            tester_name = "OpenHands (Tester)"
            tester_llm = build_reviewer_llm()
            run_agent(
                workspaces["gemini"],
                tasks["test"],
                tester_name,
                llm=tester_llm,
            )
        
        git_push_changes(workspaces["gemini"], BRANCH_NAME, "Gemini")

        print(f"\n{'─'*60}")
        print("  PHASE 2B: Verification → Run pytest")
        print(f"{'─'*60}")
        pytest_ok, pytest_output = run_pytest(workspaces["gemini"])
        if not pytest_ok:
            print(f"\n{'─'*60}")
            print("  PHASE 2C: Repair → Fix pytest failures")
            print(f"{'─'*60}")
            run_agent(
                workspaces["gemini"],
                (
                    "Pytest is failing. Fix the implementation and/or tests so "
                    "they pass.\n\n"
                    "Do not delete the test file. Do not create a virtual "
                    "environment or install packages. The orchestrator will rerun "
                    "pytest after you finish.\n\n"
                    f"Current pytest output:\n{pytest_output}"
                ),
                f"{tester_name} (Repair)",
                llm=tester_llm,
            )
            git_push_changes(workspaces["gemini"], BRANCH_NAME, "Gemini")

            print(f"\n{'─'*60}")
            print("  PHASE 2D: Verification Retry → Run pytest")
            print(f"{'─'*60}")
            pytest_ok, pytest_output = run_pytest(workspaces["gemini"])
            if not pytest_ok:
                raise RuntimeError("pytest verification failed after repair pass")
        
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
            llm=build_reviewer_llm(),
        )
        
        # ================================================================
        # Summary
        # ================================================================
        print(f"\n{'='*60}")
        print("  ✅ Pipeline Complete")
        print(f"{'='*60}")
        
        print(f"\n  Branch: {BRANCH_NAME}")
        print(f"  Origin: {origin_repo}")
        print(f"  Source: {Path(repo_source).expanduser().resolve()}")
        
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
    parser.add_argument(
        "--repo",
        default=str(DEFAULT_REPO_SOURCE),
        help="Local git repository to mirror into isolated workspaces",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt",
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
    
    if not args.yes:
        response = input("Continue with Pattern 2? [y/N]: ")
        if response.lower() != 'y':
            print("Exiting.")
            sys.exit(0)
    
    run_multi_agent_pipeline(
        task_name=args.task,
        use_claude=not args.no_claude,
        repo_source=args.repo,
    )


if __name__ == "__main__":
    main()
