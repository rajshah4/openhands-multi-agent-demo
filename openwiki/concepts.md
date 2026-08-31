# Core Concepts

Every multi-agent design in this repo rests on three independent decisions. Making them separately keeps the system understandable and adaptable.

## The Three Decisions

| Decision | Question | Typical choices |
|---|---|---|
| **Execution** | What do workers share: filesystem, credentials, compute, timeout, and failures? | SDK subagents; isolated conversations; grouped conversations; Agent Canvas |
| **Coordination** | Who observes progress and decides what happens next? | Application controller; live parent; scheduled reconciler; event handoff; persistent service |
| **Workflow state** | Where do tasks, attempts, workers, results, and gates survive a restart? | Automation KV; files and Git; GitHub or Jira; application database |

Do not choose these as a bundle. Keep a stable coordination contract and make execution and state replaceable.

The canonical controller loop regardless of pattern:

```
read workflow state
  → check capacity
  → claim bounded work
  → start or reattach to workers
  → observe completion
  → validate independently
  → record evidence
  → release execution capacity
```

## Conversation vs Sandbox

A **conversation** is an ownership, history, and audit boundary.

A **sandbox** is a compute, filesystem, credential, and failure boundary.

Creating a new conversation does **not** by itself guarantee a new sandbox. Sandbox placement on Enterprise follows the deployment's grouping configuration unless the controller explicitly prepares an isolated sandbox through `POST /api/v1/sandboxes`.

## Automation vs Controller

An **automation** answers *when* a controller runs — on a schedule or in response to an event. It does not replace the controller logic or the durable state needed to continue a workflow across runs.

A reconciliation controller that reads and writes durable state is always needed when work spans multiple automation runs.

## Execution Boundaries

### SDK subagents

The parent owns the main task and delegates through `TaskToolSet`. Subagents share the parent's runtime, filesystem, credentials, timeout, and failure scope. They are the right choice for bounded expert help mid-task (review this diff, plan these tests). They are not a separate service-level boundary.

The OpenHands SDK supports experimental parallel tool execution (`tool_concurrency_limit` on `Agent`). Because a subagent launch is a tool call, a parent with `tool_concurrency_limit > 1` can fan out multiple subagents in a single step. Subagents that write the same files are not safe to run concurrently.

See [`shared_workspace.py`](../shared_workspace.py).

### Isolated Enterprise conversations

First-class conversations provide separate ownership, history, and audit records. When exact sandbox isolation is required, the controller must create the sandbox explicitly and attach the conversation to it. Results travel through a final-response contract or a durable system (Git, tickets).

See [`patterns/common/openhands_conversations.py`](../patterns/common/openhands_conversations.py) and [`patterns/parent-child/`](../patterns/parent-child/).

### Grouped Enterprise conversations

Separate conversation histories, shared runtime capacity and filesystem. Grouping is a capacity mode, not a security boundary. One outer controller must manage the grouped sandbox lifecycle; a child must not release a sandbox while siblings still use it.

### Agent Canvas

The local, visual surface over the OpenHands Agent Server. Every conversation is a node you can open mid-run. Workspace and credential sharing depend on the backend configuration. Canvas is not campaign-level durable storage.

Both pattern scripts support `--runtime canvas` without code changes.

## Workflow State

Conversation history helps an agent reason but is not a durable campaign record. Durable state must carry ownership, attempts, worker IDs, artifacts, validation outcomes, and the next permitted action.

| State store | Good when | Important limit |
|---|---|---|
| Local files | One local controller owns a bounded demo | Files disappear with an ephemeral controller |
| Automation KV | One custom automation needs checkpoints across runs | Not a general multi-controller lease service |
| Files + Git | Serialized controller needs reviewable, restartable checkpoints | Git is not a transactional queue |
| GitHub / Jira | Work naturally advances through issues, labels, branches, reviews | Poor fit for frequent leases and heartbeats |
| Application database | Multiple controllers or tenants claim work concurrently | Adds schema, migration, and operational cost |

A workflow can use more than one. Jira owns the request; GitHub owns code and review artifacts; automation KV owns event-deduplication and active worker IDs.

## Decision Loop: Code or Model

Independent of pattern, the decision loop itself can be:

- **Deterministic code** — cheap, reproducible, testable. Right when the decision is mechanical (next pending task, gate on a status string). This repo's demo scripts are deterministic.
- **LLM following a skill** — right when state is natural language (issues written by humans) and the decision needs judgment.

Start deterministic. Add the model where mechanical rules stop being enough.

## ACP Workers

[ACP (Agent Client Protocol)](https://docs.agentclientprotocol.com/) lets the OpenHands SDK wrap any ACP-speaking harness as a first-class worker. Claude Code, Gemini CLI, and other compatible agents can fill a worker slot in any of the three patterns without changing the control layer.

```python
from openhands.sdk.agent import ACPAgent

worker = ACPAgent(
    acp_command=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
)
```

See [`shared_workspace.py`](../shared_workspace.py) for a working three-vendor pipeline.
