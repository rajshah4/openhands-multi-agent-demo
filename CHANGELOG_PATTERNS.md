# Pattern Documentation Update

## Summary

Updated the repository to clearly document **three architectural patterns** for
multi-agent orchestration with OpenHands, clarifying the isolation vs. complexity
trade-offs and when to use each approach.

## Current Direction

The repo now positions harness flexibility as one part of a broader
multi-agent pattern catalog. The main choices are:

- **Workflow pattern**: how work advances between agents.
- **Runtime pattern**: where agents run and how isolated they are.
- **User/control surface**: whether the workflow starts from a script,
  automation, Agent Canvas, or another product surface.

The repo also includes workflow patterns beyond harness/runtime selection:

- **Linear pipeline**: implement -> test -> review.
- **Parent-child supervisor**: one parent conversation delegates bounded child
  conversations and gates on their final responses.
- **Polling continuation loop**: a scheduled orchestrator wakes every 15
  minutes, checks durable state, spawns at most one worker, logs, and exits.

## What Changed

### 1. Updated `README.md`

**Before:** Described "two approaches" (Cloud vs SDK)

**After:** Describes "three patterns" with clear comparison table:
- **Pattern 1: Easy** — Single agent-server (`shared_workspace.py`)
- **Pattern 2: Isolated Local** — Multiple agent-servers (`multi_server_isolation.py`)
- **Pattern 3: Cloud** — Cloud-managed sandboxes (`cloud_conversations.py`)

**Key additions:**
- Pattern comparison table at the top
- "When to Use Each Pattern" decision guide
- Architecture insights explaining why Pattern 3 = Isolation + Simplicity
- Updated file descriptions to map to patterns

### 2. Created `PATTERNS.md`

**New comprehensive guide** covering:
- Visual architecture diagrams for all three patterns
- Detailed code examples for each pattern
- Orchestration responsibilities breakdown
- Pros/cons analysis
- Decision tree for pattern selection
- Migration path recommendations
- "Goldilocks Principle" explanation

**Key sections:**
- Pattern 1: Easy (10 lines, no isolation)
- Pattern 2: Isolated Local (150 lines, manual orchestration)
- Pattern 3: Cloud (50 lines, automatic orchestration)

### 3. Created `multi_server_isolation.py`

**New conceptual implementation** showing Pattern 2:
- ~200 lines demonstrating multi-agent-server orchestration
- Shows infrastructure management complexity
- Illustrates manual git coordination
- Includes detailed comments explaining each step

**Purpose:** Educational — shows what Pattern 2 entails so users understand
why Pattern 1 (simple) or Pattern 3 (Cloud) are better choices for most use cases.

## Key Insights Documented

### The Coordination Burden

| Pattern | You Manage | Lines of Code |
|---------|-----------|---------------|
| Pattern 1 (Easy) | Nothing special | ~10 |
| Pattern 2 (Isolated Local) | Servers, ports, git, cleanup | ~150 |
| Pattern 3 (Cloud) | High-level workflow only | ~50 |

### The "Goldilocks" Principle

```
Pattern 1: Too coupled      → Local dev
Pattern 2: Too complex      → Air-gapped only  
Pattern 3: Just right! ✨    → Production
```

**Cloud (Pattern 3) = Isolation (Pattern 2) + Simplicity (Pattern 1)**

### Architecture Compatibility

All three runtime patterns can be shown through Agent Canvas or driven from
scripts/automations:

- Pattern 1: Canvas or script -> local agent-server and shared workspace.
- Pattern 2: Canvas or script -> local orchestrator plus isolated workspaces.
- Pattern 3: Canvas or script -> Cloud/Enterprise conversations where the
  platform manages sandboxes.

With ACP connectivity, Agent Canvas can include specialized external harnesses
inside those patterns while keeping the workflow contract stable.

Pattern 3 remains the production-oriented example because the platform manages
sandbox provisioning, observability, and cleanup.

## Migration Path

Documented recommended progression:
1. Start with **Pattern 1** (prove concept locally)
2. Move to **Pattern 3** (scale to production with Cloud)
3. Consider **Pattern 2** only if Cloud isn't an option

## Visual Improvements

Added ASCII diagrams showing:
- Single shared workspace (Pattern 1)
- Multiple isolated workspaces with git coordination (Pattern 2)  
- Cloud-managed automatic provisioning (Pattern 3)

## Files Updated/Created

- ✏️  `README.md` — Restructured around three patterns
- ✨ `PATTERNS.md` — New comprehensive patterns guide
- ✨ `multi_server_isolation.py` — New conceptual Pattern 2 implementation
- ✨ `CHANGELOG_PATTERNS.md` — This document

## Usage Examples

### Pattern 1 (Easy)
```bash
python shared_workspace.py
```

### Pattern 2 (Isolated Local)
```bash
python multi_server_isolation.py  # Conceptual - shows orchestration complexity
```

### Pattern 3 (Cloud)
```bash
python cloud_conversations.py
```

## Value Proposition

The documentation now clearly shows:

1. **For developers:** Pattern 1 is simplest for local work
2. **For enterprises:** Pattern 3 provides isolation + observability without complexity
3. **For special cases:** Pattern 2 exists for air-gapped scenarios, but comes with 5x orchestration overhead

This aligns with the new OpenHands vision: simple local development (agent-server)
scales seamlessly to production (Cloud) without requiring users to manage
multi-server infrastructure themselves.
