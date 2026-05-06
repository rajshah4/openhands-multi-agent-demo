# Multi-Agent Orchestration Patterns

This document explains the three architectural patterns for multi-agent orchestration
with OpenHands, their trade-offs, and when to use each.

## Quick Visual Guide

```
┌─────────────────────────────────────────────────────────────┐
│                    Pattern 1: Easy                          │
│  ┌────────────────────────────────────────────┐             │
│  │  Single Agent-Server (one workspace)       │             │
│  │  ├─ Agent 1 ──┐                            │             │
│  │  ├─ Agent 2 ──┼─→ Shared Files             │             │
│  │  └─ Agent 3 ──┘                            │             │
│  └────────────────────────────────────────────┘             │
│  ✅ Simple (~10 lines)  ❌ No isolation                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Pattern 2: Isolated Local                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Server 1 │  │ Server 2 │  │ Server 3 │                  │
│  │ Agent 1  │  │ Agent 2  │  │ Agent 3  │                  │
│  │ /tmp/ws1 │  │ /tmp/ws2 │  │ /tmp/ws3 │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       └──────git───┬─────git──────┘                        │
│                    └─→ You orchestrate                      │
│  ✅ Full isolation  ❌ Complex (~150 lines)                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Pattern 3: Cloud                           │
│  cloud_conversations.py (~50 lines)                │
│       │                                                     │
│       ├─► ☁️  Sandbox 1 (auto) → Agent 1 + Web UI          │
│       ├─► ☁️  Sandbox 2 (auto) → Agent 2 + Web UI          │
│       └─► ☁️  Sandbox 3 (auto) → Agent 3 + Web UI          │
│              Cloud handles everything ✅                     │
│  ✅ Full isolation  ✅ Simple code  ✅ Observability         │
└─────────────────────────────────────────────────────────────┘
```

## Pattern Overview

| Pattern | Isolation | Complexity | Infrastructure | Best For |
|---------|-----------|------------|----------------|----------|
| **1. Easy** | None | Low (~10 lines) | None | Local dev |
| **2. Isolated Local** | Full | High (~150 lines) | Manual | Air-gapped |
| **3. Cloud** | Full | Medium (~50 lines) | Automatic | Production |

---

## Pattern 1: Easy (Single Agent-Server)

### Architecture

```
┌─────────────────────────────────────────┐
│   One Agent-Server Process              │
│   ┌─────────────────────────────────┐   │
│   │  Shared Workspace (/project)    │   │
│   │                                 │   │
│   │  Agent 1 (Claude)    ───┐      │   │
│   │                         ↓      │   │
│   │  Agent 2 (Gemini)    → Files   │   │
│   │                         ↑      │   │
│   │  Agent 3 (Reviewer)  ───┘      │   │
│   │                                 │   │
│   └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### How It Works

All agents run in **one process** with a **shared workspace**:

1. Agent 1 writes files to `/workspace/project`
2. Agent 2 reads those files, adds tests
3. Agent 3 reads everything, performs review

**Communication:** Direct filesystem access (instant)

### Code Example

```python
from openhands import Conversation, Agent

workspace = "/workspace/project"

# All agents share the same workspace
implementer = Conversation(agent=claude_agent, workspace=workspace)
implementer.send_message("Create shortener.py")
implementer.run()

tester = Conversation(agent=gemini_agent, workspace=workspace)
tester.send_message("Write tests for shortener.py")  # Sees Claude's file!
tester.run()

reviewer = Conversation(agent=reviewer_agent, workspace=workspace)
reviewer.send_message("Review all .py files")  # Sees everything!
reviewer.run()
```

**Lines of code:** ~10

### Pros & Cons

**✅ Advantages:**
- Extremely simple code
- Fast (no network, no git)
- All SDK features (DelegateTool, ACP, file-based agents)
- No infrastructure to manage
- Free

**❌ Disadvantages:**
- No isolation between agents
- Agents can interfere with each other's work
- If one agent corrupts state, all agents affected
- Can't distribute across machines

### When to Use

- **Local development** — Quick iteration and testing
- **Tight collaboration** — Agents need to work on same files
- **Simple workflows** — Sequential or coordinated parallel work
- **Cost-conscious** — No Cloud usage

---

## Pattern 2: Isolated Local (Multiple Agent-Servers)

### Architecture

```
┌────────────────────────┐
│ Agent-Server 1 (8080)  │
│ ┌────────────────────┐ │     Git Push
│ │ Workspace A        │ │ ────────────┐
│ │ /tmp/claude_ws     │ │             │
│ │ Agent: Claude      │ │             ↓
│ └────────────────────┘ │         ┌─────────┐
└────────────────────────┘         │   Git   │
                                   │  Repo   │
┌────────────────────────┐         └─────────┘
│ Agent-Server 2 (8081)  │             ↑
│ ┌────────────────────┐ │ Git Pull    │
│ │ Workspace B        │ │ ────────────┘
│ │ /tmp/gemini_ws     │ │             │
│ │ Agent: Gemini      │ │             │
│ └────────────────────┘ │             │
└────────────────────────┘             │
                                       │
┌────────────────────────┐             │
│ Agent-Server 3 (8082)  │             │
│ ┌────────────────────┐ │ Git Pull    │
│ │ Workspace C        │ │ ────────────┘
│ │ /tmp/reviewer_ws   │ │
│ │ Agent: Reviewer    │ │
│ └────────────────────┘ │
└────────────────────────┘
```

### How It Works

Each agent runs in **its own agent-server process** with **isolated workspace**:

1. Start agent-server 1 on port 8080 with workspace A
2. Start agent-server 2 on port 8081 with workspace B
3. Start agent-server 3 on port 8082 with workspace C
4. YOU orchestrate git push/pull between workspaces

**Communication:** Git (explicit push/pull)

### Code Example (Conceptual)

```python
# YOU manage server lifecycle
proc1 = start_agent_server(port=8080, workspace="/tmp/ws1")
proc2 = start_agent_server(port=8081, workspace="/tmp/ws2")
proc3 = start_agent_server(port=8082, workspace="/tmp/ws3")

# YOU setup git in each workspace
for ws in ["/tmp/ws1", "/tmp/ws2", "/tmp/ws3"]:
    subprocess.run(["git", "clone", repo, ws])
    subprocess.run(["git", "checkout", "-b", branch], cwd=ws)

# Phase 1: Agent 1 implements
send_task("http://localhost:8080/api/conversations", "implement shortener.py")
wait_for_completion(8080)

# YOU push their work
subprocess.run(["git", "push", "origin", branch], cwd="/tmp/ws1")

# YOU pull into workspace 2
subprocess.run(["git", "pull", "origin", branch], cwd="/tmp/ws2")

# Phase 2: Agent 2 tests
send_task("http://localhost:8081/api/conversations", "write tests")
wait_for_completion(8081)

# YOU push again
subprocess.run(["git", "push", "origin", branch], cwd="/tmp/ws2")

# ... repeat for agent 3 ...

# YOU cleanup
proc1.terminate()
proc2.terminate()
proc3.terminate()
```

**Lines of code:** ~150

### Orchestration Responsibilities

**YOU must manage:**

1. **Server lifecycle:**
   - Start N agent-server processes
   - Allocate unique ports
   - Monitor health
   - Graceful shutdown

2. **Workspace isolation:**
   - Create N temporary directories
   - Clone repo into each
   - Manage cleanup

3. **Git coordination:**
   - Push after each agent completes
   - Pull before next agent starts
   - Handle merge conflicts
   - Branch management

4. **Error handling:**
   - Detect agent failures
   - Retry logic
   - Rollback on errors

5. **Port management:**
   - Avoid conflicts
   - Firewall rules (if distributed)

### Pros & Cons

**✅ Advantages:**
- Full isolation (separate processes, filesystems)
- Air-gapped capability (no Cloud dependency)
- Can distribute across machines (with networking)
- Agents can't interfere with each other

**❌ Disadvantages:**
- Complex orchestration (~150 lines)
- Manual server management
- Manual git coordination
- No automatic cleanup
- Port management overhead
- No built-in observability

### When to Use

- **Air-gapped environments** — No Cloud connectivity allowed
- **Custom orchestration** — Building your own platform
- **Learning** — Understanding multi-agent infrastructure
- **Extreme isolation requirements** — Regulatory/security needs

---

## Pattern 3: Cloud (Automatic Multi-Sandbox)

### Architecture

```
cloud_conversations.py (your laptop)
│
│  Orchestration Logic Only
│  (~50 lines of code)
│
├─► OpenHands Cloud API
    │
    ├─► ☁️ Sandbox 1 (automatic)
    │     ├─ Git setup ✅
    │     ├─ Workspace isolation ✅
    │     ├─ Agent: Claude Code
    │     └─ Web UI for observability
    │
    ├─► ☁️ Sandbox 2 (automatic)
    │     ├─ Git setup ✅
    │     ├─ Workspace isolation ✅
    │     ├─ Agent: Gemini CLI
    │     └─ Web UI for observability
    │
    └─► ☁️ Sandbox 3 (automatic)
          ├─ Git setup ✅
          ├─ Workspace isolation ✅
          ├─ Agent: OpenHands
          └─ Web UI for observability
```

### How It Works

Cloud **automatically provisions** sandboxes for each agent:

1. YOU call Cloud API: "Start conversation for implementation"
2. Cloud provisions sandbox, sets up git, starts agent
3. Cloud monitors, provides Web UI, handles cleanup
4. Repeat for each agent

**Communication:** Git (Cloud manages it)

### Code Example

```python
import requests

API = "https://app.all-hands.dev/api/v1/app-conversations"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Start conversation 1 (Cloud provisions sandbox automatically)
conv1 = requests.post(API, headers=headers, json={
    "task": "implement shortener.py",
    "repo": "youruser/yourrepo",
    "branch": "feature-branch"
}).json()

print(f"Watch Claude work: {conv1['url']}")  # Live Web UI!
wait_for_completion(conv1['id'])

# Start conversation 2 (new sandbox, pulls conv1's work automatically)
conv2 = requests.post(API, headers=headers, json={
    "task": "write tests for shortener.py",
    "repo": "youruser/yourrepo",
    "branch": "feature-branch"
}).json()

print(f"Watch Gemini work: {conv2['url']}")
wait_for_completion(conv2['id'])

# Start conversation 3 (new sandbox, pulls all previous work)
conv3 = requests.post(API, headers=headers, json={
    "task": "review all .py files",
    "repo": "youruser/yourrepo",
    "branch": "feature-branch"
}).json()

print(f"Watch review: {conv3['url']}")
wait_for_completion(conv3['id'])

# Cloud handles cleanup automatically
```

**Lines of code:** ~50

### Cloud Handles

**Automatic infrastructure:**

1. ✅ **Sandbox provisioning** — Spin up isolated containers
2. ✅ **Git integration** — Clone repo, checkout branch, push/pull
3. ✅ **Port management** — No port conflicts
4. ✅ **Observability** — Web UI for each conversation
5. ✅ **Cleanup** — Terminate sandboxes when done
6. ✅ **Error recovery** — Retry logic, stuck detection
7. ✅ **Persistence** — Conversation history, artifacts
8. ✅ **Authentication** — Secure API keys, secrets management

### Pros & Cons

**✅ Advantages:**
- Full isolation (Cloud provisions separate sandboxes)
- Simple code (~50 lines vs ~150 for Pattern 2)
- Automatic orchestration (Cloud does the hard work)
- Web UI observability (watch agents work in real-time)
- No infrastructure management
- Scalable (Cloud handles capacity)
- Audit trail (conversation history)

**❌ Disadvantages:**
- Requires internet connectivity
- Usage-based pricing
- Less control over infrastructure
- Vendor dependency (OpenHands Cloud)

### When to Use

- **Production workflows** — Reliability and observability critical
- **Enterprise** — Auditability, compliance, multi-user
- **Observability** — Need to watch agents work
- **Scale** — Many parallel agents
- **Time > Money** — Prefer simple code over infrastructure management

---

## The "Goldilocks" Principle

```
Pattern 1 (Easy):          Too coupled      ← Local dev
Pattern 2 (Multi-Local):   Too complex      ← Air-gapped only
Pattern 3 (Cloud):         Just right! ✨    ← Production
```

### Key Insight

**Pattern 3 = Isolation of Pattern 2 + Simplicity of Pattern 1**

Cloud orchestration gives you:
- Full isolation (like Pattern 2)
- Simple code (like Pattern 1)
- Plus: Observability, scalability, reliability

This is why `cloud_conversations.py` (Pattern 3) is only ~50 lines while `multi_server_isolation.py`
(Pattern 2) requires ~150 lines.

---

## Decision Tree

```
Do you need full isolation between agents?
│
├─ No → Pattern 1 (Easy)
│        - Simple local dev
│        - Agents collaborate tightly
│        - ~10 lines of code
│
└─ Yes → Can you use Cloud?
         │
         ├─ Yes → Pattern 3 (Cloud)
         │         - Production workflows
         │         - ~50 lines of code
         │         - Automatic orchestration
         │
         └─ No → Pattern 2 (Isolated Local)
                  - Air-gapped environments
                  - ~150 lines of code
                  - Manual orchestration
```

---

## Migration Path

Most teams follow this progression:

1. **Start with Pattern 1** — Prove the concept locally
   - Fast iteration
   - Learn multi-agent patterns
   - Test harness integration

2. **Move to Pattern 3** — Scale to production
   - Add observability
   - Handle multiple users
   - Audit requirements

3. **Consider Pattern 2** — Only if Cloud isn't an option
   - Air-gapped deployment
   - Regulatory constraints
   - Custom platform requirements

**Anti-pattern:** Starting with Pattern 2 before trying Pattern 1 or 3.
Most teams don't need the complexity of managing multiple agent-servers locally.

---

## Related Concepts

### Agent-Server vs App-Server

- **agent-server** — Single agent runtime (Pattern 1, Pattern 2)
- **app-server** — Multi-agent orchestration (Pattern 3, Cloud)

Pattern 2 runs multiple **agent-servers** to achieve what **app-server** does
automatically in Pattern 3.

### Canvas + Agent-Server Architecture (2026)

The new OpenHands architecture:
- **Canvas (GUI)** — Single frontend for all backends
- **Agent-Server** — OSS runtime (Patterns 1 & 2)
- **Cloud** — SaaS runtime (Pattern 3)

All three patterns work with this architecture:
- Pattern 1: Canvas → local agent-server
- Pattern 2: Canvas → multiple local agent-servers
- Pattern 3: Canvas → Cloud backend

---

## Summary

| Pattern | Isolation | Code | Infrastructure | Use Case |
|---------|-----------|------|----------------|----------|
| **1** | None | ~10 lines | None | Local dev, prototyping |
| **2** | Full | ~150 lines | Manual | Air-gapped, custom platform |
| **3** | Full | ~50 lines | Automatic (Cloud) | Production, enterprise |

**Recommendation:** Start with Pattern 1, scale to Pattern 3, only use Pattern 2
if Cloud is not an option.
