"""OpenAI-compatible client. Groq, OpenRouter, Ollama, vLLM — all speak this.

Provider is a config value, never a code dependency. No OpenAI, no Anthropic:
open-weight models only.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
# Measured over 12 hand-verified cases against five open-weight models:
# 12/12 in 54s with zero rejected findings, cheaper and faster than the
# alternatives, and Apache 2.0 rather than a vendor licence.
MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3-235b-a22b-2507")
API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY", "")
JSON_OBJECT_ONLY = os.environ.get("LLM_JSON_OBJECT_ONLY", "1") == "1"


def chat(messages: list[dict], schema: dict | None = None, tools: list[dict] | None = None,
         temperature: float = 0.0, max_tokens: int = 4000,
         model: str | None = None) -> dict:
    """One call. Returns the raw message dict so callers can read tool_calls.

    `model` overrides the env default per call. Without it the model is process
    global, so two models cannot run concurrently without racing on it — which
    is what stopped a five-model comparison from running in parallel.
    """
    body = {"model": model or MODEL, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens}
    if schema:
        # Constrained decoding, not "please reply in JSON" in the prompt.
        # ponytail: not every open model supports json_schema; json_object is the floor.
        body["response_format"] = ({"type": "json_object"} if JSON_OBJECT_ONLY else
                                   {"type": "json_schema",
                                    "json_schema": {"name": "out", "strict": True,
                                                    "schema": schema}})
    if tools:
        body["tools"] = tools

    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json",
                 # urllib's default UA gets 403'd by Cloudflare in front of Groq.
                 "User-Agent": "claimcheck/0.1"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                out = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:500]
            # Free tiers meter per minute; the wait is short and the run is long.
            if e.code == 429 and attempt < 3:
                m = re.search(r"try again in ([\d.]+)s", detail)
                time.sleep(float(m.group(1)) + 1 if m else 20)
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["choices"][0]["message"]


def json_call(messages: list[dict], schema: dict, retries: int = 1) -> dict:
    """Schema-constrained call with one retry. Open models drift on long output."""
    messages = [{"role": "system",
                 "content": "Reply with a single JSON object matching this schema:\n"
                            + json.dumps(schema)}] + messages
    for attempt in range(retries + 1):
        msg = chat(messages, schema=schema)
        try:
            return json.loads(_strip(msg["content"]))
        except (json.JSONDecodeError, TypeError, AttributeError):
            if attempt == retries:
                raise
            messages = messages + [{"role": "user", "content": "Invalid JSON. Return only valid JSON matching the schema."}]
    raise RuntimeError("unreachable")


def _strip(content: str) -> str:
    """Reasoning models emit <think> blocks and fenced code around the JSON."""
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    start, end = content.find("{"), content.rfind("}")
    return content[start:end + 1] if start >= 0 else content
