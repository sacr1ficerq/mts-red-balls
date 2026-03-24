import json
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def repair_json(json_str: str) -> str:
    """Attempt to repair common JSON errors from LLM output."""
    # Fix missing colon between key and value (e.g., "query{"action" -> "query":{"action")
    repaired = re.sub(r'"(\w+)"\s*\{', r'"\1":{', json_str)
    # Fix missing colon before string value (e.g., "query"python" -> "query":"python")
    repaired = re.sub(r'"(\w+)"\s*"([^"]*)"', r'"\1":"\2"', repaired)
    # Fix missing comma between key-value pairs
    repaired = re.sub(r'"\s*"', ',"', repaired)
    # Fix missing quotes around values
    repaired = re.sub(
        r":\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*([,}])", r':"\1"\2', repaired
    )
    return repaired

def extract_json_objects(text: str) -> list:
    """Extract JSON objects from text using a stack-based approach."""
    objects = []
    stack = []
    start_index = -1

    for i, char in enumerate(text):
        if char == "{":
            if not stack:
                start_index = i
            stack.append(char)
        elif char == "}":
            if stack:
                stack.pop()
                if not stack:
                    json_str = text[start_index : i + 1]
                    try:
                        obj = json.loads(json_str)
                        objects.append(obj)
                    except json.JSONDecodeError:
                        # Try to repair the JSON
                        try:
                            repaired = repair_json(json_str)
                            obj = json.loads(repaired)
                            logger.warning(
                                f"Repaired malformed JSON: {json_str[:100]}..."
                            )
                            objects.append(obj)
                        except json.JSONDecodeError as e:
                            logger.debug(f"Failed to repair JSON: {e}")
    return objects

def parse_json_output(text: str) -> Dict[str, Any]:
    """Parse JSON from LLM output, handling extra text"""
    if not text:
        return {}

    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try stack-based extraction
    json_objects = extract_json_objects(text)
    if json_objects:
        return json_objects[0]

    # Try regex for markdown code blocks
    code_blocks = re.findall(
        r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL
    )
    for block in code_blocks:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            try:
                return json.loads(repair_json(block))
            except json.JSONDecodeError:
                pass

    logger.warning(f"Failed to parse JSON from text: {text[:100]}...")
    return {}
