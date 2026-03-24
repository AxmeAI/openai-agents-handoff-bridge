# OpenAI Agents SDK + AXME Human Approval Bridge

OpenAI Agents SDK gives you powerful agents with tool use, handoffs, and
guardrails. But production needs human approval gates that can wait hours or
days, retry on failure, enforce timeouts, and survive process restarts. You end
up building 200 lines of infrastructure — polling loops, database state, email
notifications — before writing any agent logic. AXME handles all of that.

> **Alpha** -- AXME is in alpha. APIs may change. Not recommended for production
> workloads without contacting the team first. See [AXME Cloud Alpha](https://cloud.axme.ai/alpha).

---

## Before / After

### Before: DIY Approval Infrastructure

```python
# You end up building this yourself:
import asyncio, sqlite3, smtplib, time

# Persist approval state across restarts
db = sqlite3.connect("approvals.db")
db.execute("CREATE TABLE IF NOT EXISTS approvals (...)")

# Poll for human response
while True:
    row = db.execute("SELECT approved FROM approvals WHERE id=?", (task_id,)).fetchone()
    if row:
        break
    time.sleep(10)  # What if the process crashes here?

# Retry on failure? Build it. Timeouts? Build it. Observability? Build it.
# 200+ lines of infrastructure before any agent logic
```

### After: AXME Handles It

```python
# Agent does its work, then requests human approval via AXME
intent_id = client.send_intent({
    "intent_type": "human_approval",
    "to_agent": "agent://approver",
    "payload": {"task": "Deploy model v2.3 to production", "risk_level": "high"}
})
# AXME durably waits — hours, days. Survives restarts. Retries delivery.
result = client.wait_for(intent_id, timeout_seconds=604800)  # 7 day timeout
if result.get("data", {}).get("approved"):
    proceed_with_deployment()
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your AXME API key and OpenAI API key
```

### 3. Run the scenario

```bash
# Terminal 1: Start the agent (processes tasks + requests human approval)
python agent.py

# Terminal 2: Send a task for processing
python initiator.py
```

The initiator sends a task. The OpenAI agent processes it, determines human
approval is needed, and creates a durable approval request via AXME. The human
can approve hours later -- AXME holds the state. When approved, the agent
resumes and completes the task.

---

## How It Works

```
┌────────────────────┐      ┌──────────────────┐      ┌──────────────┐
│  Your Application  │      │   AXME Cloud     │      │    Human     │
│                    │      │                  │      │   Reviewer   │
│  ┌──────────────┐  │ send │  ┌────────────┐  │notify│              │
│  │ OpenAI Agent │──┼────> │  │  Intent    │──┼────> │  Dashboard   │
│  │ (Agents SDK) │  │      │  │  (durable) │  │      │  or CLI      │
│  │              │  │      │  │            │  │      │              │
│  │ - Tool use   │  │      │  │  Waiting   │  │      │  Approve /   │
│  │ - Guardrails │  │      │  │  State     │<─┼───── │  Reject      │
│  │ - Handoffs   │  │      │  │  (7 days)  │  │      │              │
│  └──────┬───────┘  │      │  └────────────┘  │      └──────────────┘
│         │          │resume│  ┌────────────┐  │
│         │<─────────┼───── │  │  Resume    │  │
│         │          │      │  │  + Result  │  │
│  Agent resumes     │      │  └────────────┘  │
│  and completes     │      │                  │
│                    │      │  Retries,        │
│                    │      │  timeouts,       │
│                    │      │  observability   │
└────────────────────┘      └──────────────────┘
```

1. **Initiator** sends a task intent to the agent via AXME
2. **OpenAI Agent** processes the task using tools and LLM reasoning
3. Agent determines human approval is needed and creates an approval intent via AXME
4. **AXME** holds the intent durably -- survives agent restarts, enforces timeout
5. **Human** reviews and approves (via CLI, dashboard, or API) -- can be hours/days later
6. **AXME** resumes the agent with the approval result
7. Agent completes the task and resolves the original intent

---

## What Each Component Does

| Component | Role | Framework |
|-----------|------|-----------|
| `agent.py` | Processes tasks, requests human approval when needed | OpenAI Agents SDK |
| `initiator.py` | Sends a task into the pipeline, observes lifecycle | AXME SDK |
| `scenario.json` | Defines the agent and approval workflow | AXP Scenario |

**OpenAI Agents SDK** does the AI thinking (tool use, reasoning, guardrails).
**AXME** does the infrastructure (durable approval gates, retries, timeouts, observability).

---

## Works With

This pattern works with any OpenAI agent. AXME is framework-agnostic -- it
adds durable infrastructure to any agent regardless of framework:

- **OpenAI Agents SDK** agents
- **LangGraph** / **LangChain** agents
- **AutoGen** agents
- **CrewAI** agents
- Plain Python scripts
- Any HTTP-capable service

---

## Related

- [AXME Python SDK](https://github.com/AxmeAI/axme-sdk-python) -- `pip install axme`
- [AXME Documentation](https://github.com/AxmeAI/axme-docs)
- [AXME Examples](https://github.com/AxmeAI/axme-examples) -- more patterns (delivery, durability, human-in-the-loop)
- [AXP Intent Protocol Spec](https://github.com/AxmeAI/axp-spec)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)

---

Built with [AXME](https://github.com/AxmeAI/axme) (AXP Intent Protocol).
