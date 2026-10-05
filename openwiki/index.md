# Multi-Agent Orchestration Documentation

Complete reference for coordinating multiple OpenHands agents in production workflows.

## Core Documentation

1. **[Quickstart](./quickstart.md)** — Get started in 5 minutes
2. **[Choosing an Approach](./choosing-a-pattern.md)** — Decision guide for your workflow
3. **[Architecture Patterns](./architecture-patterns.md)** — Deep dive into each pattern
4. **[API Reference](./api-reference.md)** — Common interfaces and utilities

## Quick Reference

### The Three Approaches

| Approach | Use When | Complexity | Durability |
|----------|----------|-----------|-----------|
| **In-Conversation Delegation** | Bounded helper runs within a parent | Low | No |
| **Parent-Child Lifecycle** | Supervised workers with separate visibility | Medium | No |
| **Durable Async Workflow** | Work must persist across controller restarts | High | **Yes** |

### Files to Start With

```
shared_workspace.py              # Approach 1 example
patterns/parent-child/           # Approach 2 example
  └─ run_supervisor.py
patterns/polling/                # Approach 3 example
  └─ orchestrate_once.py
```

Run with `--dry-run` to see the controller logic without creating conversations.

## Key Concepts

- **Coordination**: Who owns progress decisions? (parent, supervisor, reconciler)
- **Worker Identity**: Long-lived services or ephemeral conversations?
- **State Persistence**: Where does state survive when a controller restarts?
- **Result Flow**: How do results move between agents?

## Learn More

- See [BEST_PRACTICES.md](../BEST_PRACTICES.md) for production patterns
- See [PATTERNS.md](../PATTERNS.md) for detailed design patterns
- See [README.md](../README.md) for project overview

## Repository Structure

```
.
├── openwiki/                    # This documentation
│   ├── index.md                 # You are here
│   ├── quickstart.md
│   ├── choosing-a-pattern.md
│   ├── architecture-patterns.md
│   └── api-reference.md
├── shared_workspace.py          # Approach 1: in-conversation
├── multi_server_isolation.py    # Approach 1: isolated multi-server
├── cloud_conversations.py       # Cloud platform examples
├── patterns/
│   ├── parent-child/            # Approach 2: supervised workers
│   ├── polling/                 # Approach 3: durable workflows
│   └── common/                  # Shared utilities
├── automations/                 # Automation definitions
├── scripts/                     # Setup and registration scripts
├── docs/                        # Additional documentation
└── tests/                       # Test suite
```

## Navigation

- **Just starting?** → Read [Quickstart](./quickstart.md)
- **Not sure which approach?** → Go to [Choosing an Approach](./choosing-a-pattern.md)
- **Need implementation details?** → See [Architecture Patterns](./architecture-patterns.md)
- **Looking for code examples?** → Check [API Reference](./api-reference.md)
- **Want production patterns?** → Read [BEST_PRACTICES.md](../BEST_PRACTICES.md)
