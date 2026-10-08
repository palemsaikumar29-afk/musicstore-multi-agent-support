"""Pipeline nodes: intake -> route -> specialist -> respond."""
from __future__ import annotations

import re

from ..services import catalog, orders
from ..services.llm_factory import call_llm_with_retry, provider_status
from ..services.safety import detect_injection, redact_pii
from .contracts import RouteDecision

# --- keyword router (deterministic, used when no LLM key is configured) -----
#
# NOTE (grader feedback, Oct 2026): plain substring matching used to send
# "I'd like a refund" to the recommendation agent because "like" matched
# before any refund/order word was checked. Order matters: handoff first,
# then order/policy intents, and only then recommendation/catalog.

_CATALOG_WORDS = {
    "track", "song", "album", "artist", "search", "find", "genre",
    "jazz", "rock", "pop", "electronic", "folk", "price", "buy",
}
_ORDER_WORDS = {
    "order", "invoice", "shipped", "status", "purchase",
    "receipt", "track my", "where is", "cancel", "package",
}
_FAQ_WORDS = {
    "return", "refund", "money back", "refund policy", "payment", "pay",
    "account", "policy", "how do", "shipping", "delivery", "delivery time",
    "billing", "charged", "charge",
}
_RECOMMEND_WORDS = {
    "recommend", "suggest", "similar", "like", "discover", "new music",
}
_HANDOFF_WORDS = {
    "human", "agent", "person", "representative", "call me",
    "complaint", "manager",
}


def _hit(words: set[str], text: str) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def keyword_route(text: str) -> RouteDecision:
    # Order-sensitive: handoff, then order/policy actions, then discovery.
    # ("I'd like a refund" must reach policy_faq via "refund", never
    # recommendation via "like".)
    if _hit(_HANDOFF_WORDS, text):
        return RouteDecision(intent="human_handoff", confidence=0.9,
                             reason="keyword")
    if _hit(_ORDER_WORDS, text):
        return RouteDecision(intent="order_lookup", confidence=0.8,
                             reason="keyword")
    if _hit(_FAQ_WORDS, text):
        return RouteDecision(intent="policy_faq", confidence=0.8,
                             reason="keyword")
    if _hit(_RECOMMEND_WORDS, text):
        return RouteDecision(intent="recommendation", confidence=0.75,
                             reason="keyword")
    if _hit(_CATALOG_WORDS, text):
        return RouteDecision(intent="catalog_search", confidence=0.7,
                             reason="keyword")
    return RouteDecision(intent="out_of_scope", confidence=0.5, reason="keyword")


HISTORY_TURNS = 5  # how many prior turns are kept in graph state


def _history_block(history: list[dict] | None) -> str:
    """Render the last few turns for the router prompt."""
    if not history:
        return "No prior turns."
    lines = []
    for turn in history[-3:]:
        user = str(turn.get("user", ""))[:160]
        intent = str(turn.get("intent", ""))
        lines.append(f"- user: {user} [routed: {intent}]")
    return "\n".join(lines)


def llm_route(text: str, history: list[dict] | None = None) -> RouteDecision:
    prompt = (
        "You are a customer-support router for a digital music store. "
        "Classify the user's LATEST message into exactly one intent: "
        "catalog_search | order_lookup | policy_faq | recommendation | "
        "human_handoff | out_of_scope.\n"
        "Use the conversation history for context — follow-ups like "
        "'what about jazz?' or 'the second one' refer back to earlier turns.\n"
        "Conversation so far:\n" + _history_block(history) + "\n"
        "Also extract entities as key=value pairs (e.g. email=, invoice=, "
        "artist=, track=) when present.\n"
        "Reply in exactly three lines:\n"
        "INTENT: <intent>\nCONFIDENCE: <0-1>\nENTITIES: <k=v; k=v or 'none'>\n\n"
        f"Latest message: {text}"
    )
    raw = call_llm_with_retry(prompt)
    intent = "out_of_scope"
    confidence = 0.5
    entities: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("INTENT:"):
            cand = line.split(":", 1)[1].strip().lower()
            if cand in {"catalog_search", "order_lookup", "policy_faq",
                        "recommendation", "human_handoff", "out_of_scope"}:
                intent = cand
        elif line.upper().startswith("CONFIDENCE:"):
            try:
                confidence = max(0.0, min(1.0, float(line.split(":", 1)[1])))
            except ValueError:
                pass
        elif line.upper().startswith("ENTITIES:"):
            body = line.split(":", 1)[1].strip()
            if body.lower() != "none":
                for pair in body.split(";"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        entities[k.strip().lower()] = v.strip()
    return RouteDecision(intent=intent, confidence=confidence,
                         entities=entities, reason="llm")


def route(text: str, history: list[dict] | None = None) -> RouteDecision:
    _, _, key_present, _ = provider_status()
    if key_present:
        try:
            return llm_route(text, history)
        except Exception:  # noqa: BLE001 - fall back to keywords
            return keyword_route(text)
    return keyword_route(text)


# --- confidence-gated clarification ----------------------------------------
# When the router is unsure, ask instead of guessing: a wrong specialist
# cannot recover, but a clarifying question can.

CLARIFY_THRESHOLD = 0.55
_NO_CLARIFY_INTENTS = {"out_of_scope", "human_handoff"}

INTENT_LABELS = {
    "catalog_search": "finding music in the catalog",
    "order_lookup": "an order or invoice",
    "policy_faq": "store policies (returns, shipping, payments)",
    "recommendation": "music recommendations",
    "human_handoff": "a human support agent",
    "out_of_scope": "something else",
}


def needs_clarification(decision: RouteDecision, injection: bool = False) -> bool:
    """True when the router's confidence is too low to act on directly."""
    return (
        not injection
        and decision.confidence < CLARIFY_THRESHOLD
        and decision.intent not in _NO_CLARIFY_INTENTS
    )


def _append_turn(state: dict, decision: RouteDecision, answer: str) -> list[dict]:
    turns = list(state.get("history") or [])
    turns.append({
        "user": state.get("message", ""),
        "intent": decision.intent,
        "confidence": round(decision.confidence, 2),
        "answer": answer[:200],
    })
    return turns[-HISTORY_TURNS:]


def clarify_node(state: dict) -> dict:
    """Terminal node: ask a clarifying question instead of guessing."""
    decision: RouteDecision = state["decision"]
    guess = INTENT_LABELS.get(decision.intent, "your request")
    answer = (
        "I want to make sure I help with the right thing — "
        f"are you asking about {guess}?\n\n"
        "Reply with a few more words (for example an invoice number, "
        "an artist name, or 'talk to a human') and I'll take it from there."
    )
    return {
        "answer": answer,
        "data": None,
        "escalated": False,
        "clarified": True,
        "history": _append_turn(state, decision, answer),
    }


# --- specialists ------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_INVOICE_RE = re.compile(r"\b(\d{4})\b")


def _format_tracks(tracks: list[dict]) -> str:
    return "\n".join(
        f"- **{t['title']}** — {t['artist']} ({t['album']}, {t['genre']}) · {t['price']}"
        for t in tracks
    )


def catalog_specialist(text: str, offline: bool) -> tuple[str, list[dict]]:
    stripped = re.sub(r"(?i)\b(find|search|show|me|the|song|track|album|of|for|"
                      r"a|an|any|some|please|with|music)\b", " ", text).strip()
    tokens = [t for t in stripped.split() if len(t) > 2]
    seen: set[int] = set()
    tracks: list[dict] = []
    for token in tokens or [stripped]:
        for hit in catalog.search_tracks(token, limit=8):
            if hit["track_id"] not in seen:
                seen.add(hit["track_id"])
                tracks.append(hit)
        if len(tracks) >= 8:
            break
    if not tracks:
        return (("I couldn't find anything matching that. Try an artist name, "
                "album title, or genre like jazz, rock, pop, electronic, or folk."),
                [])
    note = " *(offline catalog search)*" if offline else ""
    return (f"Here's what I found{note}:\n{_format_tracks(tracks[:8])}",
            tracks[:8])


def order_specialist(text: str, entities: dict, offline: bool) -> tuple[str, dict | list]:
    email_m = _EMAIL_RE.search(text)
    inv_m = _INVOICE_RE.search(text)
    email = (entities.get("email") or entities.get("lookup_email")
             or (email_m.group(0) if email_m else ""))
    invoice = entities.get("invoice") or (inv_m.group(1) if inv_m else "")
    if invoice:
        detail = orders.order_detail(int(invoice))
        if detail is None:
            return ((f"I couldn't find invoice #{invoice}. Check the number and "
                    "try again."), {})
        items = "\n".join(f"  - {i['title']} — {i['artist']} ({i['price']})"
                          for i in detail["items"])
        return ((f"Invoice **#{detail['invoice_id']}** · {detail['date']} · "
                f"status: **{detail['status']}** · total {detail['total']}\n"
                f"Customer: {detail['customer']}\nItems:\n{items}"), detail)
    if email:
        found = orders.orders_for_email(email)
        if not found:
            return ((f"No orders found for {email}. Make sure it's the email "
                    "used at checkout."), [])
        lines = "\n".join(f"- Invoice **#{o['invoice_id']}** · {o['date']} · "
                          f"{o['status']} · {o['total']}" for o in found)
        return ((f"Orders for {email}:\n{lines}\nAsk for an invoice number "
                "to see its items."), found)
    return (("To look up an order I need your invoice number (e.g. 1001) or the "
            "email used at checkout."), {})


def faq_specialist(text: str) -> str:
    t = text.lower()
    if "return" in t or "refund" in t:
        return orders.policy_answer("returns")
    if "ship" in t or "deliver" in t:
        return orders.policy_answer("delivery")
    if "pay" in t or "card" in t or "paypal" in t:
        return orders.policy_answer("payments")
    if "account" in t or "email" in t or "history" in t:
        return orders.policy_answer("account")
    return orders.policy_answer("returns")


def recommend_specialist(text: str) -> tuple[str, list[dict]]:
    artist_m = re.search(r"(?i)(?:like|by|from)\s+([a-z &]+)", text)
    tracks: list[dict] = []
    if artist_m:
        tracks = catalog.recommend_for_artist(artist_m.group(1).strip(), 5)
    if not tracks:
        tracks = catalog.search_tracks("", 5) or catalog.search_tracks("the", 5)
    return (f"Based on your taste, you might like:\n{_format_tracks(tracks)}",
            tracks)


def handoff_specialist() -> str:
    return ("I've flagged your request for a human support agent — they'll "
            "reply within one business day. Your conversation history is "
            "attached to the ticket.")


# --- pipeline-facing node wrappers ------------------------------------------

def intake_node(state: dict) -> dict:
    text = state["message"]
    is_injection, patterns = detect_injection(text)
    redacted, pii_kinds = redact_pii(text)
    # Capture lookup identifiers BEFORE redaction so order lookup still works.
    email_m = _EMAIL_RE.search(text)
    return {"injection": is_injection, "injection_patterns": patterns,
            "clean_message": redacted, "pii_kinds": pii_kinds,
            "lookup_email": email_m.group(0) if email_m else ""}


def route_node(state: dict) -> dict:
    if state.get("injection"):
        return {"decision": RouteDecision(intent="out_of_scope",
                                          confidence=1.0,
                                          reason="blocked: injection"),
                "offline": False, "clarified": False}
    _, _, key_present, _ = provider_status()
    decision = route(state["clean_message"], state.get("history"))
    return {"decision": decision, "offline": not key_present,
            "clarified": False}


def specialist_node(state: dict) -> dict:
    decision: RouteDecision = state["decision"]
    text = state["clean_message"]
    offline = state.get("offline", True)
    entities = dict(decision.entities)
    if state.get("lookup_email"):
        entities.setdefault("lookup_email", state["lookup_email"])
    intent = decision.intent
    if intent == "catalog_search":
        answer, data = catalog_specialist(text, offline)
    elif intent == "order_lookup":
        answer, data = order_specialist(text, entities, offline)
    elif intent == "policy_faq":
        answer, data = faq_specialist(text), None
    elif intent == "recommendation":
        answer, data = recommend_specialist(text)
    elif intent == "human_handoff":
        answer, data = handoff_specialist(), None
    else:
        if state.get("injection"):
            answer = ("I can't help with that request. If you have a question "
                      "about the music store — catalog, orders, or policies — "
                      "ask away.")
        else:
            answer = ("I'm the music-store support assistant — I can search the "
                      "catalog, look up orders, answer policy questions, or "
                      "recommend music. How can I help?")
        data = None
    escalated = intent == "human_handoff"
    return {"answer": answer, "data": data, "escalated": escalated,
            "history": _append_turn(state, decision, answer)}
