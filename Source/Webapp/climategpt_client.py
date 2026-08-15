"""
Minimal ClimateGPT client wrapper used by `pipeline_app.py`.

This client is intentionally small: it reads configuration from environment
variables and exposes `call_decision_model(prompt, available_tools)` which
returns the parsed JSON object emitted by the decision model.

Configuration via env:
- DECISION_MODEL_URL: endpoint URL
- DECISION_MODEL_USER / DECISION_MODEL_PASS: basic auth credentials (optional)
- DECISION_MODEL_TIMEOUT: request timeout seconds (default 20)

The decision model is expected to return a short English sentence followed
by a JSON object. This client extracts the JSON object and returns it as
Python dict. If extraction or parsing fails it raises ValueError or
requests.RequestException for transport errors.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List
import requests
import re

DECISION_MODEL_URL = os.environ.get(
    "DECISION_MODEL_URL",
    "https://erasmus.ai/models/climategpt_8b_test/v1/chat/completions",
)
DECISION_MODEL_USER = os.environ.get("DECISION_MODEL_USER")
DECISION_MODEL_PASS = os.environ.get("DECISION_MODEL_PASS")
# Optional API key / bearer token support
DECISION_MODEL_API_KEY = os.environ.get("DECISION_MODEL_API_KEY")
DECISION_MODEL_TIMEOUT = int(os.environ.get("DECISION_MODEL_TIMEOUT", "20"))


def call_decision_model(prompt: str, available_tools: List[str]) -> Dict[str, Any]:
    """Call the configured ClimateGPT decision model and return parsed JSON.

    The model should return one short English sentence (optional) followed by
    a JSON object. This function extracts the JSON object and returns it.
    """
    if not DECISION_MODEL_URL:
        raise ValueError("DECISION_MODEL_URL not configured")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a tool-routing assistant. First produce a single short English sentence "
                "explaining your choice, then on a new line output a JSON object EXACTLY in this shape:\n"
                '{"tool": "<tool_name>", "arguments": { ... }}\n'
                "Return only that one sentence and the JSON (no extra text)."
            ),
        },
        {
            "role": "user",
            "content": f"User prompt: {prompt}\n\nAvailable tools: {', '.join(available_tools)}",
        },
    ]

    payload = {"model": "/cache/climategpt_8b_test", "messages": messages}

    headers = {"Content-Type": "application/json"}
    auth = None
    if DECISION_MODEL_API_KEY:
        # Prefer API key / Bearer token when provided
        headers["Authorization"] = f"Bearer {DECISION_MODEL_API_KEY}"
    elif DECISION_MODEL_USER and DECISION_MODEL_PASS:
        auth = (DECISION_MODEL_USER, DECISION_MODEL_PASS)

    resp = requests.post(
        DECISION_MODEL_URL,
        json=payload,
        headers=headers,
        auth=auth,
        timeout=DECISION_MODEL_TIMEOUT,
    )
    resp.raise_for_status()

    try:
        j = resp.json()
        content = j.get("choices", [])[0].get("message", {}).get("content")
    except Exception:
        content = resp.text

    if not content:
        raise ValueError("Decision model returned empty response")

    # Find JSON object in the returned content
    m = re.search(r"(\{[\s\S]*\})", content)
    if not m:
        raise ValueError("Decision model did not return a JSON object in its assistant content")

    import json as _json

    try:
        return _json.loads(m.group(1))
    except Exception as e:
        raise ValueError(f"Failed to parse JSON from decision model content: {e}")



