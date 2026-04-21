"""Lightweight text/JSON parsing helpers used across the graph package.

No `app.*` imports. Uses the standard-library ``re`` module (we used to depend
on the third-party ``regex`` package for recursive ``(?R)`` patterns; recursive
fallbacks here are linear-time best-effort).
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import deque
from typing import Any


# ---------------------------------------------------------------------------
# Native JSON extraction
# ---------------------------------------------------------------------------


def _extract_native_json(raw_text: str) -> Any:
    """Find a top-level JSON object or array in ``raw_text``."""
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)

    # Try whole text first
    cleaned = raw_text.strip()
    if cleaned.startswith(("{", "[")):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Greedy regex (linear): find first {...} or [...]
    match = re.search(r"(\{.*\}|\[.*\])", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def extract_array(text: Any) -> Any:
    """Extract a JSON array from a markdown code block or fall back to native parse."""
    if not isinstance(text, str):
        text = str(text)
    fenced = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            try:
                cleaned = fenced.group(1).replace("'", '"').replace('\\"', '"').lstrip("\ufeff")
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return _extract_native_json(text)
    return _extract_native_json(text)


def find_first_json(text: Any) -> Any:
    """Find the first JSON object/array in a code block or standalone."""
    if not isinstance(text, str):
        text = str(text)

    # Code block first
    block = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.DOTALL)
    if block:
        try:
            return json.loads(block.group(1).strip())
        except json.JSONDecodeError:
            pass

    return _extract_native_json(text)


def find_json_block(raw_text: Any) -> Any:
    """Best-effort JSON extraction across multiple formats."""
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)
    raw_text = "\n".join(line for line in raw_text.strip().split("\n"))

    start_token = "```json"
    end_token = "```"
    start_index = raw_text.find(start_token)
    if start_index != -1:
        end_index = raw_text.find(end_token, start_index + len(start_token))
        if end_index != -1:
            json_str = raw_text[start_index + len(start_token) : end_index].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                try:
                    if json_str.startswith("\ufeff"):
                        json_str = json_str[1:]
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

    # Look for any {...} or [...] pattern
    matches = re.findall(r"(\{.*?\}|\[.*?\])", raw_text, re.DOTALL)
    for match in matches:
        try:
            cleaned = match.replace("'", '"')
            cleaned = re.sub(r"//.*?(?=\n|\r|$)", "", cleaned)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            continue

    return find_first_json(raw_text)


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


def json_parse_with_quotes(value: str) -> Any:
    json_value = value.replace("'", '"').replace("\\", "\\\\")
    return json.loads(json_value)


def parse_metadata_value(value: Any) -> Any:
    """Parse metadata value into a dict using multiple safe strategies."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    for parser in (ast.literal_eval, json_parse_with_quotes):
        try:
            result = parser(value)
            if isinstance(result, dict):
                return result
        except Exception:  # noqa: BLE001
            continue
    return None


def filter_metadata_fields(metadata: dict, fields: list[str]) -> dict:
    """Filter metadata to only include specified fields."""
    if not fields:
        return metadata or {}
    if not metadata:
        return {}

    filtered: dict = {}
    for key, value in metadata.items():
        try:
            metadata_dict = parse_metadata_value(value)
            if not metadata_dict:
                continue
            keep = {field: metadata_dict[field] for field in fields if field in metadata_dict}
            if keep:
                filtered[key] = str(keep)
        except Exception:  # noqa: BLE001
            continue
    return filtered


# ---------------------------------------------------------------------------
# Entity-string parsing
# ---------------------------------------------------------------------------


def extract_entity_properties(entity_str: str) -> str | None:
    """Extract properties from EntityNode string representation."""
    if not entity_str or not isinstance(entity_str, str):
        return None
    entity_str = entity_str.strip()
    if entity_str == "()":
        return ""
    pattern = r"\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$"
    match = re.search(pattern, entity_str)
    if match:
        content = match.group(1).strip()
        return content if content else ""
    return None


def extract_entity_name(entity_str: str) -> str | None:
    """Extract entity name from EntityNode string representation."""
    if not isinstance(entity_str, str):
        return None
    if not entity_str:
        return ""
    entity_str = entity_str.strip()
    if entity_str.startswith("(") and entity_str.endswith(")") and entity_str.count("(") == 1:
        return ""
    pattern = r"^(.*?)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$"
    match = re.search(pattern, entity_str)
    if match:
        return match.group(1).strip()
    return entity_str


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class CircularMessageBuffer:
    """Simple circular buffer for deduplication of recent messages."""

    def __init__(self, maxlen: int = 5) -> None:
        self.buffer: deque = deque(maxlen=maxlen)

    def _hash_message(self, session_id: str, role: str, content: str) -> str:
        normalized = " ".join(str(content).strip().lower().split())
        message = f"{session_id}:{role}:{normalized}"
        return hashlib.md5(message.encode()).hexdigest()

    def add(self, session_id: str, role: str, content: str) -> bool:
        msg_hash = self._hash_message(session_id, role, content)
        if any(getattr(msg, "hash", None) == msg_hash for msg in self.buffer):
            return True
        return False

    def get_size(self) -> int:
        return len(self.buffer)

    def reset(self) -> None:
        self.buffer.clear()
