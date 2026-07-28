# Multi-Agent Best Practices

This guide collects the architecture and operating lessons from the runnable
examples in this repository and the larger NeuroGolf experiments. The
principles apply to software delivery, research, testing, data work, and other
multi-agent workflows.

The main lesson is that an agent platform supplies conversations and execution
environments. The application still needs explicit control, workflow state,
validation, capacity limits, recovery, and cleanup.

## Separate Three Decisions

Design these layers independently:

| Layer | Question | Common choices |
| --- | --- | --- |
| Execution | Where do agents run, and what do they share? | SDK subagents, isolated Enterprise conversations, grouped Enterprise conversations, Agent Canvas |
| Control | What decides which work happens next? | Live parent, bounded polling batch, scheduled automation tick, persistent reconciler, event-triggered tick |
| Workflow state | What records progress across workers and controller restarts? | Files, automation KV, Git, issues or tickets, application database |

Do not create one implementation for every combination. Keep a stable
controller contract and make execution and state replaceable:

```text
read workflow state
  -> check capacity
  -> claim bounded work
  -> start or reattach to workers
  -> observe completion
  -> validate independently
  -> record evidence
  -> release execution capacity
```

## Choose An Execution Boundary

### SDK subagents

Use SDK subagents when one bounded task needs a few trusted specialists.

- The parent owns the main task and delegates through `TaskToolSet`.
- Independent task calls can run concurrently through the SDK's experimental
  `tool_concurrency_limit`; dependent work should remain ordered.
- The parent and subagents share a runtime, filesystem, credentials, timeout,
  and failure scope.
- Each subagent can keep task-specific history, but it is not a separate
  top-level ownership or service-level boundary.
- Keep top-level queue ownership outside subagent calls.

Implementation:
[`shared_workspace.py`](shared_workspace.py)

### Isolated Enterprise conversations

Use isolated sandboxes across tenant, credential, trust, or failure
boundaries.

- A first-class conversation does not by itself guarantee a dedicated
  sandbox. Placement follows the Enterprise grouping configuration unless the
  controller explicitly prepares a sandbox and attaches the conversation.
- For deterministic placement, create the sandbox through
  `POST /api/v1/sandboxes`, wait for `RUNNING`, and pass its `sandbox_id` when
  creating the app conversation.
- Conversation links provide visible, separate audit records.
- Git, a final-response contract, or another durable system transfers results;
  local worker files are not automatically visible to the controller.
- This placement consumes the most sandbox capacity.

Implementation:
the explicit placement controls in
[`patterns/common/openhands_conversations.py`](patterns/common/openhands_conversations.py)
and the live-verified
[Enterprise workflow-primitives probe](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-workflow-primitives).
The [`patterns/parent-child`](patterns/parent-child/) supervisor demonstrates
first-class conversations and gates but leaves placement configuration-driven.

### Grouped Enterprise conversations

Use grouped placement when trusted workers need separate conversation
histories but can share runtime capacity.

- Conversations remain separate.
- Filesystem, credentials, CPU, memory, and the failure domain are shared.
- Grouping is a capacity mode, not a security boundary.
- One outer controller owns the grouped sandbox lifecycle.
- A child must not pause or release a sandbox while siblings still use it.
- Track a lease or reference count and release the sandbox only after the
  group drains.

Measured example:
[Enterprise sandbox grouping](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-sandbox-grouping)

### Agent Canvas

Use Agent Canvas when a trusted team wants lightweight, visible workers or
Kubernetes-native placement.

- Conversation records are separate.
- Workspace and credential sharing depend on the configured backend.
- Canvas does not supply durable workflow state by itself.
- The controller can run on an operator machine, in the cluster, or in another
  service. Record its placement explicitly.

Implementation:
[`patterns/common/canvas_conversations.py`](patterns/common/canvas_conversations.py)
and the [Agent Canvas project](https://github.com/OpenHands/agent-canvas)

## Choose A Control Pattern

| Control pattern | Lifetime | Good when |
| --- | --- | --- |
| Live parent | Remains active for one bounded lifecycle | One request should finish while one owner waits and applies gates |
| Bounded polling batch | Runs until a finite batch drains | An experiment or job has a clear end state |
| Scheduled automation tick | Reconciles, acts, checkpoints, and exits | Work can wait between controller runs |
| Persistent reconciler | Continuously observes queue and capacity | A sustained queue needs prompt admission and recovery |
| Event-triggered tick | An event invokes one idempotent reconciliation | Work is irregular and an external system emits useful events |

An automation determines when a controller runs. The controller determines
what happens next. Workflow state records what prior runs already did.

Events do not remove the need for a controller. Delivery can be duplicated,
delayed, or missed. Make event handlers idempotent and retain periodic
reconciliation.

Implementations:

- [`patterns/parent-child`](patterns/parent-child/)
- [`patterns/polling`](patterns/polling/)

## Choose Where Workflow State Lives

| State option | Good when | Limit |
| --- | --- | --- |
| Local files | One local controller owns a bounded demonstration | Files disappear with an ephemeral controller sandbox |
| OpenHands automation KV | One custom automation needs state across temporary runs | It is not a general concurrent claim service |
| Files plus Git | One serialized controller needs reviewable, restartable checkpoints | Git does not provide transactional multi-controller claims |
| GitHub or Jira | Work naturally advances through branches, labels, issues, or tickets | Poor fit for frequent leases and heartbeats |
| Application database | Controllers or tenants claim work concurrently | Adds schema, backup, migration, and operational work |

Do not use OpenHands internal PostgreSQL tables as an application coordination
interface. They are platform implementation details.

## Give Every Unit Stable Identity

Do not identify work by titles or list position. Titles can change and
controllers can restart.

Use stable identifiers for:

- workflow
- controller run
- task
- task owner
- attempt
- attempt sequence
- automation and automation run
- start task
- conversation
- sandbox
- artifact
- validation result
- reusable lesson or memory record
- candidate hash or result fingerprint

Number tasks and attempts in a form that sorts and remains unique:

```text
workflow_id: research-2026-07
task_id: task-0042
attempt_id: task-0042-attempt-03
attempt_sequence: 0507
```

The 400-task NeuroGolf simulation used 400 task owners and 12 attempts per
task. It verified 4,800 unique attempt IDs and 4,800 unique sequence numbers.
The larger matched comparison recorded 9,600 attempts without losing task
ownership.

Store remote identifiers as soon as they exist:

```json
{
  "task_id": "task-0042",
  "attempt_id": "task-0042-attempt-03",
  "controller_run_id": "run-20260727-09",
  "start_task_id": "start-...",
  "conversation_id": "conversation-...",
  "sandbox_id": "sandbox-...",
  "status": "running"
}
```

This lets a restarted controller reattach instead of creating duplicate work.

## Use An Append-Only Attempt Ledger

Keep completed and failed attempts. Do not overwrite them with the latest
summary.

Record:

- scheduler decision and task owner
- attempt and sequence identifiers
- retrieved lesson IDs
- start-task, conversation, sandbox, and automation identifiers
- lifecycle checkpoints
- artifact source and content hash
- independent validation result
- candidate hash and duplicate flag
- promoted lessons
- cost and token snapshots when available
- cleanup state

Maintain a current task view or index for fast decisions, but derive it from
immutable attempts and lifecycle events.

The file-ledger stress test retained 4,800 attempts and parsed 24,013 JSON
files correctly. It also exposed quadratic full-ledger reads. Keep an indexed
view rather than reparsing the full history before every decision.

## Keep Agent Context Separate From Workflow State

Conversation history helps an agent reason within one unit of work. It should
not be the only record of ownership, progress, or prior results.

- Give each worker a self-contained prompt.
- Store task claims and remote identifiers outside the conversation.
- Require a small final-response contract.
- Store artifacts in Git or another durable system.
- Promote reusable lessons only after independent validation.
- Pass prior candidate hashes and failed approaches when duplicate exploration
  would waste work.

Durable memory should contain validated techniques, their conditions, and
counterexamples—not every model statement.

## Make Dispatch Idempotent

A controller can fail after creating a worker but before recording completion.
Reconciliation must prefer reattachment over replacement.

1. Claim a stable task and attempt.
2. Create the worker.
3. Persist the start-task ID immediately.
4. Persist the conversation ID when startup becomes ready.
5. On restart, inspect stored identifiers before creating anything new.
6. Record retry and recovery attachments in the ledger.

The in-platform Enterprise controller recovered a stored conversation after
controller interruption without launching a duplicate worker.

## Separate Single-Controller And Multi-Controller State

Files, automation KV, and Git are reasonable for one serialized controller.

Git is especially useful when state transitions should be reviewable and
recoverable across ephemeral controller runs. A push-based claim can prevent a
second serialized controller from proceeding, but Git is not a general lease
service.

Use an application-owned transactional database or another real lease service
when several controllers can claim work concurrently. A lease should include:

- owner
- acquisition time
- expiry or heartbeat deadline
- attempt number
- explicit release and recovery rules

The files-first competing-controller test duplicated 100 of 100 task decisions
and candidates because the ledger had no atomic claim boundary.

## Limit Active Work And Queue The Rest

Backlog size and active concurrency are different.

```text
new work = min(ready work, tested active limit - active work)
```

A workflow with one hundred tasks does not require one hundred active
sandboxes. Queueing protects the deployment.

- For isolated Enterprise placement, sandbox availability usually constrains
  active work.
- For grouped placement, use a tested conversation density and monitor shared
  CPU, memory, filesystem, and credentials.
- For Agent Canvas, measure the configured worker backend and cluster.
- Reduce the active limit when output quality or response completeness
  degrades, even if the runtime remains healthy.

On the measured Replicated build, four grouped in-platform children produced
only three independently verifiable contracts. Two active children produced
two of two valid contracts and returned the installation to zero active
sandboxes. Treat measured limits as deployment-specific defaults, not product
limits.

## Treat Worker Reports As Inputs

A completed conversation or automation run does not prove the artifact is
correct.

Use a small machine-readable contract:

```text
status: done | needs-human | failed
artifact: <durable reference or none>
summary: <short result>
next_gate: validate | human-review | stop
```

Then validate independently:

- run deterministic tests or a scorer outside the worker
- use a separate reviewer when judgment is required
- reject missing or malformed contracts
- record counterexamples and validation failures
- keep merges, deployments, approvals, and other irreversible actions behind
  a human gate

An automation can report `COMPLETED` even when its terminal command or worker
failed. Use the workflow ledger and validation result as the source of truth.

## Prefer Durable Artifacts During Recovery

The original sandbox may disappear after a worker has already completed.

If a durable artifact and terminal checkpoint exist:

1. retrieve and parse the artifact
2. run independent validation
3. record the result
4. use sandbox status only for cleanup evidence

Do not invalidate completed work solely because the original sandbox is
missing. The long-running Enterprise test exposed this ordering problem when a
valid Git artifact existed but recovery checked for the sandbox first.

## Bound Observation And Retries

Give startup, execution, final-response collection, validation, and cleanup
separate timeouts.

- Poll conversation status for normal observation.
- Use bounded event reads for terminal recovery and diagnostics.
- Allow a short grace period for final-response indexing.
- Retry transient failures in bounded bursts until the overall deadline.
- Do not reread an entire long event history on every poll.
- Preserve failure classification: startup, execution, provider, contract,
  validation, or cleanup.

Long event histories can reach deployment-specific search boundaries. Use a
durable artifact channel rather than depending on an unlimited event stream.

## Use Events For Speed And REST For Recovery

The Enterprise 0.24.0 workflow-primitives probe verified both observation
paths:

- Connect to the agent-server WebSocket with first-message session
  authentication and `resend_mode=all`.
- Treat a per-field `execution_status=finished` event as provisional because a
  stop hook can resume work. Wait for
  `full_state.execution_status=finished`; `error` and `stuck` are immediately
  authoritative.
- Continue periodic app-conversation and durable-event reconciliation so a
  restarted controller can recover from a lost socket or callback.
- Read `/server_info` for sandbox-wide idle inspection, not conversation
  completion.
- Persist sanitized app-record metrics with their source, including cost,
  token, cache, reasoning, and context-window fields when present.

These controls are implemented in
[`patterns/common/openhands_conversations.py`](patterns/common/openhands_conversations.py).
The WebSocket helper keeps `websockets` optional; the REST path remains
dependency-free.

## Assign One Cleanup Owner

Every sandbox or grouped work cell needs one lifecycle owner.

The owner should:

1. confirm no sibling still uses the runtime
2. preserve required evidence and identifiers
3. pause, sleep, or release the runtime through the supported API
4. checkpoint cleanup state
5. retry cleanup safely during later reconciliation

Treat an already-deleted conversation, an automatically removed last sandbox,
and a null sandbox tombstone as successful idempotent cleanup. Use pause for a
bounded recovery window and deletion only after durable artifacts have been
preserved. Never force-delete a grouped sandbox based on idle time alone.

When a controller and worker share a grouped automation sandbox, the outer
automation owns cleanup. Inner workers must not pause that sandbox.

Use `keep_alive: false` when the automation should release its sandbox after
the run. Verify post-run capacity rather than assuming cleanup occurred.

## Keep Logs Useful And Safe

Record stable IDs and state transitions:

- task, attempt, and owner
- controller and automation run
- start task, conversation, and sandbox
- queue and active counts
- retry and recovery reason
- validation and cleanup state

Do not log secret values, environment dumps, complete prompts, token-bearing
Git remotes, or complete event payloads.

Track operational metrics:

- queue time
- worker startup and execution time
- active and queued work
- sandbox reuse
- validation rate
- retry and duplicate rate
- cleanup failures
- runtime restarts and resource growth
- cost and tokens when reliably available

## Keep Human Authority Explicit

Agents and controllers can propose, implement, test, and report. Humans should
retain approval for merges, deployments, production changes, access changes,
and other irreversible actions.

Convert ambiguous, missing, malformed, or blocking results into
`needs-human`. Do not infer approval from a successful automation status.

## Qualify In Stages

Test a controller in this order:

1. Offline state transitions and contract parsing
2. Expected ledger volume and identifier uniqueness
3. One live worker
4. Bounded concurrency below known capacity
5. Controller interruption and reattachment
6. Worker timeout, malformed output, and validation failure
7. Cleanup after success, failure, and interruption
8. Repeated controller cycles over an endurance window
9. Overlapping controllers
10. Concurrent claims after introducing a transactional store

Re-run qualification after changing the OpenHands version, SDK, runtime image,
model, grouping strategy, capacity, or controller state store.

Describe evidence accurately:

- **Tested:** directly measured in the stated environment
- **Implemented:** code exists and offline tests pass
- **Recommended:** an architectural conclusion based on tested components
- **Untested:** still requires qualification

## Before Starting A New Workflow

Write down:

```text
goal:
execution:
control:
workflow state:
task identifier format:
active-work limit:
worker contract:
independent validation:
cleanup owner:
human gates:
scale-out boundary:
untested assumptions:
```

This statement is more useful than naming an architecture without describing
its actual boundaries.

## Related Implementations And Evidence

- [Parent-child controller](patterns/parent-child/)
- [Polling controller](patterns/polling/)
- [Enterprise and Agent Canvas adapters](patterns/common/)
- [NeuroGolf research lab](https://github.com/rajshah4/openhands-agent-research-lab)
- [In-platform Enterprise controller](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/in-platform-controller)
- [Long-running Enterprise campaign](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/long-running-campaign)
- [Agent Canvas Kubernetes controller](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/agent-canvas-kubernetes/controller)
