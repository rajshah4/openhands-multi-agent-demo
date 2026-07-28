# Parent And Child Prompt Contracts

## Visible Parent Prompt

Keep the visible automation prompt understandable to a customer. Explain only:

- what the automation coordinates
- what event triggered it
- what it posts back
- where humans remain in control

Avoid internal bug history, expected outcomes, secret names, implementation trivia, and long shell walkthroughs. Put operational detail in version-controlled skills and scripts.

## Child Prompt Shape

Give each child:

1. A single role and bounded objective
2. Issue, repository, branch, and parent run identifiers
3. Relevant repo-local skill paths
4. Allowed side effects
5. Required validation
6. Explicit prohibitions
7. A final output contract

Require children to place all gate evidence in their final response because
first-class child conversations do not guarantee whether uncommitted files are
shared with the parent.

## Story-To-PR Contract

```text
status: done | needs-human | failed
artifact: <path or none>
branch: <branch or none>
pr: <url or none>
summary: <five or fewer bullets>
next_gate: code-review | human-review | stop
```

Advance only when `status: done` and `next_gate: code-review`.

## Code-Review Contract

```text
status: pass | findings | needs-human | failed
blocking: yes | no
artifact: <path or none>
pr: <url or none>
summary: <five or fewer bullets>
next_gate: qa | human-review | stop
```

Advance only when status is `pass` or `findings`, `blocking: no`, and `next_gate: qa`.

## QA Contract

```text
status: pass | needs-human | failed
artifact: <path or none>
pr: <url or none>
summary: <five or fewer bullets>
next_gate: human-review | stop
```

Complete automation only when `status: pass` and `next_gate: human-review`. Keep merge as a human decision.

## Contract Parsing Rules

- Parse exact top-level `field: value` lines.
- Normalize field names and enumerated values to lowercase.
- Reject duplicate fields with conflicting values.
- Reject missing required fields.
- Treat unknown status or gate values as malformed.
- Never infer a passing contract from commits, comments, or tests alone.
- Preserve the original response as an artifact, but do not dump it into parent logs.
