"""Anthropic client + the shared agent runner.

Every "agent" in this system is a focused Claude call. Two helpers cover all of
them:

  * ``parse_structured`` — one-shot call that returns a validated Pydantic object
    (classification, field extraction, filling).
  * ``run_with_tools``   — short agentic loop for the one agent that needs to
    read the live web (the Extractor, via Claude's server-side web_fetch).
"""

from __future__ import annotations

from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel

# Default to the latest, most capable Claude model. See the claude-api skill.
MODEL = "claude-opus-4-8"

T = TypeVar("T", bound=BaseModel)

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    """Lazily construct a client so importing the package never requires a key."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the env
    return _client


def parse_structured(system: str, user: str, schema: Type[T], max_tokens: int = 4000) -> T:
    """Return a validated instance of ``schema`` produced by Claude."""
    resp = get_client().messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if resp.parsed_output is None:
        raise RuntimeError(f"Model did not return parseable output (stop_reason={resp.stop_reason})")
    return resp.parsed_output


# Claude's server-side web tools. web_fetch reads a specific URL; web_search is a
# fallback when the email only gives a camp name, not a direct link.
WEB_TOOLS = [
    {"type": "web_fetch_20260209", "name": "web_fetch"},
    {"type": "web_search_20260209", "name": "web_search"},
]


def run_with_tools(system: str, user: str, tools=WEB_TOOLS, max_continuations: int = 6) -> str:
    """Run a tool-using agent loop and return its final text.

    Server-side tools run on Anthropic's infra, so we don't execute anything
    locally — we just re-send on ``pause_turn`` until the model is done. Thinking
    blocks are preserved by appending the full ``content`` each turn.
    """
    client = get_client()
    messages = [{"role": "user", "content": user}]
    resp = None
    for _ in range(max_continuations):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=system,
            thinking={"type": "adaptive"},
            tools=tools,
            messages=messages,
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    return _text_of(resp)


def _text_of(resp) -> str:
    if resp is None:
        return ""
    return "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
