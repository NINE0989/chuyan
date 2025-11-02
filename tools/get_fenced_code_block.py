"""Small helper: extract the first fenced GLSL code block from LLM output."""
import re


def extract_fenced(output: str) -> str | None:
    """Return inner text of the first ```glsl ... ``` (case-insensitive).
    Returns None if not found.
    """
    m = re.search(r'(?is)```\s*(?:glsl)?\s*\n?(.*?)\n?```', output)
    return m.group(1).strip() if m else None