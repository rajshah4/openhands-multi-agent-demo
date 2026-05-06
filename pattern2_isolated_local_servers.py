#!/usr/bin/env python3
"""
Pattern 2: Isolated Local Multi-Agent Orchestration
====================================================

This is a CONCEPTUAL IMPLEMENTATION showing how to orchestrate multiple
agent-servers locally for full isolation without Cloud dependency.

⚠️  WARNING: This pattern requires ~150 lines of orchestration code to manage:
    - Multiple agent-server instances (different ports)
    - Isolated workspaces (separate directories)
    - Git coordination (manual push/pull between workspaces)
    - Server lifecycle (startup, shutdown, cleanup)

For most users, Pattern 1 (pipeline.py) or Pattern 3 (demo.py) are better choices.
This pattern is useful for:
- Air-gapped environments (no Cloud connectivity)
- Learning multi-agent infrastructure
- Building custom orchestration layers

Architecture:
    
    demo_local.py (orchestrator)
    │
    ├─► Agent-Server 1 (localhost:8080) → /tmp/claude_workspace
    │     └─ Claude Code → implement shortener.py
    │           └─ git push to feature-branch
    │
    ├─► Agent-Server 2 (localhost:8081) → /tmp/gemini_workspace  
    │     └─ Gemini CLI → git pull, write tests
    │           └─ git push to feature-branch
    │
    └─► Agent-Server 3 (localhost:8082) → /tmp/reviewer_workspace
          └─ OpenHands → git pull, review code
"""

import subprocess
import tempfile
import requests
import time
import os
import shutil
import socket
from typing import Dict, List


# ============================================================================
# Configuration
# ============================================================================

REPO_URL = "https://github.com/rajshah4/openhands-demo-repo.git"
BRANCH_NAME = f"multi-agent-{int(time.time())}"

AGENT_CONFIGS = [
    {
        "name": "Claude Code (Implementer)",
        "port": None,  # Will be auto-assigned
        "workspace": None,  # Will be created
        "task": "Create shortener.py with shorten(), resolve(), and stats() functions",
        "harness": "claude-code",
    },
    {
        "name": "Gemini CLI (Tester)",
        "port": None,
        "workspace": None,
        "task": "Write comprehensive pytest tests for shortener.py. Cover all functions.",
        "harness": "gemini-cli",
    },
    {
        "name": "OpenHands (Reviewer)",
        "port": None,
        "workspace": None,
        "task": "Review all Python files. Check for bugs, security issues, and style.",
        "harness": "openhands",
    },
]


# ============================================================================
# Helper Functions
# ============================================================================

def find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def start_agent_server(port: int, workspace: str) -> subprocess.Popen:
    """
    Start an agent-server instance on the specified port.
    
    NOTE: This is conceptual. The actual command depends on how
    agent-server is packaged and configured.
    """
    print(f"  🚀 Starting agent-server on port {port}...")
    print(f"     Workspace: {workspace}")
    
    env = os.environ.copy()
    env["AGENT_SERVER_PORT"] = str(port)
    env["WORKSPACE_DIR"] = workspace
    
    # Conceptual command - adjust based on actual agent-server CLI
    proc = subprocess.Popen(
        ["openhands", "agent-server", "--port", str(port), "--workspace", workspace],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to be ready
    for attempt in range(30):
        try:
            resp = requests.get(f"http://localhost:{port}/health", timeout=1)
            if resp.status_code == 200:
                print(f"  ✅ Agent-server ready on port {port}")
                return proc
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(1)
    
    proc.terminate()
    raise RuntimeError(f"Failed to start agent-server on port {port}")


def setup_workspace(workspace: str, repo_url: str, branch: str) -> None:
    """Clone repo and checkout branch in the workspace."""
    print(f"  📦 Setting up workspace: {workspace}")
    
    # Clone repo
    subprocess.run(
        ["git", "clone", repo_url, workspace],
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
    
    print(f"  ✅ Workspace ready: {branch}")


def send_task_to_agent(port: int, task: str, workspace: str) -> str:
    """
    Start a conversation on the agent-server and wait for completion.
    
    NOTE: This is conceptual. The actual API depends on agent-server's
    REST API specification.
    """
    print(f"  📤 Sending task to localhost:{port}")
    print(f"     Task: {task[:60]}...")
    
    # Start conversation
    resp = requests.post(
        f"http://localhost:{port}/api/conversations",
        json={
            "initial_message": task,
            "workspace": workspace,
        },
        timeout=10
    )
    resp.raise_for_status()
    
    conv_id = resp.json()["conversation_id"]
    print(f"  🆔 Conversation ID: {conv_id}")
    
    # Poll for completion
    while True:
        status_resp = requests.get(
            f"http://localhost:{port}/api/conversations/{conv_id}",
            timeout=10
        )
        status = status_resp.json()["status"]
        
        if status == "finished":
            print(f"  ✅ Task completed")
            return conv_id
        elif status in ["error", "stuck"]:
            raise RuntimeError(f"Task failed with status: {status}")
        
        print(f"  ⏳ Status: {status}...")
        time.sleep(5)


def git_push(workspace: str, branch: str) -> None:
    """Commit and push changes from workspace."""
    print(f"  📤 Pushing changes from {os.path.basename(workspace)}...")
    
    # Stage all changes
    subprocess.run(
        ["git", "add", "."],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    
    # Commit
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=workspace,
        capture_output=True
    )
    
    if result.returncode != 0:  # There are changes
        subprocess.run(
            ["git", "commit", "-m", f"Agent changes from {os.path.basename(workspace)}"],
            cwd=workspace,
            check=True,
            capture_output=True
        )
        
        # Push
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=workspace,
            check=True,
            capture_output=True
        )
        print(f"  ✅ Changes pushed to {branch}")
    else:
        print(f"  ℹ️  No changes to push")


def git_pull(workspace: str, branch: str) -> None:
    """Pull latest changes into workspace."""
    print(f"  📥 Pulling changes into {os.path.basename(workspace)}...")
    
    subprocess.run(
        ["git", "pull", "origin", branch],
        cwd=workspace,
        check=True,
        capture_output=True
    )
    
    print(f"  ✅ Changes pulled from {branch}")


def cleanup(configs: List[Dict], processes: List[subprocess.Popen]) -> None:
    """Stop all agent-servers and clean up workspaces."""
    print("\n" + "=" * 60)
    print("  🧹 Cleanup")
    print("=" * 60)
    
    # Terminate all processes
    for proc in processes:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    
    print("  ✅ All agent-servers stopped")
    
    # Optional: Remove temporary workspaces
    # Uncomment to enable auto-cleanup
    # for config in configs:
    #     if config["workspace"]:
    #         shutil.rmtree(config["workspace"], ignore_errors=True)
    #         print(f"  🗑️  Removed {config['workspace']}")


# ============================================================================
# Main Orchestration
# ============================================================================

def run_multi_agent_pipeline():
    """
    Run the three-phase pipeline across three isolated agent-servers.
    
    This demonstrates the manual orchestration required for Pattern 2.
    """
    print("=" * 60)
    print("  Pattern 2: Isolated Local Multi-Agent Orchestration")
    print("  Multiple Agent-Servers · Full Isolation · Manual Coordination")
    print("=" * 60)
    
    processes = []
    
    try:
        # ================================================================
        # Phase 0: Setup Infrastructure
        # ================================================================
        print("\n" + "─" * 60)
        print("  PHASE 0: Infrastructure Setup")
        print("─" * 60)
        
        for config in AGENT_CONFIGS:
            # Allocate port
            config["port"] = find_free_port()
            
            # Create workspace
            config["workspace"] = tempfile.mkdtemp(
                prefix=f"agent_{config['name'].split()[0].lower()}_"
            )
            
            # Setup git repo in workspace
            setup_workspace(config["workspace"], REPO_URL, BRANCH_NAME)
            
            # Start agent-server
            proc = start_agent_server(config["port"], config["workspace"])
            processes.append(proc)
            
            print()
        
        # ================================================================
        # Phase 1: Implementation
        # ================================================================
        print("\n" + "─" * 60)
        print("  PHASE 1: Claude Code → Implementation")
        print("─" * 60)
        
        claude_config = AGENT_CONFIGS[0]
        send_task_to_agent(
            claude_config["port"],
            claude_config["task"],
            claude_config["workspace"]
        )
        
        # Push implementation to git
        git_push(claude_config["workspace"], BRANCH_NAME)
        
        # ================================================================
        # Phase 2: Testing
        # ================================================================
        print("\n" + "─" * 60)
        print("  PHASE 2: Gemini CLI → Write Tests")
        print("─" * 60)
        
        gemini_config = AGENT_CONFIGS[1]
        
        # Pull Claude's implementation
        git_pull(gemini_config["workspace"], BRANCH_NAME)
        
        # Run test generation
        send_task_to_agent(
            gemini_config["port"],
            gemini_config["task"],
            gemini_config["workspace"]
        )
        
        # Push tests to git
        git_push(gemini_config["workspace"], BRANCH_NAME)
        
        # ================================================================
        # Phase 3: Review
        # ================================================================
        print("\n" + "─" * 60)
        print("  PHASE 3: OpenHands → Code Review")
        print("─" * 60)
        
        reviewer_config = AGENT_CONFIGS[2]
        
        # Pull all changes
        git_pull(reviewer_config["workspace"], BRANCH_NAME)
        
        # Run review
        send_task_to_agent(
            reviewer_config["port"],
            reviewer_config["task"],
            reviewer_config["workspace"]
        )
        
        # ================================================================
        # Summary
        # ================================================================
        print("\n" + "=" * 60)
        print("  ✅ Pipeline Complete")
        print("=" * 60)
        
        print(f"\n  Branch: {BRANCH_NAME}")
        print(f"  Repo: {REPO_URL}")
        print("\n  Agent-Server Workspaces:")
        for config in AGENT_CONFIGS:
            print(f"    • {config['name']:30s} → {config['workspace']}")
        
        print("\n  💡 Workspaces preserved for inspection.")
        print("     Delete manually when done.")
        
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        raise
    
    finally:
        cleanup(AGENT_CONFIGS, processes)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    print("\n⚠️  CONCEPTUAL IMPLEMENTATION")
    print("=" * 60)
    print("This script demonstrates Pattern 2 architecture but is NOT")
    print("fully implemented. It shows the ~150 lines of orchestration")
    print("required to run multiple agent-servers locally.")
    print()
    print("For production use:")
    print("  • Pattern 1 (pattern1_easy_shared_workspace.py) — Simple local orchestration")
    print("  • Pattern 3 (pattern3_cloud_multi_sandbox.py) — Cloud-managed multi-sandbox")
    print("=" * 60)
    print()
    
    response = input("Continue with conceptual demo? [y/N]: ")
    if response.lower() != 'y':
        print("Exiting.")
        exit(0)
    
    run_multi_agent_pipeline()
