"""
Agent — OpenAI Agents SDK + AXME Human Approval Bridge

Listens for task intents via AXME inbox, processes them using an OpenAI agent,
then requests human approval via AXME before completing high-risk tasks.
The approval gate is durable — humans can approve hours or days later.

Requires: AXME_API_KEY, OPENAI_API_KEY
"""

from __future__ import annotations

import json
import os
import sys
import time

from axme import AxmeClient, AxmeClientConfig
from agents import Agent, Runner, function_tool

# ---------------------------------------------------------------------------
# OpenAI Agents SDK: Tools and Agent Definition
# ---------------------------------------------------------------------------

@function_tool
def analyze_task(description: str) -> str:
    """Analyze a task and determine its risk level and required actions."""
    # In production, this would do real analysis
    risk_indicators = ["production", "deploy", "delete", "financial", "customer data", "migration"]
    description_lower = description.lower()
    risk_count = sum(1 for indicator in risk_indicators if indicator in description_lower)

    if risk_count >= 2:
        risk_level = "high"
    elif risk_count >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    return json.dumps({
        "risk_level": risk_level,
        "risk_indicators_found": risk_count,
        "requires_human_approval": risk_level in ("high", "medium"),
        "analysis": f"Task analyzed. Risk level: {risk_level}. "
                    f"Found {risk_count} risk indicators in description.",
    })


@function_tool
def prepare_execution_plan(task: str, risk_level: str) -> str:
    """Prepare a detailed execution plan for the task."""
    return json.dumps({
        "task": task,
        "risk_level": risk_level,
        "steps": [
            "Validate preconditions",
            "Create backup/snapshot",
            "Execute primary action",
            "Verify outcome",
            "Update audit log",
        ],
        "estimated_duration": "15 minutes" if risk_level == "low" else "45 minutes",
        "rollback_available": True,
    })


task_agent = Agent(
    name="Task Processor",
    instructions=(
        "You are a task processing agent. When given a task:\n"
        "1. Use analyze_task to assess the risk level\n"
        "2. Use prepare_execution_plan to create a plan\n"
        "3. Return a structured JSON result with: task, risk_level, "
        "requires_human_approval, and execution_plan"
    ),
    tools=[analyze_task, prepare_execution_plan],
    model="gpt-4o-mini",
)


# ---------------------------------------------------------------------------
# AXME: Agent Loop
# ---------------------------------------------------------------------------

AGENT_URI = "agent://task-processor"

def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    print(f"Agent (Task Processor) running as {AGENT_URI}")
    print("Polling AXME inbox for task intents...")

    while True:
        try:
            inbox = client.list_inbox(owner_agent=AGENT_URI)
            threads = inbox.get("threads", [])

            for thread in threads:
                intent_id = thread.get("intent_id")
                intent = client.get_intent(intent_id)
                payload = intent.get("payload", {})
                intent_type = intent.get("intent_type", "")

                if intent_type != "process_task":
                    continue

                if intent.get("status") != "pending_action":
                    continue

                print(f"\n--- Processing task: {intent_id} ---")
                task_description = payload.get("task", "")
                print(f"Task: {task_description}")

                # Run OpenAI agent to analyze and plan
                result = Runner.run_sync(
                    task_agent,
                    f"Analyze and prepare an execution plan for this task: {task_description}",
                )
                agent_output = result.final_output
                print(f"Agent analysis: {agent_output[:200]}...")

                # Parse agent output to determine if approval is needed
                needs_approval = "high" in agent_output.lower() or "medium" in agent_output.lower()

                if needs_approval:
                    # Request human approval via AXME — durable wait state
                    print("High/medium risk detected. Requesting human approval via AXME...")
                    client.resume_intent(
                        intent_id,
                        {
                            "status": "pending_human_approval",
                            "agent_analysis": agent_output,
                            "task": task_description,
                            "message": "Task requires human approval before execution. "
                                       "Review the analysis and approve or reject.",
                        },
                        owner_agent=AGENT_URI,
                    )
                    print(f"Intent {intent_id} waiting for human approval")
                    print("Approve via AXME CLI:")
                    print(f"  axme intent resume {intent_id} --payload '{{\"approved\": true}}'")
                else:
                    # Low risk — complete directly
                    client.resolve_intent(
                        intent_id,
                        {
                            "status": "completed",
                            "agent_analysis": agent_output,
                            "task": task_description,
                            "executed": True,
                        },
                        owner_agent=AGENT_URI,
                    )
                    print(f"Low risk task completed: {intent_id}")

        except KeyboardInterrupt:
            print("\nShutting down agent...")
            break
        except Exception as exc:
            print(f"Error processing inbox: {exc}", file=sys.stderr)

        time.sleep(3)


if __name__ == "__main__":
    main()
