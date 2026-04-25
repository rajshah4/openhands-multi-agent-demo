# Multi-Agent Orchestration Demo

> **OpenHands as the enterprise agent control plane** — orchestrate ANY agent harness
> from a single platform.

## The Idea

Enterprises don't want to be locked into a single AI coding agent. They want to:

- Run **Claude Code** for implementation tasks
- Use **custom reviewers** defined as simple Markdown files
- Leverage **built-in agents** for exploration and testing
- Orchestrate all of them from **one control plane**

This demo shows OpenHands doing exactly that.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Orchestrator (OpenHands)            │
│                                                 │
│  ┌───────────┐  ┌────────────┐  ┌────────────┐ │
│  │ Claude    │  │ File-Based │  │ Built-in   │ │
│  │ Code      │  │ Reviewer   │  │ Bash       │ │
│  │ (ACP)     │  │ (.md)      │  │ Runner     │ │
│  └───────────┘  └────────────┘  └────────────┘ │
└─────────────────────────────────────────────────┘
```

### Agent Harnesses Used

| Harness | Type | How It's Defined |
|---------|------|------------------|
| **Claude Code** | ACPAgent (external) | `ACPAgent(acp_command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"])` |
| **Code Reviewer** | File-based agent | `.agents/agents/code-reviewer.md` — a Markdown file, no Python needed |
| **Bash Runner** | Built-in agent | Ships with `openhands-tools`, registered via `register_builtins_agents()` |
| **Implementer** | Programmatic agent | Python factory function with `register_agent()` (fallback when Claude Code unavailable) |

## Quick Start

### Run locally (in-process on your machine)

```bash
export LLM_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-anthropic-key"  # optional, for Claude Code

python demo.py --no-claude        # OpenHands agents only
python demo.py                    # Full demo with Claude Code (ACP)
```

### Run on OpenHands Cloud ☁️ (conversations visible in Cloud UI)

```bash
export LLM_API_KEY="your-anthropic-key"
export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"  # from app.all-hands.dev → Settings → API Keys

python demo.py --cloud --no-claude   # OpenHands agents on Cloud
python demo.py --cloud               # Claude Code + OpenHands on Cloud
```

Conversations run via `--cloud` will appear in your [OpenHands Cloud dashboard](https://app.all-hands.dev).

### Choose a task

```bash
python demo.py --task url-shortener   # default
python demo.py --task csv-tool
python demo.py --task custom --custom-task "Build a rate limiter class"
```

## How It Works

### `demo.py` — SDK-based orchestration (local or cloud sandbox)

Uses the OpenHands SDK to orchestrate agents in-process:

| Path | Implementation | Review | How |
|------|---------------|--------|-----|
| **Path A** (Claude Code) | Claude Code via ACP | File-based reviewer | `ACPAgent` + `TaskToolSet` |
| **Path B** (OpenHands-only) | Implementer sub-agent | File-based reviewer | `DelegateTool` |

### `demo_cloud.py` — Cloud-native orchestration (each step = a conversation)

Each agent harness runs as **its own Cloud conversation**, fully visible in the UI:

```
Your Laptop (orchestrator)
│
├─► ☁️ Conversation 1: Implement  →  visible at app.all-hands.dev
├─► ☁️ Conversation 2: Review     →  visible at app.all-hands.dev
└─► ☁️ Conversation 3: Fix        →  visible at app.all-hands.dev
```

This is the **enterprise pattern** — every step is auditable, observable, and independently trackable.

## File Structure

```
.
├── demo.py                          # SDK-based orchestration (local/cloud sandbox)
├── demo_cloud.py                    # Cloud-native orchestration (sub-conversations)
├── .agents/
│   └── agents/
│       └── code-reviewer.md         # File-based reviewer agent (no Python!)
└── README.md
```

## Claude Code Authentication

Claude Code via ACP uses `ANTHROPIC_API_KEY` for API access. Options:

1. **Anthropic API Key** — Get one from [console.anthropic.com](https://console.anthropic.com)
2. **LiteLLM Proxy** — Set both `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL`
3. **OAuth (coming)** — Claude Code is adding OAuth/web-based auth for ACP

## Enterprise Value

This demo proves that OpenHands can be the **orchestration layer** for your entire
AI-assisted development workflow:

- **Vendor flexibility** — Swap agent harnesses without changing your workflow
- **Best-of-breed** — Use Claude Code for generation, a custom agent for review
- **Governance** — All agent actions flow through OpenHands' security/confirmation system
- **Extensibility** — Add new agents as Markdown files, no deployment needed
- **Cost tracking** — Unified metrics across all harnesses

## Requirements

```bash
pip install openhands-sdk openhands-tools openhands-workspace
```

Node.js 18+ required for Claude Code ACP server (`npx`).
`openhands-workspace` is only needed for `--cloud` mode.
