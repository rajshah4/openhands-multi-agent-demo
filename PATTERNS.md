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
│  │ Clone 1  │  │ Clone 2  │  │ Clone 3  │                  │
│  │ Agent 1  │  │ Agent 2  │  │ Agent 3  │                  │
│  │ /tmp/ws1 │  │ /tmp/ws2 │  │ /tmp/ws3 │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       └──────git───┬─────git──────┘                        │
│                    └─→ Local orchestrator                   │
│  ✅ Full isolation  ❌ Complex local control                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Pattern 3: Enterprise                      │
│  cloud_conversations.py                                     │
│       │                                                     │
│       ├─► ☁️  Sandbox 1 (auto) → Agent 1 + Web UI          │
│       ├─► ☁️  Sandbox 2 (auto) → Agent 2 + Web UI          │
│       └─► ☁️  Sandbox 3 (auto) → Agent 3 + Web UI          │
│              Platform handles everything ✅                  │
│  ✅ Full isolation  ✅ Simple code  ✅ Observability         │
└─────────────────────────────────────────────────────────────┘
```

## Pattern Overview

| Pattern | Isolation | Complexity | Infrastructure |
|---------|-----------|------------|----------------|
| **1. Easy** | None | Low | None |
| **2. Isolated Local** | Full | High | Manual |
| **3. Enterprise** | Full | Medium | Automatic |

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

## Pattern 2: Isolated Local (Multiple Workspaces)

### Architecture

```
┌──────────────────────────────┐
│ Local orchestrator process   │
│ multi_server_isolation.py    │
└──────────────┬───────────────┘
               │ creates a temporary bare origin
               ↓
         ┌──────────────┐
         │ origin.git   │
         └──────┬───────┘
                │
    ┌───────────┼───────────┐
    ↓           ↓           ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Clone A  │ │ Clone B  │ │ Clone C  │
│ impl     │ │ test     │ │ review   │
│ /tmp/... │ │ /tmp/... │ │ /tmp/... │
└──────────┘ └──────────┘ └──────────┘
```

### How It Works

Each phase runs in **its own git clone** with an **isolated workspace**:

1. Mirror the current repo into a temporary bare origin
2. Clone that origin three times into separate temp directories
3. Run an OpenHands SDK conversation in each workspace
4. YOU orchestrate git push/pull between workspaces
5. Run local `pytest` in the tester workspace before review

**Communication:** Git (explicit push/pull)

### Code Example (Conceptual)

```python
# Create a local bare origin from the current checkout
origin = create_origin_repo(repo_source)

# Clone isolated workspaces for each phase
for ws in ["/tmp/ws1", "/tmp/ws2", "/tmp/ws3"]:
    subprocess.run(["git", "clone", origin, ws])
    subprocess.run(["git", "checkout", "-b", branch], cwd=ws)

# Phase 1: implementation
run_agent("/tmp/ws1", "implement shortener.py", llm=anthropic_llm)
subprocess.run(["git", "push", "-u", "origin", branch], cwd="/tmp/ws1")

# Phase 2: tests
subprocess.run(["git", "fetch", "origin", branch], cwd="/tmp/ws2")
subprocess.run(["git", "merge", "--ff-only", "FETCH_HEAD"], cwd="/tmp/ws2")
run_agent("/tmp/ws2", "write pytest tests", llm=gemini_llm)
ok = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd="/tmp/ws2")
if ok.returncode != 0:
    run_agent("/tmp/ws2", "repair pytest failures", llm=gemini_llm)

# Phase 3: review
subprocess.run(["git", "fetch", "origin", branch], cwd="/tmp/ws3")
subprocess.run(["git", "merge", "--ff-only", "FETCH_HEAD"], cwd="/tmp/ws3")
run_agent("/tmp/ws3", "review all .py files", llm=reviewer_llm)
```

**Code footprint:** High enough that the orchestration is the main point of the demo.

### Orchestration Responsibilities

**YOU must manage:**

1. **Workspace isolation:**
   - Create N temporary directories
   - Mirror the source repo into a temporary bare origin
   - Clone the origin into each workspace
   - Preserve or clean up workspaces

2. **Git coordination:**
   - Push after each agent completes
   - Pull before next agent starts
   - Handle merge conflicts
   - Branch management

3. **Verification and retries:**
   - Run local `pytest` after the test-writing phase
   - Feed failure output back into a repair pass
   - Decide when to abort after retries

4. **Error handling:**
   - Detect agent failures
   - Retry logic
   - Preserve artifacts for inspection

### Pros & Cons

**✅ Advantages:**
- Full isolation (separate filesystems and git clones)
- Air-gapped capability (no Cloud dependency)
- Can distribute across machines (with networking)
- Agents can't interfere with each other

**❌ Disadvantages:**
- Complex orchestration
- Manual git coordination
- No automatic cleanup
- No built-in observability

### When to Use

- **Air-gapped environments** — No Cloud connectivity allowed
- **Custom orchestration** — Building your own platform
- **Learning** — Understanding multi-agent infrastructure
- **Extreme isolation requirements** — Regulatory/security needs

---

## Pattern 3: Enterprise (Automatic Multi-Sandbox)

### Architecture

```
cloud_conversations.py (your laptop)
│
│  Orchestration Logic Only
│
├─► OpenHands Cloud/Enterprise API
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

The platform **automatically provisions** sandboxes for each agent:

1. YOU call the API: "Start conversation for implementation"
2. Platform provisions sandbox, sets up git, starts agent
3. Platform monitors, provides Web UI, handles cleanup
4. Repeat for each agent

**Communication:** Git (platform manages it)

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

**Code footprint:** Thinner than Pattern 2 because Cloud handles the sandbox lifecycle.

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
- Thinner local orchestration than Pattern 2
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
Pattern 3 (Enterprise):    Just right! ✨    ← Production
```

### Key Insight

**Pattern 3 = Isolation of Pattern 2 + Simplicity of Pattern 1**

Enterprise orchestration gives you:
- Full isolation (like Pattern 2)
- Simple code (like Pattern 1)
- Plus: Observability, scalability, reliability

This is why `cloud_conversations.py` stays relatively thin while
`multi_server_isolation.py` carries the local orchestration burden directly.

---

## Decision Tree

```
Do you need full isolation between agents?
│
├─ No → Pattern 1 (Easy)
│        - Simple local dev
│        - Agents collaborate tightly
│        - Low orchestration overhead
│
└─ Yes → Can you use Enterprise?
         │
         ├─ Yes → Pattern 3 (Enterprise)
         │         - Production workflows
         │         - Thin local wrapper
         │         - Automatic orchestration
         │
         └─ No → Pattern 2 (Isolated Local)
                  - Air-gapped environments
                  - High orchestration overhead
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
Most teams don't need the complexity of managing isolated local clones and git
handoff logic themselves.

---

## Related Concepts

### Agent-Server vs App-Server

- **agent-server** — Single agent runtime (Pattern 1, Pattern 2)
- **app-server** — Multi-agent orchestration (Pattern 3, Enterprise)

Pattern 2 recreates, locally and manually, parts of what the **app-server**
does automatically in Pattern 3.

### Canvas + Agent-Server Architecture (2026)

The new OpenHands architecture:
- **Canvas (GUI)** — Single frontend for all backends
- **Agent-Server** — OSS runtime (Patterns 1 & 2)
- **Enterprise** — Cloud or self-hosted runtime (Pattern 3)

All three patterns fit within this architecture:
- Pattern 1: Canvas → local agent-server
- Pattern 2: Canvas → local orchestrator plus isolated local workspaces
- Pattern 3: Canvas → Enterprise backend (Cloud or self-hosted)

---

## Summary

| Pattern | Isolation | Code | Infrastructure | Use Case |
|---------|-----------|------|----------------|----------|
| **1** | None | Low | None | Local dev, prototyping |
| **2** | Full | High | Manual | Air-gapped, custom platform |
| **3** | Full | Medium | Automatic (Cloud) | Production, enterprise |

**Recommendation:** Start with Pattern 1, scale to Pattern 3, only use Pattern 2
if Cloud is not an option.
