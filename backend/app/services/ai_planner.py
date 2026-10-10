
import json
import os

from dotenv import load_dotenv
from google import genai

from app.schemas.workflow import WorkflowCreate

load_dotenv()

SYSTEM_PROMPT = """
You are Nexora's workflow planner.

Convert the user's business automation request into a JSON workflow.

Return exactly these fields:
{
  "name": "Workflow name",
  "description": "Workflow description",
  "nodes": [
    {
      "id": "unique_node_key",
      "type": "trigger",
      "name": "Readable node name",
      "config": {},
      "retry_count": 0
    }
  ],
  "edges": [
    {
      "source": "source_node_key",
      "target": "target_node_key",
      "condition": null
    }
  ]
}

Allowed node types: trigger, ai, action, condition.

Rules:
- Use unique node IDs.
- Every edge must reference existing nodes.
- Create a directed acyclic graph.
- Start with a trigger.
- Use AI nodes for classification or scoring.
- Use condition nodes for decisions.
- Store condition field, operator, and value in config.
- Do not invent unsupported integrations.
- Generate a plan only; do not claim actions were executed.
- Return JSON only, without Markdown.
"""


def plan_workflow(user_request: str) -> WorkflowCreate:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=(
            SYSTEM_PROMPT
            + "\n\nUser's automation request:\n"
            + user_request
            + "\n\nReturn a valid workflow JSON object."
        ),
        config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response")

    workflow_json = json.loads(response.text)

    # Validate the generated data structure.
    workflow = WorkflowCreate.model_validate(workflow_json)

    # Validate graph rules such as node IDs and edge references.
    from app.services.workflow_validator import validate_workflow

    validate_workflow(workflow)

    return workflow
