# openhands-multi-agent-demo — Documentation

Practical examples of coordinating multiple OpenHands agents. The examples focus on three decisions that determine whether a multi-agent system is reliable: where agents run, who observes progress and decides what happens next, and where workflow state survives across runs.

## Pages

| Page | What it covers |
|---|---|
| [Quickstart](quickstart.md) | Run the demos; environment setup |
| [Core Concepts](concepts.md) | Execution, coordination, and state — the three independent decisions |
| [Orchestration Patterns](patterns.md) | SDK subagents, automations/reconciliation, parent-child, and event-driven handoff |
| [Working Examples](examples.md) | Runnable scripts and external reference projects |

## Repository at a Glance

```
patterns/
  common/           Enterprise and Canvas conversation adapters
  parent-child/     Live supervisor with bounded child conversations
  polling/          Restartable reconciliation loop

automations/
  implement-approved-spec/  GitHub label → implement-spec → human review

shared_workspace.py     SDK subagents and ACP workers in a shared runtime
cloud_conversations.py  Coding harnesses in managed cloud conversations
multi_server_isolation.py  Isolated local clone pattern
BEST_PRACTICES.md       Full operating guidance
docs/                   Architecture and platform detail
.agents/skills/         Reusable orchestration skill and agent definitions
tests/                  Offline tests for the example controllers
```

## Where to Start

If you have OpenHands available and want to see something run immediately, start with [Quickstart](quickstart.md).

If you want to understand the design decisions before touching code, read [Core Concepts](concepts.md) first, then [Orchestration Patterns](patterns.md).
