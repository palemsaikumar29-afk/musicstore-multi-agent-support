"""LangGraph pipeline: intake -> route -> specialist (terminal)."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from ..agents.contracts import RouteDecision
from ..agents.nodes import intake_node, route_node, specialist_node
from ..database.db import ensure_seeded
from .state import SupportState


def _route_after_intake(state: dict) -> str:
    return "route"


def _route_after_routing(state: dict) -> str:
    return "specialist"


def build_pipeline():
    g = StateGraph(SupportState)
    g.add_node("intake", intake_node)
    g.add_node("route", route_node)
    g.add_node("specialist", specialist_node)
    g.set_entry_point("intake")
    g.add_conditional_edges("intake", _route_after_intake, {"route": "route"})
    g.add_conditional_edges("route", _route_after_routing,
                            {"specialist": "specialist"})
    g.add_edge("specialist", END)
    return g.compile()


def handle_message(message: str) -> dict[str, Any]:
    """Run one support turn; returns the final state dict."""
    ensure_seeded()
    app = build_pipeline()
    result = app.invoke({"message": message})
    decision: RouteDecision = result.get("decision")
    return {
        "answer": result.get("answer", ""),
        "intent": decision.intent if decision else "unknown",
        "confidence": decision.confidence if decision else 0.0,
        "offline": result.get("offline", True),
        "escalated": result.get("escalated", False),
        "injection": result.get("injection", False),
        "pii_kinds": result.get("pii_kinds", []),
        "data": result.get("data"),
    }
