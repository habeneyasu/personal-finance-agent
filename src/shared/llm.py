"""
Shared LLM client — Cerebras (local/demo) or AWS Bedrock (production).

Priority:
1. If CEREBRAS_API_KEY is set → use Cerebras (fast, free tier)
2. If ENVIRONMENT != local → use AWS Bedrock
3. Fallback → raise exception (caller handles with "Other" / fallback message)

Usage:
    from src.shared.llm import call_llm
    answer = call_llm(prompt="Your prompt here")
"""
import json
import logging
import os
import time
from typing import Optional

_log = logging.getLogger(__name__)

# Cerebras model — Llama 3.3 70B is fast and capable
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")

# Bedrock model fallback
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


def call_llm(prompt: str, max_tokens: int = 256) -> str:
    """
    Call the configured LLM and return the response text.

    Raises an exception on failure — callers should handle with fallback.
    """
    cerebras_key = os.getenv("CEREBRAS_API_KEY", "")

    if cerebras_key:
        return _call_cerebras(prompt, cerebras_key, max_tokens)
    else:
        return _call_bedrock(prompt, max_tokens)


def _call_cerebras(prompt: str, api_key: str, max_tokens: int) -> str:
    """Call Cerebras Cloud API (OpenAI-compatible)."""
    from cerebras.cloud.sdk import Cerebras

    client = Cerebras(api_key=api_key)
    start = time.monotonic()

    response = client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=max_tokens,
        temperature=0,  # deterministic for categorization
    )

    latency_ms = (time.monotonic() - start) * 1000
    _log.info("Cerebras latency: %.0fms", latency_ms)

    return response.choices[0].message.content.strip()


def _call_bedrock(prompt: str, max_tokens: int) -> str:
    """Call AWS Bedrock (production path)."""
    import boto3

    client = boto3.client("bedrock-runtime")
    start = time.monotonic()

    response = client.converse(
        modelId=BEDROCK_MODEL,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )

    latency_ms = (time.monotonic() - start) * 1000
    _log.info("Bedrock latency: %.0fms", latency_ms)

    return (
        response.get("output", {})
        .get("message", {})
        .get("content", [{}])[0]
        .get("text", "")
        .strip()
    )
