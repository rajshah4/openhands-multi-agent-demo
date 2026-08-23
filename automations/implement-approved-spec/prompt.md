# Implement an Approved Specification

A human added the `openhands-implement-spec` label to a GitHub issue. Treat the
issue as approval to prepare an implementation for review, not approval to
merge it.

## Workflow

1. Verify that the event repository matches the cloned repository. Read the
   triggering issue and its comments.
2. Locate the specification and dependency-linked tickets referenced by the
   issue. If they are missing, ambiguous, or not committed, comment with the
   missing information and stop with `needs-human` before changing code.
3. Load and follow the repository-local
   `.agents/skills/implement-spec/SKILL.md` skill.
4. Before delegating, verify that the native `task` tool is available. If it is
   unavailable, do not silently perform the multiagent workflow as one agent;
   comment that native subagents are unavailable and stop with `needs-human`.
5. Use implementer subagents and isolated git worktrees for the ready ticket
   frontier. Merge completed ticket branches into one integration branch in
   dependency order.
6. Run the repository's tests and a read-only code review. Resolve blocking
   findings before marking the pull request ready.
7. Post a concise issue comment containing the parent conversation, branch,
   pull request, completed tickets, validation evidence, and the human's next
   decision.

## Safety And Idempotency

- Search for an existing branch or pull request associated with the issue
  before starting. Resume valid existing work instead of creating a duplicate.
- Never change acceptance tests merely to make the implementation pass.
- Never merge, approve, deploy, change branch protection, or modify secrets.
- Leave the completed pull request ready for human review.
- If delegation, validation, push, or recovery evidence is incomplete, stop
  with `needs-human`; never infer success from partial side effects.

## Final Contract

End with exact plain-text `field: value` lines:

status: done | needs-human | failed
branch: <branch or none>
pr: <url or none>
tests: <concise evidence or not-run>
summary: <five or fewer semicolon-separated items>
next_gate: human-review | stop
