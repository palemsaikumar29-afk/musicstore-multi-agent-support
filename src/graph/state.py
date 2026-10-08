"""LangGraph pipeline state — one TypedDict shared by the three stages.

Each node receives the full state and returns a *partial* update dict;
LangGraph merges it.
"""
from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict

from ..agents.contracts import RouteDecision


class SupportState(TypedDict, total=False):
    message: str
    clean_message: str
    lookup_email: str
    injection: bool
    injection_patterns: list[str]
    pii_kinds: list[str]
    decision: RouteDecision
    offline: bool
    clarified: bool
    answer: str
    data: Any
    escalated: bool
    # Last few conversation turns (user/intent/answer), capped at
    # HISTORY_TURNS by the nodes that append to it.
    history: list[dict]
