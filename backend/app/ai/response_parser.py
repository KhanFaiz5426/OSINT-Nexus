"""Shared LLM response parser — extracts JSON from messy model outputs.

Handles:
- Nemotron: outputs thinking as plain text, then JSON in code block
- Claude: <think>...</think> blocks
- OpenAI: clean JSON or markdown-wrapped
- Generic: JSON embedded in text

Security: All output is untrusted. Caller must validate.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def extract_json_from_llm_response(response_text: str) -> dict | None:
    """Extract the last valid JSON object from an LLM response.

    LLMs (especially Nemotron) often output their thinking process as plain
    text, then produce the actual JSON response at the end, sometimes wrapped
    in markdown code fences. This function finds and extracts that JSON.

    Strategy:
    1. Strip known thinking block formats (<think>, <thinking>, [thinking])
    2. Try to find the LAST ```json ... ``` code block
    3. Try to find the LAST ``` ... ``` code block
    4. Try to find the last complete {...} JSON object
    5. Validate it parses as JSON

    Args:
        response_text: Raw LLM response text.

    Returns:
        Parsed dict if valid JSON found, else None.
    """
    if not response_text or not response_text.strip():
        return None

    text = response_text.strip()

    # ── Step 1: Strip known thinking block formats ───────────────────────
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"\[thinking\].*?\[/thinking\]", "", text, flags=re.DOTALL).strip()

    # ── Step 2: Try to find the LAST ```json ... ``` code block ──────────
    # Nemotron puts JSON in the last code block after its thinking
    code_block_pattern = re.compile(r"```(?:json)?\s*\n(.*?)\n\s*```", re.DOTALL)
    matches = list(code_block_pattern.finditer(text))
    if matches:
        # Try each code block from LAST to first (last is usually the actual output)
        for match in reversed(matches):
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    # ── Step 3: Try to find the last complete {...} JSON object ──────────
    # Find all potential JSON objects by matching braces
    # Start from the end of the text (actual output is usually last)
    last_brace = text.rfind("}")
    if last_brace != -1:
        # Walk backwards to find the matching opening brace
        depth = 0
        for i in range(last_brace, -1, -1):
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                depth -= 1
            if depth == 0:
                candidate = text[i : last_brace + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

    # ── Step 4: Try the whole text as JSON ───────────────────────────────
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    logger.warning("No valid JSON found in LLM response (%d chars)", len(response_text))
    logger.debug("Response preview: %s", response_text[:500])
    return None


def clean_llm_json(data: dict) -> dict:
    """Clean LLM JSON output to fix common issues.

    - Convert null strings to empty strings for fields that expect str
    - Strip whitespace from string values
    - Remove None values from lists
    """
    if not isinstance(data, dict):
        return data

    cleaned = {}
    for key, value in data.items():
        if value is None:
            cleaned[key] = value
        elif isinstance(value, str):
            cleaned[key] = value.strip()
        elif isinstance(value, dict):
            cleaned[key] = clean_llm_json(value)
        elif isinstance(value, list):
            cleaned[key] = [
                clean_llm_json(item) if isinstance(item, dict) else item
                for item in value
                if item is not None
            ]
        else:
            cleaned[key] = value

    return cleaned
