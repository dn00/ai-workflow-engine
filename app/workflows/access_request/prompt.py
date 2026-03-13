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
- systems_requested (array of strings or null): Systems being requested.
- manager_name (string or null): The approving manager's name.
- start_date (string or null): Requested start date in YYYY-MM-DD format.
- urgency (string or null): "normal", "high", or "low".
- justification (string or null): Business justification for the request.
- recommended_action (string or null): Suggested next step.
- notes (array of strings or null): Any ambiguities or special considerations.

Return ONLY valid JSON. No markdown fences, no explanation, no extra text."""


def build_user_prompt(input_text: str) -> str:
    """Build the user prompt with the raw input text embedded."""
    return f"""Extract the access request details from the following text:

---
{input_text}
---

Return a JSON object with the fields specified in your instructions."""
