"""Shared JSON extraction utilities for LLM output parsing."""

from __future__ import annotations

import json
import re


def extract_json(
    text: str,
    *,
    strict_keys: bool = False,
    min_keys: int = 0,
) -> dict | None:
    """Extract a JSON object from LLM output text.

    Tries multiple strategies in order:
    1. Direct JSON parse of the full text
    2. Fenced code block (```json ... ```)
    3. First balanced { ... } block

    Args:
        text: Raw LLM output.
        strict_keys: If True, strategy 3 only accepts objects containing
            "findings" or "agent_id" keys.
        min_keys: If > 0, strategy 3 only accepts objects with at least
            this many keys.  Ignored when *strict_keys* is True.

    Returns:
        Parsed dict or None if extraction fails.
    """
    if not text or len(text.strip()) < 2:
        return None

    # Strategy 1: whole text
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: fenced code block
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    for block in blocks:
        try:
            result = json.loads(block)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 3: first balanced { ... }
    # Track whether we are inside a JSON string to avoid counting
    # escaped braces (e.g., "{" or "}") as structural delimiters.
    brace_depth = 0
    start = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(text):
        if escape_next:
            # Previous char was a backslash inside a string; skip this char
            escape_next = False
            continue
        if in_string:
            if ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue
        # Not inside a string
        if ch == '"':
            in_string = True
        elif ch == "{":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                candidate = text[start : i + 1]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        if strict_keys:
                            if "findings" in result or "agent_id" in result:
                                return result
                        elif min_keys > 0:
                            if len(result) >= min_keys:
                                return result
                        else:
                            return result
                except json.JSONDecodeError:
                    start = -1

    return None
