"""Gradio UI: support chat + observability tab."""
from __future__ import annotations

import os
import time

import gradio as gr

from src.graph.pipeline import handle_message
from src.services.llm_factory import provider_status

_HISTORY: list[dict] = []


def chat_turn(message: str, history: list[dict]) -> tuple[str, list[dict]]:
    if not message.strip():
        return "", history
    t0 = time.time()
    result = handle_message(message)
    ms = int((time.time() - t0) * 1000)
    entry = {
        "user": message, "intent": result["intent"],
        "offline": result["offline"], "escalated": result["escalated"],
        "injection": result["injection"], "latency_ms": ms,
    }
    _HISTORY.append(entry)
    # Guardrail refusals are rule-based template responses — no LLM runs,
    # so they must never wear the "live LLM" badge.
    if result["injection"]:
        badge = " 🛡 guardrail (rule-based refusal)"
    elif result["offline"]:
        badge = " 🟠 offline"
    else:
        badge = " 🟢 live LLM"
    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant",
         "content": result["answer"] + f"\n\n_{result['intent']}{badge}_"},
    ]
    return "", history


def status_line() -> str:
    provider, model, key_present, reason = provider_status()
    if key_present:
        return f"LLM: {provider}/{model} — live"
    return f"LLM: {provider} — offline ({reason}); keyword router + templates"


def history_table() -> list[list]:
    def _mode(e: dict) -> str:
        if e["injection"]:
            return "blocked (guardrail)"
        return "offline" if e["offline"] else "live"
    return [[e["user"][:60], e["intent"], _mode(e),
             "yes" if e["escalated"] else "no", e["latency_ms"]]
            for e in _HISTORY]


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Digital Music Store — Support") as app:
        gr.Markdown("# 🎵 Digital Music Store — Customer Support\n"
                    "Multi-agent support over the store catalog and order DB.")
        with gr.Tab("Support chat"):
            chatbot = gr.Chatbot(type="messages", height=420)
            msg = gr.Textbox(label="Your message",
                             placeholder="e.g. Where is invoice 1001? / Find jazz tracks")
            msg.submit(chat_turn, [msg, chatbot], [msg, chatbot])
            clear = gr.Button("Clear chat")
            clear.click(list, outputs=chatbot)
        with gr.Tab("Observability"):
            status = gr.Markdown(value=status_line())
            table = gr.Dataframe(
                headers=["message", "intent", "mode", "escalated", "latency_ms"],
                label="Turn history")
            refresh = gr.Button("Refresh")
            refresh.click(lambda: (status_line(), history_table()),
                          outputs=[status, table])
    return app


if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0",
                       server_port=int(os.environ.get("PORT", 7861)))
