# Architecture Patterns for Multi-Agent Coordination

Deep dive into the three coordination approaches, their design tradeoffs, and implementation details.

## Pattern 1: In-Conversation Delegation

### Model

```
User Request
    │
    ↓
Parent Conversation
    ├→ Task A (local)
    ├→ [spawn helper] → Helper Conversation B
    │                     ├→ Task B.1
    │                     ├→ Task B.2
    │                     └→ [return results]
    ├→ Process results
    └→ Task C (local)
    │
    ↓
Result
```

### Use Case Example

An analyst agent processes a large dataset and occasionally needs to run focused code or query an external API. Instead of doing everything itself, it spawns a short-lived helper for each specialized task, collects results, and continues.

### Implementation

**File:** `shared_workspace.py`

**Key components:**
- One "parent" conversation lifetime
- Parent creates ephemeral conversations (TaskToolSet) for bounded tasks
- Helpers share a workspace with the parent for file I/O
- Results returned synchronously
- All state in parent's conversation memory

**Advantages:**
- Simple — one conversation lifecycle
- Fast — no state serialization
- Easy to debug — full conversation history in one place
- Natural for sequential workflows

**Disadvantages:**
- Helpers are ephemeral — if parent crashes, helpers stop
- Parent must wait for helpers — can't parallelize across different parent steps
- All result data must fit in memory
- No separate visibility into helper work

### Reliability Pattern

Parent wraps each helper task in try-except and has fallback logic. If a helper fails, parent decides whether to retry, skip, or fail the whole request.

---

## Pattern 2: Parent-Child Lifecycle

### Model

```
User Request
    │
    ↓
Supervisor Conversation
    ├→ Spawn Child 1 ─→ Worker Conversation A
    │                   ├→ [gate: manual approval?]
    │                   ├→ Execute task
    │                   └─→ [persist result]
    │
    ├→ Spawn Child 2 ─→ Worker Conversation B
    │                   ├→ [parallel work]
    │                   └─→ [persist result]
    │
    ├→ [await children]
    ├→ Integrate results
    └→ [finalize]
    │
    ↓
Result
```

### Use Case Example

A compliance review supervisor assigns code audits to parallel workers. Each worker gets a different audit scope. The supervisor gates each worker (manual approval before start), monitors progress, collects results, and produces an aggregate report.

### Implementation

**File:** `patterns/parent-child/run_supervisor.py`

**Key components:**
- Supervisor conversation manages the workflow
- Child conversations created per work item
- Children communicate results via shared files or API
- Supervisor waits for all children to complete (or timeout)
- Human gates optional between supervisor decisions and child spawning

**Advantages:**
- Parallel workers — multiple tasks can run simultaneously
- Audit trail — each worker's conversation is visible separately
- Worker isolation — a crash in one worker doesn't affect others
- Gates for approval workflows — supervisor can pause and request manual decision
- Good for visibility and debugging

**Disadvantages:**
- More complex — need inter-conversation communication
- Worker lifetime bound to request lifetime — workers can't persist
- Needs shared storage (files) or API for result passing
- Still limited to single request lifetime

### Reliability Pattern

- Supervisor handles timeouts per child (if child doesn't complete in time, supervisor moves on)
- Shared result files act as a contract between supervisor and workers
- Supervisor can retry individual workers
- Manual gates allow humans to make go/no-go decisions

---

## Pattern 3: Durable Async Workflow

### Model

```
Workflow State (DB/Queue)
    │
    ├─ [Item 1: pending]
    ├─ [Item 2: pending]
    └─ [Item 3: pending]
    │
    ↓ (on schedule: cron, webhook, event)
    │
Controller Run N (stateless, replaceable)
    ├→ Read state: "Item 1 pending"
    ├→ Spawn Agent → Worker Conversation A
    │               ├→ [execute]
    │               └→ [return result]
    ├→ Update state: "Item 1 → completed"
    ├→ Read state: "Item 2 pending"
    ├→ Spawn Agent → Worker Conversation B
    │               └→ [execute]
    └→ Update state: "Item 2 → completed"
    │
    ↓ (on next trigger)
    │
Controller Run N+1 (stateless, replaceable)
    ├→ Read state: "Item 3 pending"
    ├→ Spawn Agent → Worker Conversation C
    │               └→ [execute]
    └→ Update state: "Item 3 → completed"
    │
    ↓
All items processed (resume if new items arrive)
```

### Use Case Example

A ticket-to-PR system where:
1. A daily controller checks a Jira project for issues with a "create-pr" label
2. For each new issue, the controller spawns an agent to create a pull request
3. The controller updates the ticket with the PR link
4. Tomorrow's controller run picks up any new issues

If the controller crashes on day 1 after processing items 1–2, day 2's controller sees item 3 still pending and continues.

### Implementation

**File:** `patterns/polling/orchestrate_once.py`

**Key components:**
- Persistent work queue (database, file, or external API)
- Controller runs on schedule (cron trigger) or on event (webhook trigger)
- Each run is idempotent — reading and processing the same items twice produces the same result
- Workers are stateless agents spawned per work item
- Result and state stored back to queue

**Advantages:**
- Durable — survives controller crashes
- Scalable — can add workers incrementally
- Flexible triggers — cron, webhook, event-driven
- Idempotent — safe to retry
- Long-running workflows — work items can accumulate
- Clear audit trail of each work item's lifecycle

**Disadvantages:**
- More complex infrastructure (state storage)
- Idempotency burden — results must not change if replayed
- Latency measured in poll intervals (not sub-second)
- Harder to debug — state lives outside the conversation

### Reliability Pattern

- **Idempotency:** Each work item has a unique ID. If the same item is processed twice, the result is the same.
- **State machine:** Items progress through states (pending → processing → completed or failed).
- **Checkpoints:** Controller persists state before and after each agent spawn.
- **Retry logic:** Failed items can be retried with backoff.
- **Dead-letter queue:** Items that fail repeatedly are moved to a separate queue for manual review.

**Example idempotency check:**
```python
# Before processing item
if item.status == "completed":
    return item.result  # Already done, return cached result

# Process item
result = spawn_and_await_agent(item)

# Update state
item.status = "completed"
item.result = result
state_store.save(item)
```

---

## Comparison Matrix

| Aspect | Pattern 1 | Pattern 2 | Pattern 3 |
|--------|----------|----------|----------|
| **Parallelism** | Sequential helpers | Parallel children | Parallel workers |
| **State durability** | In-conversation memory | Request lifetime | Persistent storage |
| **Controller restarts** | Stops all work | Stops all children | Continues from checkpoint |
| **Latency** | Sub-second (sequential) | Seconds (parallel) | Minutes (poll interval) |
| **Scalability** | Limited by one parent | Request-scoped | Unbounded (queue-driven) |
| **Visibility** | Supervisor sees everything | Supervisor + worker conversations | Supervisor + result logs |
| **Implementation complexity** | Low | Medium | High |
| **Ideal for** | Sequential specialists | Audit workflows, gated approval | Durable, long-running tasks |

---

## Composition Patterns

### Pattern 3 + Pattern 2: Durable Supervised Workflows

A durable polling controller spawns a supervisor-child workflow for each work item:

```
Polling Controller
  └→ Spawn Supervisor (per item)
       ├→ Spawn Child 1
       └→ Spawn Child 2
```

**Use case:** Ticket-to-PR with parallel code generation and review tasks per ticket.

### Pattern 2 + Pattern 1: Hierarchical Delegation

A supervisor spawns workers that internally use ephemeral helpers:

```
Supervisor
  ├→ Child 1
  │   ├→ [ephemeral helper A]
  │   └→ [ephemeral helper B]
  └→ Child 2
      └→ [ephemeral helper C]
```

**Use case:** Compliance reviews where each auditor occasionally needs specialist help.

---

## Next Steps

1. **Run the dry runs** to see controller logic
2. **Adapt to your domain** — replace prompts, state schema, validation
3. **Add error handling** — retries, timeouts, dead-letter queues
4. **Instrument for observability** — logs, metrics, traces
5. **Review [Best Practices](../BEST_PRACTICES.md)** for production patterns

For working examples, see the `patterns/` directory.
