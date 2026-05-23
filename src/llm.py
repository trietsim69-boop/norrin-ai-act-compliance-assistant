"""
LLM provider abstraction with mock-mode support.

Usage:
    from src.llm import call_llm

    result = call_llm(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user",   "content": "Say hi."},
        ],
        response_format="json",       # or None for plain text
        mock={"content": '{"hello": "world"}'},   # used when MOCK_LLM=true
    )
    # result is always a dict: {"content": "...", "tool_calls": None}

Providers supported:
    - "deepseek"  → DeepSeek API via OpenAI-compatible SDK
    - "openai"    → OpenAI API
    - "anthropic" → Anthropic Claude API

If MOCK_LLM=true in .env, every call returns the `mock` argument instead of
hitting any API. This lets you develop and demo the full pipeline offline.
"""

from __future__ import annotations

from typing import Any, Optional

from src.config import (
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_BASE_URL,
    OPENAI_API_KEY,
    DEEPSEEK_API_KEY,
    ANTHROPIC_API_KEY,
    MOCK_LLM,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_llm(
    messages: list[dict],
    *,
    model: Optional[str] = None,
    response_format: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    mock: Optional[dict] = None,
) -> dict:
    """
    Send a chat-completion request to the configured LLM provider.

    Args:
        messages: list of {"role": "system"|"user"|"assistant", "content": str}
        model: override the configured LLM_MODEL
        response_format: "json" to force JSON object output; None for free text
        temperature: sampling temperature (lower = more deterministic)
        max_tokens: max completion tokens
        mock: dict to return when MOCK_LLM=true. Shape: {"content": "...", "tool_calls": None}

    Returns:
        {"content": str, "tool_calls": list | None, "raw": provider_response}
    """
    if MOCK_LLM:
        return _normalise_mock(mock)

    model = model or LLM_MODEL
    provider = LLM_PROVIDER.lower()

    if provider in ("deepseek", "openai"):
        return _call_openai_compatible(
            provider=provider,
            messages=messages,
            model=model,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "anthropic":
        return _call_anthropic(
            messages=messages,
            model=model,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
            "Expected 'deepseek', 'openai', or 'anthropic'."
        )


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_openai_compatible(
    *,
    provider: str,
    messages: list[dict],
    model: str,
    response_format: Optional[str],
    temperature: float,
    max_tokens: int,
) -> dict:
    """Handles OpenAI and any OpenAI-compatible endpoint (DeepSeek, Together, etc.)."""
    from openai import OpenAI

    if provider == "deepseek":
        api_key = DEEPSEEK_API_KEY or OPENAI_API_KEY  # allow either env var
        base_url = LLM_BASE_URL or "https://api.deepseek.com"
        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set. Add it to .env or switch MOCK_LLM=true."
            )
    else:  # openai
        api_key = OPENAI_API_KEY
        base_url = LLM_BASE_URL or None
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env or switch MOCK_LLM=true."
            )

    client = OpenAI(api_key=api_key, base_url=base_url)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    completion = client.chat.completions.create(**kwargs)
    choice = completion.choices[0]
    return {
        "content": choice.message.content or "",
        "tool_calls": getattr(choice.message, "tool_calls", None),
        "raw": completion,
    }


def _call_anthropic(
    *,
    messages: list[dict],
    model: str,
    response_format: Optional[str],
    temperature: float,
    max_tokens: int,
) -> dict:
    """Handles Anthropic Claude — converts OpenAI-style messages to Anthropic format."""
    import anthropic

    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env or switch MOCK_LLM=true."
        )

    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    chat_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("user", "assistant")
    ]

    if response_format == "json":
        system_parts.append(
            "You must respond with a single valid JSON object and nothing else."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    completion = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system="\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN,
        messages=chat_messages,
    )

    text = "".join(block.text for block in completion.content if hasattr(block, "text"))
    return {
        "content": text,
        "tool_calls": None,
        "raw": completion,
    }


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _normalise_mock(mock: Optional[dict]) -> dict:
    if mock is None:
        return {
            "content": '{"_mock": "no mock fixture provided to call_llm()"}',
            "tool_calls": None,
            "raw": None,
        }
    return {
        "content": mock.get("content", ""),
        "tool_calls": mock.get("tool_calls"),
        "raw": None,
    }


def is_mock_mode() -> bool:
    return MOCK_LLM
