# Multi-Agent Orchestration with OpenHands

This repository shows practical ways to coordinate multiple OpenHands agents.
The examples focus on the decisions that make a multi-agent system reliable:
who starts the agents, where they work, how results move between them, and
where progress survives when a controller stops.

The examples are intentionally small. Use them to learn the control patterns,
then replace the demo prompts, state, and validation with your own workflow.

## Start Here

There are three useful starting points:

| Approach | Start here when | Working example |
| --- | --- | --- |
| [SDK orchestration](#1-sdk-orchestration) | One application or conversation should delegate bounded work to a few trusted specialists. | [`shared_workspace.py`](shared_workspace.py) |
| [Automations and reconciliation](#2-automations-and-reconciliation) | Work arrives over time, spans controller runs, or must wait for CI, external systems, or people. | [`patterns/polling`](patterns/polling/) |
| [Parent-child conversations](#3-parent-child-conversations) | One bounded request needs an accountable supervisor plus separately visible workers and gates. | [`patterns/parent-child`](patterns/parent-child/) |

The approaches compose. A scheduled automation can launch a parent-child
lifecycle, and any first-class worker conversation can use SDK subagents for
smaller specialist tasks.

If you want to inspect a control loop without creating a conversation, start
with one of the dry runs:

```bash
# A restartable reconciliation tick
cd patterns/polling
python3 orchestrate_once.py --dry-run

# A live parent with gated child assignments
cd ../parent-child
python3 run_supervisor.py --dry-run
```

## The Core Model

Do not choose a multi-agent architecture as one indivisible bundle. Make three
separate decisions:

| Decision | Question | Typical choices |
| --- | --- | --- |
| **Execution** | What do workers share: filesystem, credentials, compute, timeout, and failures? | SDK subagents, isolated conversations, grouped conversations, Agent Canvas |
| **Coordination** | Who observes progress and decides what happens next? | Application controller, live parent, scheduled reconciler, event handoff, persistent service |
| **Workflow state** | Where do tasks, attempts, active workers, results, and gates survive? | Automation KV, files and Git, GitHub or Jira, application database |

A **conversation** is an ownership, history, and audit boundary. A **sandbox**
is a compute, filesystem, credential, and failure boundary. Creating a new
conversation does not by itself guarantee a new sandbox.

An **automation** answers when a controller runs. It does not replace the
controller logic or durable state needed to continue a workflow across runs.

That separation is the main idea behind every example in this repository.

## 1. SDK Orchestration

![One parent agent delegating to subagents inside a shared runtime](assets/start-sdk-subagents.svg)

Your Python application is the controller. It starts agents or subagents,
passes assignments, waits for results, validates them, and decides when to
stop.

**Use it when:** one bounded task needs a few researchers, reviewers, test
planners, or other specialists that can safely share a runtime and failure
scope.

**Typical composition:**

- **Execution:** one conversation and one shared runtime
- **Coordination:** the application or live parent delegates and waits
- **Workflow state:** parent history, subagent task IDs, and an optional report

[`shared_workspace.py`](shared_workspace.py) demonstrates an OpenHands coding
team in one workspace. It includes native subagent delegation through
`TaskToolSet` and ACP-backed agent paths.

The SDK also supports:

- specialized Python or
  [file-based agents](https://docs.openhands.dev/sdk/guides/agent-file-based)
- sequential and resumable delegation with
  [TaskToolSet](https://docs.openhands.dev/sdk/guides/task-tool-set)
- experimental
  [parallel tool execution](https://docs.openhands.dev/sdk/guides/parallel-tool-execution)
- local or remote workspaces and
  [conversation persistence](https://docs.openhands.dev/sdk/guides/convo-persistence)
- alternative coding agents through
  [ACP](https://docs.openhands.dev/sdk/guides/agent-acp)

### Important boundary

SDK subagents are excellent for bounded specialist help inside one work cell.
They usually share the parent's filesystem, credentials, compute, timeout, and
failure scope. Use first-class child conversations when workers need separate
audit records, independently chosen runtimes, or stronger isolation.

## 2. Automations and Reconciliation

![A schedule or event starting a temporary controller that reads workflow state and manages worker conversations](assets/start-automation-controller.svg)

A schedule, webhook, or application event starts a temporary controller. The
controller reloads durable state, compares desired and actual progress, takes
a bounded action, records what happened, and exits. A later run continues from
the checkpoint.

**Use it when:** work arrives continuously, spans hours or days, can wait
between checks, or naturally advances through GitHub, Jira, a Kanban board, or
another system of record.

**Typical composition:**

- **Execution:** automation runs plus one or more worker conversations
- **Coordination:** scheduled reconciliation, event-triggered ticks, direct
  event handoffs, or a combination
- **Workflow state:** automation KV, Git, issues or tickets, or an application
  database

### Restartable polling example

[`patterns/polling`](patterns/polling/) contains a small reconciliation loop.
Each tick reads its state, performs one convergent operation, checkpoints, and
exits. The next tick observes the worker rather than waiting for it.

```text
wake -> read state -> decide -> act or stay quiet -> checkpoint -> exit
  ^                                                               |
  '------------------------ next tick -----------------------------'
```

Inspect a tick without creating a conversation:

```bash
cd patterns/polling
python3 orchestrate_once.py --dry-run
```

The teaching example uses local files so the state is easy to inspect. A
production automation running in ephemeral infrastructure should use a durable
store such as automation KV, GitHub or Jira, or an application database.

### Event-driven example: Jira story to reviewed PR

Polling is one trigger, not a requirement. A workflow with natural external
events can hand work directly between bounded agents:

```text
Jira story or qualifying comment
  -> implementation automation
  -> agent opens a GitHub pull request
  -> pull-request event
  -> independent review agent
  -> review-passed or ready-for-QA event
  -> QA agent
  -> status returns to Jira and GitHub
  -> human decides whether to merge
```

The agents do not need to talk directly. Jira, GitHub, the branch, the pull
request, and the validation results provide the handoffs and durable record.
Retries remain safe when every stage records stable identifiers and checks
whether the intended action already happened.

The
[SDLC Automation Demo](https://github.com/rajshah4/sdlc-automation-github-demo)
contains a larger GitHub-native version of this build, review, and QA flow.

### Three real reconciliation implementations

The decision-maker can be deterministic code, an LLM, or a hybrid of both:

| Example | Trigger and decision loop | Durable state | Useful lesson |
| --- | --- | --- | --- |
| [`patterns/polling`](patterns/polling/) | A deterministic Python tick | Local files in the teaching example | The smallest restartable controller |
| [LXA](https://github.com/jpshackelford/lxa) with [`pr-workflow`](https://github.com/jpshackelford/.openhands/tree/main/plugins/pr-workflow) | A scheduled OpenHands orchestrator reads GitHub and `WORKLOG.md`, dispatches workers, and auto-disables after quiet periods | GitHub plus a Git-backed worklog | Put LLM judgment in the controller when issues and reviews require interpretation |
| [Vibe Manager](https://github.com/rbren/vibe-manager) | A one-minute deterministic watcher fingerprints Kanban and conversation state; it starts an LLM manager only when an actionable change needs judgment | SQLite Kanban state plus automation KV | Keep frequent observation cheap and invoke the model conditionally |

These are variations of the same control pattern. They differ in where
judgment lives, how often the controller wakes, and which system owns state.

## 3. Parent-Child Conversations

![A parent controller starting first-class conversations with explicit or configuration-driven sandbox placement](assets/start-enterprise-conversations.svg)

A live parent owns one bounded request. It breaks the request into focused
assignments, starts first-class worker conversations, observes their status,
validates their output contracts, applies gates, and publishes a lifecycle
report.

**Use it when:** workers need separate histories, visible conversation links,
clean execution environments, different credentials, or human checkpoints
between stages—and one parent can remain active for the bounded lifecycle.

**Typical composition:**

- **Execution:** first-class conversations with configured placement, or
  explicitly prepared and attached sandboxes
- **Coordination:** one live parent starts workers, waits, and applies gates
- **Workflow state:** parent run record, child IDs, and durable Git or ticket
  artifacts

### Example: implementation, review, and QA

```text
request
  -> live parent
     -> implementation child: writable checkout and branch credentials
     -> code-review child: clean checkout and read-only PR access
     -> QA child: fresh test environment and test-only credentials
  -> lifecycle report
  -> human decides whether to merge
```

Each worker receives one responsibility and a small result contract. The
parent advances only when the contract and independent validation permit it.
A blocking review, malformed output, missing final response, or timeout becomes
`needs-human`; it is not silently inferred as success.

The workers should exchange code through durable branches or pull requests,
not by assuming their local files are visible to one another.

Inspect the supervisor without creating conversations:

```bash
cd patterns/parent-child
python3 run_supervisor.py --dry-run
```

[`patterns/parent-child`](patterns/parent-child/) demonstrates the lifecycle
and gates. By default, creating a first-class Enterprise conversation follows
the deployment's configured placement. When explicit isolation is required,
the controller must create a sandbox, wait for it to become ready, and attach
the conversation to it. The common helpers for both modes live in
[`patterns/common/openhands_conversations.py`](patterns/common/openhands_conversations.py).

The
[Enterprise workflow-primitives experiment](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-workflow-primitives)
contains live evidence for conversation startup, explicit placement, durable
event recovery, metrics, and cleanup.

## Combining the Patterns

The three starting points describe control boundaries, not mutually exclusive
products. A continuing workflow often combines them:

```text
scheduled reconciliation tick
  -> observes ticket KAN-42 is ready
  -> starts one bounded parent-child lifecycle
       -> implementation conversation
       -> review conversation
       -> QA conversation
  -> exits

next tick
  -> observes the durable lifecycle result
  -> updates the ticket and admits new work
```

Likewise, an implementation child can use two SDK subagents for research and
test planning without exposing that internal delegation to the campaign-level
controller.

For a real design, write down the composition explicitly:

```text
execution:
worker implementation:
control:
durable state:
active-work limit:
validation:
cleanup owner:
human gate:
scale-out boundary:
untested assumptions:
```

## Execution and Worker Choices

After choosing a control pattern, choose where conversations run and what kind
of agent fills each worker role.

![An OpenHands controller assigning implementation, testing, and review to different coding harnesses](assets/multi-harness-coding-team.svg)

### Execution boundaries

| Boundary | Good when | Important limit |
| --- | --- | --- |
| SDK subagents | A few trusted specialists can share one runtime | Files, credentials, resources, timeout, and failures are shared |
| Isolated Enterprise conversations | Workers cross trust, credential, tenant, or failure boundaries | First-class conversation creation alone does not guarantee isolation |
| Grouped Enterprise conversations | Separate histories matter, but trusted workers can share runtime capacity | Grouping is not security isolation; one owner must manage cleanup |
| Agent Canvas conversations | A trusted team wants lightweight, separately visible workers | Workspace and credential sharing depend on the backend; Canvas is not campaign storage |

### Native agents, command-line harnesses, and ACP

A multi-agent team does not need to use the same coding harness for every
role. OpenHands can coordinate native agents, coding-agent CLIs, and ACP-backed
agents while keeping assignment, validation, and workflow state outside the
individual worker.

| Worker | Use it when | Controller responsibility |
| --- | --- | --- |
| Native OpenHands agent | The worker needs OpenHands tools, skills, plugins, and model configuration | Select the appropriate tools, model, secrets, and result contract |
| Coding-agent CLI | The harness is installed in the runtime or does not expose ACP | Capture lifecycle, authentication, artifacts, and output explicitly |
| ACP-backed profile | Claude Code, Codex, Gemini CLI, or another ACP server should act as the conversation backend | Validate the result like any other worker; ACP does not choose the control pattern |

[`shared_workspace.py`](shared_workspace.py) shows ACP through the SDK in a
shared workspace. [`cloud_conversations.py`](cloud_conversations.py) shows
coding-agent CLIs launched inside managed conversations, with code transferred
through Git.

See [Agent Canvas and ACP](docs/agent-canvas-and-acp.md) for the platform and
harness details.

## Choosing Durable State

Conversation history helps an agent reason, but it should not be the only
campaign record. Durable state should retain ownership, attempts, worker IDs,
artifacts, validation, and the next permitted action.

| State | Good when | Important limit |
| --- | --- | --- |
| Local files | One local controller owns a bounded demo | Files disappear with an ephemeral controller and do not provide concurrent claims |
| Automation KV | One custom automation needs checkpoints across temporary runs | It is not a general multi-controller lease service |
| Files plus Git | One serialized controller needs reviewable, restartable checkpoints | Git is not a transactional queue |
| GitHub, Jira, or another ticket system | Work naturally advances through issues, labels, branches, reviews, or tickets | Poor fit for frequent leases and heartbeats |
| Application database | Multiple controllers or tenants claim work concurrently | Adds schema, migration, backup, and operational responsibility |

A workflow can use more than one. Jira might own the request, GitHub the code
and review artifacts, and automation KV the event-deduplication checkpoint and
active conversation IDs.

## Production Practices

The examples are small, but the operating rules scale:

- use stable workflow, task, attempt, conversation, sandbox, branch, and PR
  identifiers
- record attempts and failures instead of overwriting them
- make dispatch idempotent and recover a crash during conversation creation
- bound concurrency, startup, execution, response, and cleanup time
- require explicit machine-readable worker contracts
- validate artifacts independently of worker self-reports
- preserve enough durable state for a later controller to resume
- assign one cleanup owner for every sandbox or grouped work cell
- treat untrusted issue, ticket, and webhook text as data, not privileged
  instructions
- keep merges, deployments, approvals, and other irreversible actions behind
  human gates

See [Multi-Agent Best Practices](BEST_PRACTICES.md) for the full guidance on
state, capacity, validation, recovery, observability, security, and production
qualification.

## More Working Examples

| Project | What it demonstrates |
| --- | --- |
| [SDLC Automation Demo](https://github.com/rajshah4/sdlc-automation-github-demo) | GitHub-native event handoffs and parent-child build, review, and QA workflows |
| [Agent Canvas SDLC Starter](https://github.com/rajshah4/agent-canvas-sdlc-starter) | A visual local supervisor that creates implementation, review, and QA conversations |
| [OpenHands Agent Research Lab](https://github.com/rajshah4/openhands-agent-research-lab) | Bounded experiments, deterministic validation, durable attempts, and evidence-backed memory |
| [LXA](https://github.com/jpshackelford/lxa) | Long-horizon SDK execution plus a GitHub-backed scheduled repository orchestrator |
| [Vibe Manager](https://github.com/rbren/vibe-manager) | Conditional LLM reconciliation over a continuously polled Kanban and conversation system |

## Reuse the Orchestration Skill

This repository includes the shareable
[`orchestrate-multi-agent-conversations`](.agents/skills/orchestrate-multi-agent-conversations/)
skill. It guides an agent through execution boundaries, worker selection,
control patterns, durable state, result contracts, recovery, capacity,
cleanup, and human gates.

Keep the complete skill directory—including its references and validator
script—under `.agents/skills/` when reusing it in another repository. Then ask
the agent to use `$orchestrate-multi-agent-conversations` for the workflow.

## Repository Map

```text
patterns/
  common/          Enterprise and Agent Canvas conversation adapters
  parent-child/    Live supervisor with bounded child conversations
  polling/         Restartable reconciliation loop

shared_workspace.py     SDK subagents and ACP workers in a shared runtime
cloud_conversations.py  Coding harnesses in managed conversations
BEST_PRACTICES.md       State, recovery, validation, capacity, and cleanup
docs/                   Deeper architecture and platform guidance
.agents/skills/         Reusable orchestration guidance and validators
tests/                  Offline tests for the example controllers
```

## Go Deeper

- [Choosing a Pattern](docs/choosing-a-pattern.md)
- [Polling and reconciliation](patterns/polling/)
- [Parent-child conversations](patterns/parent-child/)
- [Multi-Agent Best Practices](BEST_PRACTICES.md)
- [Agent Canvas and ACP](docs/agent-canvas-and-acp.md)
- [OpenHands Software Agent SDK](https://docs.openhands.dev/sdk/)
- [Reusable orchestration skill](.agents/skills/orchestrate-multi-agent-conversations/)
