# Multi-Agent Architecture Patterns

## Contents

- Separate the decisions
- Choose an execution boundary
- Choose a worker implementation
- Choose a control pattern
- Choose durable state
- Compose the system
- Use tested examples
- Qualify the recommendation

## Separate The Decisions

Make four independent choices:

```text
control pattern
  -> common controller contract
  -> execution adapter
  -> worker implementation
  -> durable state and evidence
```

Do not create one implementation for every possible combination. Keep a stable
controller interface and make execution and state replaceable.

## Choose An Execution Boundary

| Execution boundary | What is separate | Use when | Important limit |
| --- | --- | --- | --- |
| Enterprise isolated | Conversation and explicitly selected sandbox | Workers cross trust, tenant, credential, or failure boundaries | First-class conversation creation alone does not guarantee isolation; prepare and attach a sandbox or verify the installed placement policy |
| Enterprise grouped | Conversation history; trusted workers share a sandbox | Independent ownership matters but runtime density also matters | Grouping is not security isolation; one owner must drain and pause the cell |
| Agent Canvas | Conversation records; backend, workspace, and credentials may be shared | One trusted team wants lightweight visible workers | Controller placement is separate; Canvas does not supply campaign durability by itself |
| TaskTool subagents | Child task history inside one parent conversation and runtime | Two to four trusted specialists provide bounded help | Parent context, filesystem, credentials, timeout, and failure scope are shared |

First-class conversations can use subagents internally. Keep top-level campaign
ownership outside those bounded specialist calls.

## Choose A Worker Implementation

| Worker implementation | Use when | Important limit |
| --- | --- | --- |
| Native OpenHands agent | The worker needs OpenHands tools, skills, plugins, and model configuration | Keep model selection separate from worker responsibility |
| Coding-agent CLI | The harness is already installed in the workspace or does not expose ACP | The controller must capture output, lifecycle, and authentication explicitly |
| ACP-backed agent profile | Claude Code, Codex, Gemini CLI, or another ACP server should run as the conversation backend | The ACP server owns its tools and model lifecycle; validate its result like any other worker |

Enterprise and Agent Canvas can both launch saved ACP-backed profiles. The
platform chooses the operating boundary; ACP chooses what fills the worker
slot.

## Choose A Control Pattern

| Control pattern | Trigger and lifetime | Use when | Durable requirement |
| --- | --- | --- | --- |
| Live parent | Starts with one request and waits through the lifecycle | A bounded request should finish while one owner remains active | Checkpoint enough state to explain failure and support handoff |
| Bounded polling batch | Operator or pipeline starts a finite controller process | An experiment or job has an inspectable end state | Persist claims and conversation IDs until the batch drains |
| Scheduled automation tick | Cron starts a temporary controller that reconciles, acts, checkpoints, and exits | Work can wait between ticks and no controller should remain running | Reload campaign state on every tick |
| Persistent reconciler | Service continuously observes state and capacity | A sustained queue needs prompt admission and recovery | Persist state outside process memory and provide health monitoring |
| Event-triggered tick | Queue or webhook invokes one idempotent reconciliation | Work is irregular and the surrounding platform has reliable events | Deduplicate events and retain periodic reconciliation for missed delivery |

An automation answers *when the controller runs*. The controller answers *what
happens next*. The state store answers *what previous runs already did*.

## Choose Durable State

| State boundary | Use when | Do not use when |
| --- | --- | --- |
| Local files | One local controller owns a bounded demo | Controller runs in ephemeral sandboxes |
| OpenHands automation KV | One custom automation needs state across ephemeral runs | Multiple controllers need atomic task claims |
| Files plus Git | One serialized controller needs restartable, reviewable checkpoints across runs | Multiple controllers may claim work at once |
| GitHub or Jira records | The workflow naturally advances through branches, labels, issues, or tickets | High-volume leases or heartbeats are required |
| Application database | Controllers, tenants, or workers claim work concurrently | A simple single-controller pilot does not need the operational burden |

Do not read or write OpenHands internal PostgreSQL tables as the application
contract.

## Compose The System

Use one explicit architecture statement:

```text
Goal: manage a continuing research queue
Execution: grouped Enterprise conversations
Worker: saved ACP profile for implementation; native OpenHands for validation
Control: hourly OpenHands automation tick
State: OpenHands automation KV or a Git-backed single-controller ledger
Admission: two active workers; excess work remains queued
Validation: deterministic checker outside the workers
Cleanup: automation owns the grouped sandbox lifecycle
Scale-out: replace Git claims with application database leases
```

For large campaigns, prefer a hybrid:

```text
durable campaign controller
  -> bounded first-class work cells
       -> optional small subagent fan-out
  -> independent validation
  -> durable evidence
```

## Use Tested Examples

- Parent controller:
  <https://github.com/rajshah4/openhands-multi-agent-demo/tree/main/patterns/parent-child>
- Polling controller:
  <https://github.com/rajshah4/openhands-multi-agent-demo/tree/main/patterns/polling>
- Enterprise and Agent Canvas adapters:
  <https://github.com/rajshah4/openhands-multi-agent-demo/tree/main/patterns/common>
- Verified Enterprise placement, observation, metrics, and cleanup primitives:
  <https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-workflow-primitives>
- Git-backed Enterprise automation and controller examples:
  <https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/in-platform-controller>
- Deployment and controller evidence:
  <https://github.com/rajshah4/openhands-agent-research-lab>

Treat example code as a starting point. Re-run acceptance tests against the
deployed OpenHands version, model, image, grouping strategy, and capacity.

## Qualify The Recommendation

Run these gates in order:

1. Parse and resume the expected ledger volume offline.
2. Start one live worker and validate its exact output contract.
3. Increase through bounded concurrency levels without crossing capacity.
4. Interrupt the controller after conversation creation and reattach without
   creating duplicate work.
5. Test missing, malformed, invalid, delayed, and event-page-capped responses.
6. Verify completed work releases every experiment sandbox.
7. Run repeated controller cycles long enough to expose memory growth,
   cumulative API errors, missed triggers, stale claims, and queue starvation.
8. Inject controller, worker, state-store, and event-delivery failures.

Label evidence precisely:

- `tested`: directly measured in the stated environment;
- `implemented`: code exists and unit tests pass;
- `recommended`: architectural inference based on tested components;
- `untested`: requires qualification before customer use.

Do not convert a short successful batch into an endurance or production claim.
