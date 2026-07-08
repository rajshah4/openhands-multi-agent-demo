# Choosing a Pattern

Both patterns in this repo answer the same question - *how do I coordinate
multiple OpenHands agents?* - and they split on a single axis:

> **Does the orchestrator outlive the work, or does the work outlive the
> orchestrator?**

| | [Supervisor](../patterns/supervisor/) | [Reconciler](../patterns/reconciler/) |
| --- | --- | --- |
| Shape | One live orchestrator delegates bounded children and waits | A scheduled tick observes state, takes one action, exits |
| Scope | One request -> one complete lifecycle, now | An unbounded backlog, forever |
| Where state lives | The orchestrator's context + a run directory | Durable state: files, labels, tickets - the system of record |
| The interface | The child's final-response contract (`status:` / `summary:` / `next_gate:`) | State transitions (`pending` -> `in-flight` -> `done`) |
| Failure recovery | Orchestrator gates on `needs-human` / `failed` | Any tick can crash; the next tick re-reads state and recovers |
| Cost profile | Orchestrator stays alive while children run | Nothing runs between ticks; auto-disables when quiet |
| Time horizon | Minutes to hours | Hours to days to weeks (CI, human review in the loop) |
| Mental model | A project manager running a checklist | A thermostat / Kubernetes controller loop |

## Decide in Two Questions

1. **Is the work one bounded request or an ongoing backlog?**
   One request that should finish while someone watches -> supervisor.
   A backlog that refills and work that waits on slow externals -> reconciler.

2. **Can anything hold state for the whole duration?**
   If a single conversation or process can reasonably stay alive for the whole
   job -> supervisor. If the job spans hours or days, the only reliable memory
   is durable state -> reconciler.

## Compose Them

The patterns are not competitors - the reconciler's worker can be an entire
supervisor lifecycle:

```text
cron tick (reconciler)
  -> observes: ticket KAN-42 is ready
  -> spawns ONE worker: a supervisor conversation
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
is the reconciler in production, and the
[sdlc-automation-github-demo](https://github.com/rajshah4/sdlc-automation-github-demo)
is the supervisor in production.

## The State Question (Where Worker Output Goes)

The most common adaptation mistake is assuming a worker's files are visible to
the orchestrator. Whether they are depends on the runtime:

- **Separate sandboxes** (OpenHands Cloud/Enterprise conversations - the
  default in this repo): a worker's local files are invisible to everyone
  else. Durable output travels through the **final response** (supervisor) or
  **the system of record** - git, tickets, labels (reconciler).
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
