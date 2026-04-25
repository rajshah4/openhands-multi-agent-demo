# Multi-Agent Orchestration Demo

> **Claude Code (ACP) + OpenHands** — multiple agent harnesses orchestrated
> from one platform, running on OpenHands Cloud.

## What This Does

OpenHands orchestrates **different AI coding agents** working together on one task:

| Step | Harness | Protocol | What happens |
|------|---------|----------|--------------|
| **Implement** | **Claude Code** | ACP (Agent Client Protocol) | Claude Code writes the code via real ACP |
| **Review** | **OpenHands** | SDK delegation | File-based reviewer agent finds issues |
| **Fix** | **OpenHands** | SDK delegation | Implementer fixes MAJOR/CRITICAL findings |

This proves OpenHands can be the **orchestration layer** for any agent harness —
not just its own agents.

## Quick Start

### Prerequisites

1. **OpenHands Cloud API Key** — [app.all-hands.dev](https://app.all-hands.dev) → Settings → API Keys
2. **Anthropic API Key** — [console.anthropic.com](https://console.anthropic.com)
   - Add as a secret in OpenHands Cloud: Settings → Secrets → `ANTHROPIC_API_KEY`

### Run on OpenHands Cloud (recommended)

```bash
git clone https://github.com/rajshah4/openhands-multi-agent-demo.git
cd openhands-multi-agent-demo

pip install requests

export OPENHANDS_CLOUD_API_KEY="your-cloud-api-key"

# Claude Code (ACP) implements, OpenHands reviews — all in the Cloud
python demo_cloud.py

# Watch it live at the URL printed in the output
```

This starts a Cloud conversation that runs `demo.py` inside the sandbox.
Claude Code runs via **real ACP** inside the sandbox, and the entire
pipeline is visible in the Cloud UI.

### Run locally

```bash
pip install openhands-sdk openhands-tools

export LLM_API_KEY="your-anthropic-key"
export ANTHROPIC_API_KEY="your-anthropic-key"

# Full demo: Claude Code (ACP) writes, OpenHands reviews
python demo.py

# OpenHands agents only (no ACP, no Claude Code)
python demo.py --no-claude
```

### Options

```bash
# Choose a task
python demo_cloud.py --task url-shortener     # default
python demo_cloud.py --task csv-tool
python demo_cloud.py --task custom --custom-task "Build a rate limiter"

# Point at your own repo
python demo_cloud.py --repo youruser/yourrepo

# Skip Claude Code (OpenHands only)
python demo_cloud.py --no-claude
```

## Architecture

### How ACP works in this demo

```
OpenHands Cloud Sandbox
├── demo.py (orchestrator)
│   ├── ACPAgent
│   │   └── spawns claude-agent-acp subprocess
│   │       └── Claude Code ← real ACP (JSON-RPC 2.0 over stdio)
│   │           └── writes shortener.py
│   │
│   ├── code-reviewer (file-based agent, .md file)
│   │   └── reviews shortener.py
│   │
│   └── implementer (SDK agent)
│       └── fixes issues from review
│
└── All visible in Cloud UI at app.all-hands.dev
```

`ACPAgent` spawns Claude Code as an ACP server subprocess. Communication
happens via JSON-RPC 2.0 over stdio — the same protocol IDEs use to talk
to AI agents. This is **real ACP**, not a CLI wrapper.

### Agent harnesses used

| Harness | Type | Definition |
|---------|------|------------|
| **Claude Code** | `ACPAgent` | ACP protocol via `@agentclientprotocol/claude-agent-acp` |
| **Code Reviewer** | File-based agent | `.agents/agents/code-reviewer.md` — Markdown, no Python |
| **Implementer** | Programmatic agent | Python factory via `register_agent()` |
| **Built-in agents** | SDK built-ins | `bash-runner`, `code-explorer`, `general-purpose` |

## File Structure

```
.
├── demo_cloud.py                    # Starts Cloud conversation running the pipeline
├── demo.py                          # ACP-based orchestration (runs locally or in sandbox)
├── .agents/
│   └── agents/
│       └── code-reviewer.md         # File-based reviewer (no Python needed)
└── README.md
```

## Enterprise Value

- **Multi-harness** — Claude Code writes, OpenHands reviews. Best of both worlds.
- **Real ACP** — Agent Client Protocol, not CLI shelling. Proper agent-to-agent communication.
- **Observable** — Full pipeline visible in OpenHands Cloud UI
- **Vendor-flexible** — Swap Claude Code for Gemini CLI or any ACP-compatible agent
- **Extensible** — Add new agents as Markdown files, no deployment needed
- **Governed** — All actions flow through OpenHands security/confirmation system
