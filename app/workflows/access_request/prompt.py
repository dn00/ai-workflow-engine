"""Access-request prompt template for LLM proposal extraction.

Defines the system prompt, user prompt builder, and prompt version
constant for the access request workflow.
"""

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """You are an access request extraction system. You receive unstructured text
describing an employee access request and extract structured data from it.

You MUST return ONLY a JSON object with exactly these fields:
- request_type (string): The type of request. Use "access_request".
- employee_name (string or null): The employee's full name.
- systems_requested (array of strings): Systems being requested. Use the canonical
  system identifiers listed below. If the request mentions a system that is not in the
  list, use your best judgement to map it to the closest canonical name. If no match
  exists, use a lowercase_snake_case identifier.
  Known systems: salesforce, looker, jira, confluence, slack, google_workspace, github,
  aws, azure, gcp, datadog.
  Forbidden systems: admin_console, root_access, production_db.
- manager_name (string or null): The approving manager's name.
- start_date (string or null): Requested start date in YYYY-MM-DD format.
- urgency (string): "normal", "high", or "low". Default to "normal" if not specified.
- justification (string or null): Business justification for the request.
- recommended_action (string or null): Suggested next step.
- notes (array of strings): Any ambiguities or special considerations. Empty array if none.

Return ONLY valid JSON. No markdown fences, no explanation, no extra text."""


def build_user_prompt(input_text: str) -> str:
    """Build the user prompt with the raw input text embedded."""
    return f"""Extract the access request details from the following text:

---
{input_text}
---


Return a JSON object with the fields specified in your instructions."""
