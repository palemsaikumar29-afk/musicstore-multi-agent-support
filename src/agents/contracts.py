"""Typed contracts for the music-store support pipeline."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal[
    "catalog_search",
    "order_lookup",
    "policy_faq",
    "recommendation",
    "human_handoff",
    "out_of_scope",
]


class RouteDecision(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    entities: dict[str, str] = Field(default_factory=dict)
    reason: str = ""


class TrackInfo(BaseModel):
    track_id: int
    title: str
    artist: str
    album: str
    genre: str
    duration_s: int
    price: str


class OrderSummary(BaseModel):
    invoice_id: int
    date: str
    status: str
    total: str
    customer: str
    items: list[dict[str, str]] = Field(default_factory=list)


class SupportResponse(BaseModel):
    intent: Intent
    answer: str
    data: list[dict] | dict | None = None
    offline: bool = False
    escalated: bool = False
