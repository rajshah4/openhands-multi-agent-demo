# Execution Boundaries and Runtime Placement

This guide answers **where agents run and what they share**. It does not define
how work advances.

Choose the orchestration approach first in
[Choosing an Approach](docs/choosing-a-pattern.md):

1. bounded in-conversation delegation
2. bounded supervised lifecycle
3. durable asynchronous workflow

Then choose a placement boundary for each worker. The same orchestration
approach can use different placements as trust, scale, and failure requirements
change.

## Keep Four Decisions Separate

| Decision | Question | Examples |
| --- | --- | --- |
| Orchestration approach | Who owns progress, and how long must that owner survive? | Parent delegation, live supervisor, durable reconciler or event chain |
| Conversation identity | Does the worker need its own history and audit record? | Subagent task, first-class conversation |
| Runtime placement | What do workers share? | Workspace, process, credentials, compute, sandbox, timeout |
| Worker implementation | Which coding harness performs the assignment? | Native OpenHands agent, command-line harness, ACP-backed profile |

A **conversation** is an ownership, history, and audit boundary. A **sandbox**
is a compute, filesystem, credential, timeout, and failure boundary. A Git
worktree separates files, but it does not create a new process, credential set,
or failure boundary.

## Placement Overview

| Placement | File boundary | Compute and credential boundary | Operational cost | Good fit |
| --- | --- | --- | --- | --- |
| **Shared workspace/runtime** | Shared | Shared | Low | Trusted sequential specialists and local prototypes |
| **Git worktrees or isolated clones** | Separate working trees | Usually shared host and credentials | Medium to high | Parallel file isolation without managed sandboxes |
| **Grouped managed conversations** | Backend-dependent conversation workspaces | Shared sandbox capacity | Medium | Trusted workers need separate histories but may share compute |
| **Isolated managed sandboxes** | Separate | Separate when explicitly configured | Medium | Trust, tenant, credential, or failure boundaries |

First-class conversation creation does not by itself prove isolation. Managed
placement follows backend configuration unless the controller explicitly
creates a sandbox and attaches the conversation to it.

## Quick Decision Guide

```text
Do workers cross a trust, tenant, credential, or failure boundary?
|
+-- Yes -> require explicitly isolated sandboxes
|
+-- No -> Do concurrent workers need separate files?
          |
          +-- No -> shared workspace/runtime
          |
          +-- Yes -> Do separate conversation histories matter?
                     |
                     +-- No -> Git worktrees or isolated clones
                     |
                     +-- Yes -> grouped managed conversations or
                                first-class conversations with worktrees
```

Isolation is not automatically better. Use the narrowest boundary that meets
the real risk and observability requirements.

## Shared Workspace and Runtime

All workers read and write one workspace. This is the smallest local setup and
the fastest handoff because output is immediately visible to the next worker.

```text
one process or sandbox
+-- shared workspace
    +-- implementer
    +-- tester
    +-- reviewer
```

[`shared_workspace.py`](shared_workspace.py) demonstrates two application
paths in one workspace:

- Approach 1 native `TaskToolSet` subagents inside one parent conversation
- an application-controlled Approach 2 pipeline with ACP-backed SDK
  conversations; its final review conversation nests Approach 1 delegation

### Advantages

- minimal infrastructure and coordination code
- direct file handoff
- fast local iteration
- convenient for trusted sequential work

### Limits

- workers can overwrite or corrupt shared state
- filesystem, credentials, compute, timeout, and failures are coupled
- parallel writes to the same files are unsafe
- a separate SDK `Conversation` object does not create runtime isolation

Use this placement for prototypes, sequential pipelines, and tightly trusted
specialists. Add a stronger boundary before crossing trust or credential
boundaries. The SDLC demo's
[shared-working-tree case study](https://github.com/rajshah4/sdlc-automation-github-demo/blob/main/docs/agent-canvas-dark-factory-demo.md)
records this trade-off in a larger workflow.

## Git Worktrees or Isolated Clones

Each worker gets a separate working tree or clone. Code moves through commits,
branches, and explicit merges instead of direct file sharing.

```text
local controller
+-- bare or remote Git origin
    +-- implementation worktree
    +-- test worktree
    +-- review worktree
```

[`multi_server_isolation.py`](multi_server_isolation.py) demonstrates the
heavier isolated-clone variant: it creates a temporary bare origin, prepares
separate clones, runs one SDK conversation per phase, and performs explicit Git
handoffs and local verification.

Git worktrees provide a lighter version when workers may share one host and
repository object database. Matt Pocock's
[`implement-spec`](https://github.com/mattpocock/skills/tree/main/skills/in-progress/implement-spec)
uses worktrees to isolate parallel implementers inside one bounded parent run.

### Advantages

- conflicting file edits are separated
- branches and commits create durable reviewable handoffs
- works locally and in air-gapped environments
- does not require a managed sandbox service

### Limits

- process, credentials, host resources, and failures may still be shared
- the controller owns branch creation, synchronization, merge conflicts, and
  cleanup
- Git is a durable artifact channel, not a transactional queue or lease system
- long-running workflows still need a durable workflow ledger

Use worktrees when file isolation is enough. Use isolated clones when workers
need separate repository directories or machines and the extra Git coordination
is justified.

## Grouped Managed Conversations

First-class conversations retain separate histories and visible URLs while a
backend groups trusted workers into shared sandbox capacity.

```text
one managed sandbox
+-- conversation A workspace
+-- conversation B workspace
+-- conversation C workspace
```

Grouping can reduce startup overhead and improve utilization. It is useful for
a bounded supervised lifecycle when workers need distinct identities but belong
to one trusted team.

### Limits

- grouping is not a security or tenant-isolation boundary
- workers may share credentials, compute pressure, timeout, and sandbox failure
- workspace sharing depends on backend behavior and must be tested
- one owner must manage capacity, draining, reference counts, and cleanup

The
[Enterprise sandbox-grouping experiment](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-sandbox-grouping)
contains measured evidence and explicit production limitations.

## Isolated Managed Sandboxes

Workers that cross trust, credential, tenant, or failure boundaries should use
explicitly isolated sandboxes.

```text
controller
+-- implementation conversation + writable sandbox
+-- review conversation + read-only sandbox
+-- QA conversation + test-only sandbox
```

[`cloud_conversations.py`](cloud_conversations.py) demonstrates a bounded
application-controlled lifecycle using managed first-class conversations and
Git handoff. Default placement follows the deployment configuration. When exact
isolation is required, use the explicit create, prepare, attach, and cleanup
helpers in
[`patterns/common/openhands_conversations.py`](patterns/common/openhands_conversations.py).
The SDLC demo's
[separate-sandboxes case study](https://github.com/rajshah4/sdlc-automation-github-demo/blob/main/docs/replicated-jira-delegated-factory-demo.md)
shows this placement in a larger delegated workflow.

### Advantages

- strongest compute, filesystem, credential, timeout, and failure separation
- independently visible conversation histories
- backend-managed provisioning and observability
- clearer security and cleanup ownership

### Limits

- more startup latency and capacity consumption
- output must move through final responses, Git, tickets, or another durable
  channel
- explicit placement and cleanup must be qualified against the deployed version
- conversation creation alone does not guarantee a new sandbox

The
[Enterprise workflow-primitives experiment](https://github.com/rajshah4/openhands-agent-research-lab/tree/main/experiments/enterprise-workflow-primitives)
probes explicit sandbox attachment, event recovery, metrics, and cleanup. It is
infrastructure evidence for supervised and durable workflows, not a separate
orchestration approach.

## Where Agent Canvas Fits

Agent Canvas is a visual control surface over the same decisions:

- a local supervisor can create separately visible conversations in one shared
  workspace
- conversations can use dedicated Git worktrees for file isolation
- a scheduled controller can show a durable workflow as a sequence of temporary
  manager and worker conversations
- saved native or ACP-backed profiles can fill worker roles without changing
  the orchestration approach

Canvas makes delegation visible. It does not, by itself, provide campaign
storage or prove sandbox isolation.

## Native Agents, Command-Line Harnesses, and ACP

Worker implementation is another independent choice:

| Worker | Use it when | Controller responsibility |
| --- | --- | --- |
| Native OpenHands agent | The worker needs OpenHands tools, skills, plugins, and model configuration | Select tools, model, secrets, placement, and result contract |
| Coding-agent CLI | The harness is installed in the runtime or does not expose ACP | Capture lifecycle, authentication, artifacts, and output explicitly |
| ACP-backed profile | Claude Code, Codex, Gemini CLI, or another ACP server should act as the conversation backend | Validate the result like any worker; ACP does not choose placement or control |

Do not infer isolation from the agent harness. A native agent, CLI, or ACP-backed
profile can run in a shared workspace, a grouped sandbox, or an isolated
sandbox.

## State Handoff by Placement

| Placement | Appropriate handoff |
| --- | --- |
| Shared workspace | Files plus a final response or small result contract |
| Worktrees or clones | Branches, commits, merges, and validation results |
| Grouped managed conversations | Final responses plus Git or backend-qualified shared artifacts |
| Isolated managed sandboxes | Final responses, Git, tickets, object storage, or another durable system |

Never assume a worker's local files are visible to its controller or sibling.
Make the transfer mechanism explicit in every assignment.

## Evolving a Design

A common progression is:

1. Prove the bounded workflow in a shared workspace.
2. Add worktrees when parallel file conflicts appear.
3. Move work to first-class conversations when auditability or independent
   histories matter.
4. Require explicitly isolated sandboxes when trust, credentials, tenants, or
   failure domains diverge.
5. Add durable reconciliation or event handoffs when the logical workflow must
   survive controller termination.

These steps are independent. A durable workflow may still use shared local
workers for a trusted team, while one bounded request may require fully isolated
children for security reasons.

## Summary

Choose orchestration by **who owns progress and for how long**. Choose runtime
placement by **what workers may safely share**. Choose worker implementation by
**which harness best performs the assignment**. Record all three explicitly;
do not compress them into one numbered pattern name.
