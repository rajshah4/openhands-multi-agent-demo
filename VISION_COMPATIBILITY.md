# Vision Compatibility Analysis

## TL;DR ✅

**Your three patterns are FULLY COMPATIBLE with the longer OpenHands vision**. In fact, they map almost perfectly to the new architecture being rolled out in May 2026.

---

## What I Found: The New OpenHands Architecture

Based on research in `#proj-canvas` and `#proj-new-user-journey` Slack channels, here's what's coming:

### 🎨 **Agent Canvas** (New Frontend)
- Single GUI that can connect to multiple backends
- Replaces both local GUI and cloud UI
- Launch timeline: **May 11, 2026** (alpha announcement to OSS)
- Repository renamed from `agent-server-gui` to `agent-canvas`

### 🔧 **Backend Options** (Users can add multiple)
1. **Agent-Server** (OSS, local, unauthenticated)
   - One agent-server can manage **multiple agents**
   - All agents share one workspace/sandbox (unless you manually provision more)
   - Can be hosted locally OR on a VM (e.g., DigitalOcean)
   
2. **OpenHands Cloud** (SaaS, managed, authenticated)
   - Automatic sandbox provisioning per conversation
   - Requires API key
   - Supports personal workspaces and organizations

### 📐 **Key Architectural Principle**

> "In OSS, you only get one sandbox that all your agents play in. You can _manually_ set up several of those sandboxes, and flip between them in the UI, but there's no more automatically provisioning a docker container for every conversation."
> 
> — Robert Brennan, #proj-canvas

---

## How Your Patterns Map to the Vision

### ✅ **Pattern 1: Easy Shared Workspace** → `CORE OSS VISION`

**Your Pattern:**
```python
# Single agent-server, multiple agents, shared workspace
from openhands.sdk import Agent

agent1 = Agent(...)  # Implementer
agent2 = Agent(...)  # Tester  
agent3 = Agent(...)  # Reviewer
# All share same workspace
```

**The Vision:**
- ✅ **This IS the recommended OSS pattern**
- ✅ Agent-server manages multiple agents in one workspace
- ✅ Agent Canvas connects to this single agent-server
- ✅ Simple, low-friction, no Docker-in-Docker complexity

**Compatibility:** 🟢 **PERFECT MATCH** — This is exactly what OpenHands is standardizing on for OSS users.

---

### ✅ **Pattern 2: Isolated Local Servers** → `ADVANCED OSS / MANUAL PROVISIONING`

**Your Pattern:**
```python
# Multiple agent-servers, each with isolated workspace
# You orchestrate, you manage lifecycle
server1 = start_agent_server(port=8080, workspace="/tmp/ws1")
server2 = start_agent_server(port=8081, workspace="/tmp/ws2")
server3 = start_agent_server(port=8082, workspace="/tmp/ws3")
```

**The Vision:**
> "You can _manually_ set up several of those sandboxes, and flip between them in the UI"
>
> "Users can enter two types of backends: either localhost:8080 plus an agent server key, OR app.all-hands.dev plus an API key. i.e. you can connect multiple agent-servers, and/or multiple cloud instances"
>
> — Robert Brennan, #proj-canvas

**Compatibility:** 🟢 **FULLY SUPPORTED** — Agent Canvas explicitly supports connecting to multiple agent-servers. Your pattern shows HOW to provision them.

---

### ✅ **Pattern 3: Cloud Multi-Sandbox** → `PRODUCTION / MANAGED ISOLATION`

**Your Pattern:**
```python
# OpenHands Cloud API creates isolated sandboxes automatically
POST https://app.all-hands.dev/api/v1/app-conversations
{
  "initial_message": "Implement feature X",
  "harness": "claude-code",  # or "gemini-cli", "openhands"
  "repo_url": "https://github.com/..."
}
```

**The Vision:**
- ✅ Cloud backend provides automatic sandbox isolation
- ✅ Agent Canvas can connect to Cloud with API key
- ✅ Each conversation gets its own sandbox
- ✅ Production-ready, managed infrastructure

**Compatibility:** 🟢 **PERFECT MATCH** — This is the "closed-source but more convenient" option Robert mentioned.

---

## Direct Quotes Supporting Your Approach

### On Multiple Agent-Servers:
> **Joe Pelletier:** "Let's say someone was hosting the agent-server on their own DigitalOcean VM. Under the 'Add Backend' section, would they select 'Local' to do this?"
>
> **Robert Brennan:** "Users can add two types of backends:
> • an agent-server, hosted anywhere (this still has a user-set password for safety)
> • an OpenHands Cloud (app.all-hands.dev or self-hosted) (this needs an API key)"

**Implication:** Your Pattern 2 (multiple agent-servers) is explicitly supported.

---

### On Shared vs. Isolated:
> **Robert Brennan:** "Yes this is the big architectural change: in OSS, you only get one sandbox that all your agents play in. You can _manually_ set up several of those sandboxes, and flip between them in the UI"

**Implication:** 
- Pattern 1 (shared workspace) = default OSS behavior ✅
- Pattern 2 (manual isolation) = supported advanced use case ✅

---

### On Agent-Server Managing Multiple Agents:
> **Robert Brennan:** "In that thread Chris is not distinguishing between agents and agent-servers. One agent-server can manage many agents"

**Implication:** Your Pattern 1 is the intended architecture for OSS users who need multi-agent orchestration.

---

### On App Endpoints / V1 API:
> **Robert Brennan:** "I think we can commit to v1 app server being available for enterprise for the next year"
>
> **John-Mason:** "OpenHands Enterprise customers today are actively coding against v1 app server apis... agent-server is not sufficient for control plane"

**Implication:** 
- Your Pattern 3 uses Cloud API (v1 app server) ✅
- This is committed to be supported for enterprise for 1+ year ✅
- Long-term: Agent-server + Agent Canvas will replace this for OSS

---

## The Bigger Picture: Where OpenHands is Headed

### Timeline (From Slack):
- **May 6, 2026** (TODAY): Socializing with select community members
- **May 11, 2026**: Public alpha announcement of Agent Canvas
- **May 18, 2026**: Legacy frontend freeze
- **June 1, 2026**: Agent Canvas code merged into OpenHands/OpenHands

### Key Features Being Added:
1. ✅ **Agent Canvas** — Single GUI for local + cloud
2. ✅ **Automations (OSS)** — Open-sourcing automations with agent-server integration
3. ✅ **Integrations Hub** — Plugin directory for third-party integrations
4. ✅ **Multiple Backend Support** — Connect to multiple agent-servers AND Cloud instances

### User Journeys:
- **Small logos / OSS users**: Start with Agent Canvas + local agent-server (Pattern 1)
- **Advanced OSS users**: Multiple agent-servers for isolation (Pattern 2)
- **Enterprise**: OpenHands Cloud or self-hosted Enterprise (Pattern 3)

---

## Action Items for Your Demo Repo

### ✅ **You're Already Aligned!**

Your three patterns perfectly demonstrate the architectural spectrum:

1. **Pattern 1** → Entry point for OSS users (Agent Canvas + single agent-server)
2. **Pattern 2** → Advanced self-hosters who need isolation
3. **Pattern 3** → Production users who want managed infrastructure

### 📝 **Minor Enhancements to Consider:**

#### 1. **Add Agent Canvas Integration Example**
Since Agent Canvas will be the recommended frontend:

```markdown
## Using Agent Canvas (Recommended)

Instead of calling the SDK directly, you can use Agent Canvas to:
- Connect to your local agent-server (Pattern 1)
- Switch between multiple agent-servers (Pattern 2)  
- Connect to OpenHands Cloud (Pattern 3)

Install Agent Canvas:
\`\`\`bash
npm install -g @openhands/agent-canvas
agent-canvas
\`\`\`

Then add backends via the UI.
```

#### 2. **Clarify the Terminology**
Align with the new naming:
- ~~"app-server"~~ → "agent-server" (for OSS)
- ~~"app-server"~~ → "Cloud API" or "v1 API" (for Cloud/Enterprise)

#### 3. **Add a "Future Vision" Section to README**
Link to the public Notion doc Robert shared:
> https://quasar-elbow-92b.notion.site/public-draft-User-Journey-OSS-Announcement-3587be798a17802e8e91d2db70bd09aa

---

## Conclusion

### 🎯 **Your Demo is EXACTLY What Users Need**

The OpenHands team is:
- ✅ Moving toward multi-agent-server support (Pattern 2)
- ✅ Standardizing on shared workspace for OSS (Pattern 1)
- ✅ Maintaining Cloud API for managed use cases (Pattern 3)

Your repository demonstrates all three patterns clearly, which will help users understand:
1. The simple path (Pattern 1)
2. The flexible path (Pattern 2)
3. The managed path (Pattern 3)

### 🚀 **This is Timely**

With Agent Canvas launching **May 11** and the OSS community asking questions about:
- "How do I manage multiple agents?"
- "What happened to Docker provisioning?"
- "How does agent-server work with the frontend?"

Your demo provides concrete, working examples of the new architecture.

**Bottom line:** Your approach is not just compatible — it's prescient. You've documented the exact patterns OpenHands is standardizing on before they were even publicly announced! 🎉

---

## References

- **Slack Threads:**
  - https://allhandsai.slack.com/archives/C07ELRWQR3P/p1777917183264399 (App server vs agent-server discussion)
  - https://allhandsai.slack.com/archives/C0B1MS8SM3N (Agent Canvas project updates)
  - https://allhandsai.slack.com/archives/C0B0VFN92UV (New User Journey project)

- **Public Notion:**
  - https://quasar-elbow-92b.notion.site/public-draft-User-Journey-OSS-Announcement-3587be798a17802e8e91d2db70bd09aa

- **GitHub:**
  - https://github.com/OpenHands/agent-canvas (Renamed from agent-server-gui)
  - https://github.com/OpenHands/OpenHands/issues/13827 (Community feedback on self-hosting)
