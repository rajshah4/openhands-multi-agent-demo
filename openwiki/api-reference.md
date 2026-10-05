# API Reference

Common interfaces and utilities used across multi-agent orchestration patterns.

## Conversation Management

### Creating Conversations

#### OpenHands Conversations (Enterprise / Cloud)

```python
from patterns.common.openhands_conversations import (
    OpenHandsConversationClient,
    ConversationContext,
)

# Initialize client
client = OpenHandsConversationClient(
    agent_server_url="https://api.openhands.example.com",
    api_key="your-api-key"
)

# Create a conversation
context = ConversationContext(
    repo_name="my-repo",
    repo_branch="main",
)

conversation = client.create_conversation(context)

# Send messages
response = client.send_message(
    conversation_id=conversation.id,
    prompt="Analyze this code for bugs",
    max_iterations=10
)

# Get results
result = client.get_conversation_state(conversation_id=conversation.id)
```

#### Canvas Conversations (Local Agent Canvas)

```python
from patterns.common.canvas_conversations import CanvasConversationClient

# Initialize for local Agent Canvas
client = CanvasConversationClient(
    agent_server_url="http://localhost:8001"
)

# Create and manage conversations
conversation = client.create_conversation()
response = client.send_message(
    conversation_id=conversation.id,
    prompt="Your task here"
)
```

### Conversation Lifecycle

| Method | Description | Returns |
|--------|-------------|---------|
| `create_conversation(context)` | Start a new conversation | `Conversation` |
| `send_message(id, prompt, ...)` | Send user message | `Response` |
| `get_conversation_state(id)` | Get current state | `ConversationState` |
| `get_file(id, path)` | Read file from conversation workspace | `bytes` |
| `put_file(id, path, content)` | Write file to conversation workspace | `None` |
| `close_conversation(id)` | End conversation | `None` |

---

## State Persistence

### File-Based State (Shared Workspace)

For Pattern 1 (in-conversation delegation), all agents share files in the workspace:

```python
# Parent writes work for helper
with open("/workspace/task.json", "w") as f:
    json.dump({"task": "analyze", "data": data}, f)

# Helper reads, processes, and writes result
with open("/workspace/task.json", "r") as f:
    task = json.load(f)

result = process(task["data"])

with open("/workspace/result.json", "w") as f:
    json.dump({"status": "completed", "result": result}, f)

# Parent reads result
with open("/workspace/result.json", "r") as f:
    result = json.load(f)
```

### API-Based State (Parent-Child)

For Pattern 2 (parent-child lifecycle), children communicate via API or shared service:

```python
# Supervisor stores work item
work_item = {
    "id": "child-1",
    "task": "audit-module-a",
    "status": "assigned",
}
state_store.put(work_item)

# Child polls for work
work_item = state_store.get("child-1")

# Child processes and updates
work_item["status"] = "completed"
work_item["result"] = audit_results
state_store.put(work_item)

# Supervisor polls for completion
work_item = state_store.get("child-1")
if work_item["status"] == "completed":
    print(f"Child completed: {work_item['result']}")
```

### Queue-Based State (Durable Workflow)

For Pattern 3 (durable async workflow), state lives in a persistent queue:

```python
class WorkItem:
    """Durable work item in a queue."""
    id: str
    status: str  # "pending", "processing", "completed", "failed"
    input_data: dict
    result_data: dict = None
    retry_count: int = 0

# Controller: read pending items
pending = queue.list_items(status="pending", limit=10)

for item in pending:
    # Idempotency check
    if item.status != "pending":
        continue
    
    # Mark as processing
    item.status = "processing"
    queue.update(item)
    
    try:
        # Spawn worker
        result = spawn_agent(item.input_data)
        
        # Mark as completed
        item.status = "completed"
        item.result_data = result
        queue.update(item)
    except Exception as e:
        # Retry logic
        item.retry_count += 1
        if item.retry_count > 3:
            item.status = "failed"
        else:
            item.status = "pending"  # Requeue
        queue.update(item)
```

---

## Common Patterns

### Spawning a Worker Conversation

```python
def spawn_worker(parent_client, work_item, timeout_sec=300):
    """Spawn a worker conversation and wait for completion."""
    
    # Create worker conversation
    worker = parent_client.create_conversation()
    
    # Send task
    response = parent_client.send_message(
        conversation_id=worker.id,
        prompt=f"Process this work item: {work_item}",
        max_iterations=10,
    )
    
    # Wait for completion or timeout
    result = parent_client.get_conversation_state(
        conversation_id=worker.id,
        timeout_sec=timeout_sec
    )
    
    return result
```

### Supervisor Spawning Multiple Children

```python
async def supervise_parallel_workers(supervisor_client, children_specs):
    """Spawn multiple child conversations in parallel."""
    
    children = []
    for spec in children_specs:
        child = supervisor_client.create_conversation()
        response = supervisor_client.send_message(
            conversation_id=child.id,
            prompt=spec["prompt"],
            max_iterations=spec.get("max_iterations", 5),
        )
        children.append((child.id, response))
    
    # Wait for all children
    results = []
    for child_id, _ in children:
        result = supervisor_client.get_conversation_state(child_id)
        results.append(result)
    
    return results
```

### Polling Controller Loop

```python
def polling_controller(queue_client, spawn_func, poll_interval_sec=60):
    """Main loop for a durable polling controller."""
    
    while True:
        try:
            # Read pending work items
            items = queue_client.list_items(status="pending", limit=10)
            
            if not items:
                time.sleep(poll_interval_sec)
                continue
            
            # Process each item
            for item in items:
                # Idempotency: skip if already processing
                if item.status != "pending":
                    continue
                
                # Mark as processing
                item.status = "processing"
                queue_client.update(item)
                
                try:
                    # Spawn worker
                    result = spawn_func(item)
                    
                    # Mark as completed
                    item.status = "completed"
                    item.result = result
                    queue_client.update(item)
                except Exception as e:
                    # Retry logic
                    item.retry_count += 1
                    if item.retry_count > 3:
                        item.status = "failed"
                        item.error = str(e)
                    else:
                        item.status = "pending"
                    queue_client.update(item)
        
        except Exception as e:
            # Log and continue
            logger.error(f"Controller error: {e}")
            time.sleep(poll_interval_sec)
```

---

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENHANDS_API_KEY` | API key for OpenHands Cloud | `oh_sk_...` |
| `AGENT_SERVER_URL` | Local Agent Canvas URL | `http://localhost:8001` |
| `REPO_URL` | Git repository URL | `https://github.com/owner/repo` |
| `REPO_BRANCH` | Git branch to clone | `main` |
| `OPENHANDS_WORKSPACE` | Shared workspace path | `/workspace/agent-work` |

### Configuration File

```python
from dataclasses import dataclass

@dataclass
class Config:
    """Orchestration configuration."""
    agent_server_url: str = "http://localhost:8001"
    api_key: str = None
    repo_url: str = None
    repo_branch: str = "main"
    max_workers: int = 5
    timeout_sec: int = 300
    retry_attempts: int = 3

# Load from environment or file
config = Config(
    api_key=os.environ.get("OPENHANDS_API_KEY"),
    agent_server_url=os.environ.get("AGENT_SERVER_URL", "http://localhost:8001"),
)
```

---

## Error Handling

### Common Exceptions

| Exception | Cause | Handling |
|-----------|-------|----------|
| `ConversationTimeout` | Agent didn't complete in time | Retry or mark as failed |
| `AuthenticationError` | Invalid API key | Check credentials |
| `WorkspaceError` | Shared workspace not accessible | Check filesystem permissions |
| `AgentError` | Agent encountered an error | Inspect conversation logs |

### Retry Strategy

```python
import time
from functools import wraps

def retry_with_backoff(max_attempts=3, initial_delay=1):
    """Decorator for retry logic with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator

@retry_with_backoff(max_attempts=3)
def spawn_and_await_worker(client, task):
    worker = client.create_conversation()
    return client.send_message(worker.id, task)
```

---

## Next Steps

- See `patterns/parent-child/run_supervisor.py` for a working parent-child example
- See `patterns/polling/orchestrate_once.py` for a working polling example
- Read [Best Practices](../BEST_PRACTICES.md) for error handling and observability patterns
