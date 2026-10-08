"""LangGraph pipeline: intake -> route -> clarify | specialist (terminal)."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from ..agents.contracts import RouteDecision
from ..agents.nodes import (
    clarify_node,
    intake_node,
    needs_clarification,
    route_node,
    specialist_node,
)
from ..database.db import ensure_seeded
from .state import SupportState


def _route_after_intake(state: dict) -> str:
    return "route"


def _route_after_routing(state: dict) -> str:
    decision: RouteDecision | None = state.get("decision")
    if decision is not None and needs_clarification(
            decision, state.get("injection", False)):
        return "clarify"
    return "specialist"


def build_pipeline():
    g = StateGraph(SupportState)
    g.add_node("intake", intake_node)
    g.add_node("route", route_node)
    g.add_node("clarify", clarify_node)
    g.add_node("specialist", specialist_node)
    g.set_entry_point("intake")
    g.add_conditional_edges("intake", _route_after_intake, {"route": "route"})
    g.add_conditional_edges("route", _route_after_routing,
                            {"clarify": "clarify",
                             "specialist": "specialist"})
    g.add_edge("clarify", END)
    g.add_edge("specialist", END)
    return g.compile()


def handle_message(message: str,
                   history: list[dict] | None = None) -> dict[str, Any]:
    """Run one support turn; returns the final state dict.

    Pass the prior turns as ``history`` (list of {"user","intent",...}
    dicts) to give the router conversation context; the returned dict
    includes the updated ``history`` with this turn appended.
    """
    ensure_seeded()
    app = build_pipeline()
    result = app.invoke({"message": message, "history": list(history or [])})
    decision: RouteDecision = result.get("decision")
    return {
        "answer": result.get("answer", ""),
        "intent": decision.intent if decision else "unknown",
        "confidence": decision.confidence if decision else 0.0,
        "offline": result.get("offline", True),
        "escalated": result.get("escalated", False),
        "clarified": result.get("clarified", False),
        "injection": result.get("injection", False),
        "pii_kinds": result.get("pii_kinds", []),
        "data": result.get("data"),
        "history": result.get("history", []),
    }
