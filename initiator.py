"""
Initiator — Sends a task through the OpenAI agent + AXME approval pipeline.

Sends a process_task intent to the agent, then observes the full lifecycle
including the human approval gate.

Requires: AXME_API_KEY
"""

from __future__ import annotations

import json
import os
import sys

from axme import AxmeClient, AxmeClientConfig


def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    task = "Deploy ML model v2.3 to production and migrate customer data to new schema"

    print(f"Sending task to agent: {task}")
    intent_id = client.send_intent({
        "intent_type": "process_task",
        "to_agent": "agent://task-processor",
        "payload": {
            "task": task,
            "priority": "high",
            "requestor": "engineering-team",
        },
    })
    print(f"Intent created: {intent_id}")
    print("Observing lifecycle events...\n")

    for event in client.observe(intent_id):
        event_type = event.get("event_type", "unknown")
        data = event.get("data", {})
        print(f"  [{event_type}] {json.dumps(data, indent=2)[:200]}")

        if event_type in ("intent.completed", "intent.failed", "intent.cancelled"):
            break

        if data.get("status") == "pending_human_approval":
            print("\n  >>> Human approval required. Approve via AXME CLI:")
            print(f"  >>> axme intent resume {intent_id} --payload '{{\"approved\": true}}'")
            print()

    # Fetch final state
    final = client.get_intent(intent_id)
    print(f"\nFinal status: {final.get('status')}")
    print(f"Result: {json.dumps(final.get('result', {}), indent=2)}")


if __name__ == "__main__":
    main()
