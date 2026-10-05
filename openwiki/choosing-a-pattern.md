# Choosing an Approach for Multi-Agent Orchestration

Use this two-question decision tree to pick the right coordination pattern for your workflow.

## Decision Tree

```
Do you need workflow state to survive 
a controller restart?
│
├─ NO  ──→ Does the request need an 
│          accountable supervisor with 
│          separate visibility into workers?
│          │
│          ├─ NO  ──→ [Approach 1] In-Conversation Delegation
│          │          (One parent, bounded helper runs)
│          │
│          └─ YES ──→ [Approach 2] Parent-Child Lifecycle
│                      (Supervisor + supervised workers)
│
└─ YES ──→ [Approach 3] Durable Async Workflow
           (Event-driven or polling reconciliation)
```

## Approach 1: In-Conversation Delegation

**When to use:** One agent can do most of the work but needs bounded, temporary help from specialists.

**Key characteristics:**
- Single parent conversation controls everything
- Helper conversations are ephemeral (created, used, destroyed)
- All state lives in the parent's memory
- Latency measured in seconds to minutes
- No need for separate supervision or worker visibility

**Example:** An analyst agent that occasionally needs to run targeted code or fetch external data — helpers execute the task then return results.

**File:** `shared_workspace.py`

**Tradeoff:** If the parent run crashes, all helpers stop. If workers take a long time, the parent waits.

---

## Approach 2: Parent-Child Lifecycle

**When to use:** One request needs an accountable supervisor plus separately visible workers that may run in parallel or take varying amounts of time.

**Key characteristics:**
- Supervisor conversation controls the workflow
- Worker conversations are created per task and remain visible after completion
- Parents and workers share result via file or API
- Useful for audit trails, manual gates, or parallel work
- Workers can be gated (human approval before start)
- Each worker lifecycle is bounded to the request lifetime

**Example:** A compliance review where a supervisor assigns code audits to parallel workers, gates results, then approves or rejects.

**File:** `patterns/parent-child/run_supervisor.py`

**Tradeoff:** Workers are started and stopped per request. If you need workers to persist across requests, use Approach 3.

---

## Approach 3: Durable Async Workflow

**When to use:** The same workflow must run reliably and resume after a controller restart. Work items may queue up between controller runs.

**Key characteristics:**
- Workflow state persists in a database or queue
- Controller runs on a schedule (cron) or on event trigger
- Each controller run observes the state, picks work items, spawns agents, then persists results
- Controllers are stateless and replaceable
- Work is durable — if a controller crashes, the next one picks up where the previous stopped

**Example:** A ticket-to-PR system where a daily controller checks for new "create-pr" labels, spawns an agent per ticket, and updates the ticket with results.

**File:** `patterns/polling/orchestrate_once.py`

**Tradeoff:** More complex setup (state storage, idempotency). Controller latency is one poll interval.

---

## Hybrid Approaches

The three approaches compose. For example:

- **Approach 3 + Approach 2:** A durable workflow (polling controller) spawns a supervised parent-child request per work item.
- **Approach 2 + Approach 1:** A supervisor spawns child conversations that internally use bounded helpers for specialist tasks.

## Choosing Based on Your System

| Criterion | Approach 1 | Approach 2 | Approach 3 |
|-----------|-----------|-----------|-----------|
| **Workflow persists across restarts?** | No | No | **Yes** |
| **Parallel workers?** | No | **Yes** | **Yes** |
| **Worker visibility after run?** | No | **Yes** | **Yes** |
| **Latency tolerance** | Low | Medium | Medium-High |
| **Complexity** | Low | Medium | **High** |
| **Setup required** | Minimal | Moderate | **State storage** |

## Implementation Steps

1. **Pick your approach** using the decision tree above
2. **Run the dry run** to see the controller logic:
   ```bash
   cd patterns/[approach]
   python3 [controller].py --dry-run
   ```
3. **Adapt to your domain** — replace demo prompts, state schema, and validation logic
4. **Add supervision and gates** as needed for your workflow
5. **Review [Best Practices](../BEST_PRACTICES.md)** for reliability patterns

See [Architecture Patterns](./architecture-patterns.md) for a detailed breakdown of each approach.
