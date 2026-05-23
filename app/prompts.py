"""
prompts.py — Prompt templates for extraction and JSON repair.

Prompts are engineered to:
  - Force JSON-only output
  - Prevent hallucinations
  - Require null for unknown values
  - Enforce deterministic extraction
"""

# ---------------------------------------------------------------------------
# System prompt for the extraction agent
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM_PROMPT = """\
You are a precise data extraction engine.

RULES — follow all of them without exception:
1. Return ONLY valid JSON that conforms exactly to the provided schema.
2. Never include explanations, markdown code fences, or any text outside the JSON.
3. Never fabricate information that is not present in the input text.
4. If a field's value cannot be determined from the input, set it to null.
5. Do not guess, infer beyond what is explicitly stated, or fill in plausible values.
6. All string values must be concise and factual.
7. Monetary amounts must be numeric floats (e.g. 49.99), never strings.
8. confidence_score must reflect how clearly the source text supported your extraction.

Your output will be parsed by a machine. Any deviation will cause a failure.
"""


def build_extraction_prompt(raw_text: str) -> str:
    """
    Build the user message for a customer support ticket extraction.

    Args:
        raw_text: The raw, unstructured text to extract from.

    Returns:
        Formatted user prompt string.
    """
    return f"""\
Extract structured information from the following text into the CustomerSupportTicket schema.

TEXT TO EXTRACT FROM:
\"\"\"
{raw_text.strip()}
\"\"\"

Return ONLY the JSON object. No explanations. No markdown. No code fences.
Unknown fields must be null.
"""


# ---------------------------------------------------------------------------
# Repair prompt — sent when the first response was malformed JSON
# ---------------------------------------------------------------------------
REPAIR_SYSTEM_PROMPT = """\
You are a JSON repair engine.

RULES:
1. Return ONLY corrected, valid JSON.
2. Do not add explanations or commentary.
3. Do not add new fields that were not in the original JSON.
4. Preserve all original values; only fix syntax errors.
5. Output must be parseable by Python's json.loads().
"""


def build_repair_prompt(malformed_json: str) -> str:
    """
    Build a prompt that asks the model to fix broken JSON.

    Args:
        malformed_json: The invalid JSON string returned by a prior call.

    Returns:
        Formatted repair prompt string.
    """
    return f"""\
The following JSON is invalid or malformed. Fix all syntax errors.

MALFORMED JSON:
\"\"\"
{malformed_json.strip()}
\"\"\"

Return ONLY the corrected JSON object. Nothing else.
"""
