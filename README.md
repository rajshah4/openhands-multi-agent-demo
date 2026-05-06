# Multi-Agent Orchestration with OpenHands

> Three vendors, one pipeline — OpenHands orchestrates Claude Code, Gemini CLI,
> and its own agents to implement, test, and review code.

![OpenHands Multi-Agent Demo — three conversations, three vendors, one repo](assets/multi-conversation.png)

## Why Multi-Agent Orchestration?

An **agent harness** wraps a model with tools, context, and execution —
Claude Code, Gemini CLI, and OpenHands are all harnesses. Each has different
strengths: Claude Code for implementation, Gemini CLI for fast test generation,
OpenHands for code review with its own agent framework.

This demo uses OpenHands as the orchestration layer that coordinates all three.
The same implement → test → review pipeline runs across vendors, and you can
swap any harness without changing the pipeline. The point isn't that you *need*
three vendors — it's that you *can*, and OpenHands makes them composable.

## The Pipeline

Every demo in this repo runs the same three-phase pipeline:

| Phase | Default Harness | What it does |
|-------|-----------------|--------------|
| **Implement** | Claude Code (Anthropic) | Writes the code from a spec |
| **Test** | Gemini CLI (Google) | Reads the code, writes and runs pytest tests |
| **Review** | OpenHands | Reviews everything, reports findings with severity |

You can swap any harness — run `--no-claude` to use OpenHands for all phases.

## Three Patterns for Multi-Agent Orchestration

This repo demonstrates **three architectural patterns** for running multiple agents.
They produce the same output but differ in isolation, complexity, and infrastructure.

📖 **[Read the full patterns guide →](PATTERNS.md)** for detailed architecture explanations,
decision trees, and migration paths.

### Pattern Comparison

| | **Pattern 1: Easy** | **Pattern 2: Isolated Local** | **Pattern 3: Cloud** |
|---|---|---|---|
| **Script** | `pattern1_easy_shared_workspace.py` | `pattern2_isolated_local_servers.py` | `pattern3_cloud_multi_sandbox.py` |
| **Sandboxes** | 1 shared | N isolated (manual) | N isolated (automatic) |
| **Agent-Servers** | 1 instance | N instances | Cloud-managed |
| **Coordination** | Filesystem | Git (you orchestrate) | Git (Cloud orchestrates) |
| **Code complexity** | ~10 lines | ~150 lines | ~50 lines |
| **Infrastructure** | None | Manual server management | Automatic provisioning |
| **Observability** | Terminal logs | Terminal logs | Web UI per agent |
| **Cost** | Free | Free | Usage-based |
| **Best for** | Local dev, tight collaboration | Air-gapped, custom orchestration | Production, auditability |

---

### When to Use Each Pattern

**Pattern 1 (Easy)** — Agents share a workspace, simple code
- ✅ Quick local development
- ✅ Agents collaborate on same files
- ✅ Minimal infrastructure
- ❌ No isolation between agents

**Pattern 2 (Isolated Local)** — Full isolation, manual orchestration  
- ✅ Complete isolation without Cloud
- ✅ Air-gapped environments
- ❌ You manage multiple servers, ports, and git coordination
- ❌ More complex orchestration code

**Pattern 3 (Cloud)** — Full isolation, automatic orchestration
- ✅ Isolation + simple code
- ✅ Automatic sandbox provisioning
- ✅ Web UI for each agent
- ❌ Requires internet and Cloud API key

## Pattern 1: Easy — Single Agent-Server (`pattern1_easy_shared_workspace.py`)

All agents run in a **single shared workspace** using the
[OpenHands SDK](https://docs.openhands.dev/sdk/overview). Claude Code and
Gemini CLI connect as subprocesses via
[ACP (Agent Client Protocol)](https://docs.agentclientprotocol.com/).

```
pattern1_easy_shared_workspace.py (your laptop)
│
└─► Single Agent-Server (one workspace)
     ├─ Agent 1 [Claude Code]  → writes shortener.py
     ├─ Agent 2 [Gemini CLI]   → writes test_shortener.py
     └─ Agent 3 [OpenHands]    → reviews all files
        
        All share /workspace/project ✅
```

**Architecture:** One sandbox, agents coordinate via shared filesystem.

**Best for:** Quick local development, tight collaboration, minimal infrastructure.

### Setup and Run

```bash
git clone https://github.com/rajshah4/openhands-multi-agent-demo.git
cd openhands-multi-agent-demo

pip install openhands-sdk openhands-tools
export LLM_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export GEMINI_API_KEY="your-key"

python pattern1_easy_shared_workspace.py               # ACP pipeline with all three harnesses
python pattern1_easy_shared_workspace.py --no-claude   # Pure OpenHands agent delegation
python pattern1_easy_shared_workspace.py --cloud       # Run on Cloud infrastructure (still single sandbox)
```

When run with `--no-claude`, the SDK uses `DelegateTool` to spawn OpenHands
subagents — the LLM decides the flow rather than a hardcoded script.

---

## Pattern 2: Isolated Local — Multiple Agent-Servers (`pattern2_isolated_local_servers.py`)

**⚠️ NOT YET IMPLEMENTED** — Conceptual example showing multi-server orchestration.

Each agent runs in its **own agent-server instance** on different ports.
You manually manage servers, workspaces, and git coordination.

```
pattern2_isolated_local_servers.py (your laptop)
│
├─► Agent-Server 1 (localhost:8080) → /tmp/claude_workspace
│     └─ Agent: Claude Code → implements, pushes to git
│
├─► Agent-Server 2 (localhost:8081) → /tmp/gemini_workspace  
│     └─ Agent: Gemini CLI → pulls, tests, pushes
│
└─► Agent-Server 3 (localhost:8082) → /tmp/reviewer_workspace
      └─ Agent: OpenHands → pulls, reviews
```

**Architecture:** Multiple agent-servers, each with isolated workspace.
You orchestrate git push/pull between workspaces.

**Best for:** Air-gapped environments, custom orchestration, learning internals.

**Trade-off:** Full isolation but requires ~150 lines of orchestration code to
manage server lifecycle, ports, workspaces, and git coordination.

---

## Pattern 3: Cloud — Automatic Multi-Sandbox (`pattern3_cloud_multi_sandbox.py`)

Each agent runs in its **own OpenHands Cloud sandbox**. Cloud automatically
provisions sandboxes, handles git coordination, and provides web UI for each agent.

```
pattern3_cloud_multi_sandbox.py (your laptop)
│
├─► ☁️ Conversation 1   [Claude Code / Anthropic]
│     └─ Cloud provisions sandbox, implements, pushes to repo
│
├─► ☁️ Conversation 2   [Gemini CLI / Google]
│     └─ Cloud provisions sandbox, pulls, tests, pushes
│
└─► ☁️ Conversation 3   [OpenHands]
      └─ Cloud provisions sandbox, pulls, reviews
```

**Architecture:** Cloud-managed sandboxes, automatic orchestration.
You write high-level workflow, Cloud handles infrastructure.

**Best for:** Production workflows, observability, auditability, enterprise.

### Setup and Run

```bash
# Prerequisites: ANTHROPIC_API_KEY and GEMINI_API_KEY as Cloud secrets
# Get a Cloud API key from https://app.all-hands.dev → Settings → API Keys

pip install requests
export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"

python pattern3_cloud_multi_sandbox.py                          # default: url-shortener
python pattern3_cloud_multi_sandbox.py --task csv-tool          # CSV-to-JSON converter
python pattern3_cloud_multi_sandbox.py --task custom --custom-task "Build a rate limiter"
python pattern3_cloud_multi_sandbox.py --repo youruser/yourrepo # your own repo
python pattern3_cloud_multi_sandbox.py --no-claude              # OpenHands for all steps
```

You'll see three conversation URLs — click each one to watch that agent work live
in the [Cloud UI](https://app.all-hands.dev).

**Value:** Same isolation as Pattern 2 (multi-server) but with ~50 lines of code
instead of ~150. Cloud handles sandbox provisioning, cleanup, and observability.

---

## Demo Results

Output from a Pattern 3 (Cloud) run (April 2026):

| Phase | Harness | Cost | Output |
|-------|---------|------|--------|
| Implement | Claude Code | $0.048 | `shortener.py` — URL shortener with `shorten()`, `resolve()`, `stats()` |
| Test | Gemini CLI | $0.000 | `test_shortener.py` + additional test files — 17 pytest tests |
| Review | OpenHands | $0.338 | 12 findings including command injection vuln and hash collision bug |
| **Total** | **3 vendors** | **$0.39** | |

---

## Files

| File | What it does |
|------|--------------|
| `pattern3_cloud_multi_sandbox.py` | **Pattern 3** — Cloud conversations via API (automatic multi-sandbox) |
| `pattern1_easy_shared_workspace.py` | **Pattern 1** — SDK with ACP (single shared workspace) |
| `pattern2_isolated_local_servers.py` | **Pattern 2** — Multi agent-server orchestration (not yet implemented) |
| `shortener.py` | Sample output — URL shortener generated by the pipeline |
| `.agents/agents/code-reviewer.md` | File-based agent definition for the reviewer |

---

## Architecture Insights

### Why Three Patterns?

Each pattern represents a different **isolation vs. complexity** trade-off:

**Pattern 1** is the "Goldilocks" for local development:
- ✅ Simple (~10 lines)
- ✅ Fast (no network calls)
- ✅ All SDK features (DelegateTool, ACP, file-based agents)
- ❌ No isolation (agents share filesystem)

**Pattern 2** provides local isolation but at high cost:
- ✅ Full isolation (separate agent-servers)
- ✅ Air-gapped capability
- ❌ Complex (~150 lines to orchestrate)
- ❌ Manual server/port/git management

**Pattern 3** is the "Goldilocks" for production:
- ✅ Full isolation (Cloud provisions sandboxes)
- ✅ Simple (~50 lines)
- ✅ Observability (Web UI per agent)
- ✅ Automatic orchestration
- ❌ Requires Cloud connectivity

### The Key Insight

**Cloud conversations (Pattern 3) = Isolation (Pattern 2) + Simplicity (Pattern 1)**

You get the full sandbox isolation of Pattern 2 without the orchestration
complexity. Cloud handles:
- ✅ Sandbox provisioning and cleanup
- ✅ Port management
- ✅ Git integration
- ✅ Observability (Web UI)
- ✅ Error recovery

This is why `pattern3_cloud_multi_sandbox.py` is only ~50 lines while a local multi-server equivalent
(`pattern2_isolated_local_servers.py`) would be ~150 lines.

---

## Enterprise Value

- **Multi-vendor flexibility** — Anthropic implements, Google tests, OpenHands reviews
- **Observable workflows** — Each agent in its own conversation, fully auditable
- **Distributed architecture** — Agents communicate through artifacts (git), not tight coupling
- **Vendor-agnostic** — Swap any agent without changing the pipeline
- **Extensible** — Add new harnesses by adding entries to `HARNESS_INSTRUCTIONS`
- **Cost-effective** — Full implement + test + review pipeline for under $0.40
- **Pattern flexibility** — Start local (Pattern 1), scale to Cloud (Pattern 3)

## Links

- [OpenHands Cloud](https://app.all-hands.dev) — run and observe agent conversations
- [OpenHands SDK docs](https://docs.openhands.dev/sdk/overview) — build agent pipelines in Python
- [Agent Client Protocol (ACP)](https://docs.agentclientprotocol.com/) — the protocol connecting harnesses
- [The Rise of Subagents](https://www.philschmid.de/the-rise-of-subagents) — why isolating tasks into focused agents improves reliability
