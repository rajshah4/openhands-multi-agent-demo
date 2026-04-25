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

### With Claude Code (full demo)

```bash
export LLM_API_KEY="your-api-key"           # For OpenHands agents
export ANTHROPIC_API_KEY="your-anthropic-key" # For Claude Code
python demo.py
```

### Without Claude Code (OpenHands-only delegation)

```bash
export LLM_API_KEY="your-api-key"
python demo.py --no-claude
```

### Choose a task

```bash
python demo.py --task url-shortener   # default
python demo.py --task csv-tool
python demo.py --task custom --custom-task "Build a rate limiter class"
```

## How It Works

### Path A: Claude Code + OpenHands (full demo)

1. **Phase 1** — Claude Code (via ACP protocol) implements the feature
2. **Phase 2** — OpenHands code-reviewer agent reviews the implementation
3. **Result** — Two different agent harnesses collaborated on one task

### Path B: Pure OpenHands delegation (fallback)

1. **Orchestrator** delegates to an `implementer` sub-agent (writes code)
2. **Orchestrator** delegates to a `code-reviewer` sub-agent (reviews code)
3. **Orchestrator** synthesizes findings and requests fixes if needed

## File Structure

```
.
├── demo.py                          # Main orchestration script
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
pip install openhands-sdk openhands-tools
```

Node.js 18+ required for Claude Code ACP server (`npx`).
