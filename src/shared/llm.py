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


def call_llm(prompt: str, max_tokens: int = 256, user_id: str = None, agent: str = "unknown") -> str:
    """
    Call the configured LLM and return the response text.
    
    Tracks token usage and cost in llm_usage table if user_id is provided.
    Raises an exception on failure — callers should handle with fallback.
    """
    cerebras_key = os.getenv("CEREBRAS_API_KEY", "")

    if cerebras_key:
        return _call_cerebras(prompt, cerebras_key, max_tokens, user_id, agent)
    else:
        return _call_bedrock(prompt, max_tokens, user_id, agent)


def _store_usage(user_id: str, agent: str, model: str, prompt_tokens: int,
                 completion_tokens: int, latency_ms: float, cost_usd: float) -> None:
    """Store LLM usage metrics in the database."""
    if not user_id:
        return
    try:
        from src.shared.db import get_connection, get_cursor
        conn = get_connection()
        try:
            with get_cursor(conn) as cur:
                cur.execute(
                    """
                    INSERT INTO llm_usage 
                    (user_id, agent, model, prompt_tokens, completion_tokens, 
                     total_tokens, latency_ms, estimated_cost_usd)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, agent, model, prompt_tokens, completion_tokens,
                     prompt_tokens + completion_tokens, latency_ms, cost_usd),
                )
        finally:
            conn.close()
    except Exception as e:
        _log.warning("Failed to store LLM usage: %s", e)


def _call_cerebras(prompt: str, api_key: str, max_tokens: int,
                   user_id: str = None, agent: str = "unknown") -> str:
    """Call Cerebras Cloud API (OpenAI-compatible)."""
    from cerebras.cloud.sdk import Cerebras

    client = Cerebras(api_key=api_key)
    start = time.monotonic()

    response = client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=max_tokens,
        temperature=0,
    )

    latency_ms = (time.monotonic() - start) * 1000
    _log.info("Cerebras latency: %.0fms", latency_ms)

    # Extract token usage
    usage = response.usage
    prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
    completion_tokens = getattr(usage, 'completion_tokens', 0) or 0

    # Cerebras pricing: ~$0.10 per 1M tokens (llama3.1-8b)
    cost_usd = (prompt_tokens + completion_tokens) / 1_000_000 * 0.10

    _store_usage(user_id, agent, CEREBRAS_MODEL, prompt_tokens, completion_tokens, latency_ms, cost_usd)

    return response.choices[0].message.content.strip()


def _call_bedrock(prompt: str, max_tokens: int,
                  user_id: str = None, agent: str = "unknown") -> str:
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

    # Extract token usage from Bedrock response
    usage = response.get("usage", {})
    prompt_tokens = usage.get("inputTokens", 0)
    completion_tokens = usage.get("outputTokens", 0)

    # Nova Lite pricing: $0.00006 per 1K input, $0.00024 per 1K output
    cost_usd = (prompt_tokens / 1000 * 0.00006) + (completion_tokens / 1000 * 0.00024)

    _store_usage(user_id, agent, BEDROCK_MODEL, prompt_tokens, completion_tokens, latency_ms, cost_usd)

    return (
        response.get("output", {})
        .get("message", {})
        .get("content", [{}])[0]
        .get("text", "")
        .strip()
    )
