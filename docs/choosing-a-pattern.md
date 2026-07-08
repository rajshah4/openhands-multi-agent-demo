# Choosing a Pattern

Both patterns in this repo answer the same question - *how do I coordinate
multiple OpenHands agents?* - and they split on a single axis:

> **Does the orchestrator outlive the work, or does the work outlive the
> orchestrator?**

| | [Parent-Child](../patterns/parent-child/) | [Polling Loop](../patterns/polling/) |
| --- | --- | --- |
| Shape | One live parent delegates bounded children and waits | A scheduled tick observes state, takes one action, exits - it never waits |
| Scope | One request -> one complete lifecycle, now | An unbounded backlog, forever |
| Where state lives | The orchestrator's context + a run directory | Durable state: files, labels, tickets - the system of record |
| The interface | The child's final-response contract (`status:` / `summary:` / `next_gate:`) | State transitions (`pending` -> `in-flight` -> `done`) |
| Failure recovery | Orchestrator gates on `needs-human` / `failed` | Any tick can crash; the next tick re-reads state and recovers |
| Cost profile | Orchestrator stays alive while children run | Nothing runs between ticks; auto-disables when quiet |
| Time horizon | Minutes to hours | Hours to days to weeks (CI, human review in the loop) |
| Mental model | A project manager running a checklist | A thermostat / Kubernetes controller loop |

## Decide in Two Questions

1. **Is the work one bounded request or an ongoing backlog?**
   One request that should finish while someone watches -> parent-child.
   A backlog that refills and work that waits on slow externals -> polling loop.

2. **Can anything hold state for the whole duration?**
   If a single conversation or process can reasonably stay alive for the whole
   job -> parent-child. If the job spans hours or days, the only reliable
   memory is durable state -> polling loop.

## Compose Them

The patterns are not competitors - the polling loop's worker can be an entire
parent-child lifecycle:

```text
cron tick (polling loop)
  -> observes: ticket KAN-42 is ready
  -> spawns ONE worker: a parent-child lifecycle
       -> child: story-to-pr
       -> child: code-review
       -> child: qa
       -> lifecycle report
  -> exits
next tick observes the lifecycle result and updates the ticket
```

Backlog-level orchestration outside, lifecycle-level orchestration inside.
This is exactly how a continuously running software factory is shaped: the
[ohtv-workflow plugin](https://github.com/jpshackelford/.openhands/tree/main/plugins/ohtv-workflow)
is the polling loop in production, and the
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo)
is the parent-child factory in production.

## The Third Option: No Orchestrator At All

Parent-child and polling both keep an orchestrator. **Event-driven handoff**
removes it: each agent finishes by changing the system of record (a push, a
label, a ticket transition), and that change triggers the next agent through
an automation or webhook.

| Pattern | Who advances the work |
| --- | --- |
| Parent-child | A live parent |
| Polling loop | A scheduled tick |
| Event-driven handoff | The event itself |

Use it when the workflow is already expressed in a system of record and every
step has a natural trigger. The production example is the GitHub-label path in
the sdlc demo; see the README's Pattern 3 section for how this repo's linear
pipeline demos map onto it.

## Subagents: Delegation Inside One Conversation

The three patterns coordinate work *across* conversations. The OpenHands SDK's
[TaskToolSet](https://docs.openhands.dev/sdk/guides/task-tool-set) adds a
smaller delegation unit below that level: a parent agent launches a
specialized **subagent** as a tool call inside its own conversation. The
subagent runs synchronously - the parent blocks until it finishes and returns
a `TaskObservation` with the result text - and it can be resumed later by task
id with its full conversation history reloaded. Beyond the general-purpose
default, custom specializations (a code reviewer, a test planner, a domain
expert) register with `register_agent()`.

The shape is parent-child in miniature. What changes is the boundary:

| | Subagent (TaskToolSet) | Child conversation (Pattern 1) |
| --- | --- | --- |
| Where it runs | Inside the parent's conversation and runtime | Its own conversation - own sandbox on Cloud/Enterprise |
| Visibility | A tool call in the parent's event stream | A separate conversation URL you can open, watch, and audit |
| Blocking | Synchronous - the parent blocks until the step's subagent calls return | The parent chooses when to wait and where to gate |
| Context handoff | Prompt in, result text out; resumable by task id | Final-response contract (`status:` / `summary:` / `next_gate:`) |
| Use when | Bounded expert help mid-task: review this diff, plan these tests, look up context | Lifecycle steps that need isolation, their own audit trail, or human gates between them |

Use a subagent when an agent needs bounded expert help and can wait for the
answer. Reach for full child conversations when visibility, separate
sandboxes, or a customer-facing audit trail matter. The two compose: a
Pattern 1 child (or a polling worker) can use subagents internally for its
own lookups without the orchestrator ever knowing.

A related but different knob is
[parallel tool execution](https://docs.openhands.dev/sdk/guides/parallel-tool-execution):
setting `tool_concurrency_limit` on the `Agent` (default `1`, i.e.
sequential; the feature is experimental) lets one agent step run several
independent tool calls concurrently. On its own it is not an orchestration
pattern - nothing about *who advances the work* changes. It matters here
because a subagent launch is itself a tool call, so a parent with
`tool_concurrency_limit > 1` can fan out several subagents in a single step
and block until they all return. The safety caveat is the same as this repo's
state rule below: tool calls (including subagents) that modify shared state
or write the same files are not safe to run concurrently.

## The State Question (Where Worker Output Goes)

The most common adaptation mistake is assuming a worker's files are visible to
the orchestrator. Whether they are depends on the runtime:

- **Separate sandboxes** (OpenHands Cloud/Enterprise conversations - the
  default in this repo): a worker's local files are invisible to everyone
  else. Durable output travels through the **final response** (parent-child) or
  **the system of record** - git, tickets, labels (polling loop).
- **Shared working tree** (local Agent Canvas, shared SDK workspace): workers
  read and write the same directory. Files transfer directly, but runs are not
  parallel-safe and mutate the real checkout.

The full write-up, learned the hard way, is in the sdlc repo's state-model
sections:
[shared working tree](https://github.com/rajshah4/sdlc-automation-github-demo/blob/main/docs/agent-canvas-dark-factory-demo.md)
vs
[separate sandboxes](https://github.com/rajshah4/sdlc-automation-github-demo/blob/main/docs/replicated-jira-delegated-factory-demo.md).

## Code or Model as the Decision-Maker

Independent of the pattern, the decision loop itself can be:

- **Deterministic code** (this repo's scripts): cheap, reproducible, easy to
  test. Right when the decision is mechanical - next pending task, gate on a
  status string.
- **An LLM following a skill** (ohtv's `/orchestrate`, the sdlc repo's parent
  conversation): right when the state is natural language - issues written by
  humans - and the decision needs judgment.

Start deterministic. Add the model where mechanical rules stop being enough.
