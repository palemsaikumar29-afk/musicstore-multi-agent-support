# Digital Music Store — Multi-Agent Customer Support

Capstone Agent 4 (Interview Kickstart Applied Agentic AI). A supervisor-style
multi-agent support system over a digital music store: it routes customer
messages to specialist agents for catalog search, order lookup, store
policies, recommendations, or human handoff — with prompt-injection
detection and PII redaction on every turn *before* any LLM call.

## Architecture

```
user message
      │
      ▼
┌─ intake ─────────────── 26 injection patterns; PII redaction (email/phone/
│                         card/SSN); lookup identifiers captured pre-redaction
├─ route ─────────────── LLM router (structured INTENT/CONFIDENCE/ENTITIES)
│                         with deterministic keyword-router fallback in
│                         offline mode
└─ specialist ────────── catalog_search | order_lookup | policy_faq |
                         recommendation | human_handoff | out_of_scope
      │                                    │
      ▼                                    ▼
terminal: answered            terminal: escalated / blocked
```

### Five layers (`src/`)

| Layer | Contents |
|---|---|
| `ui` | `app.py`: Gradio 5.x — **Support chat** tab + **Observability** tab (LLM status, turn history, latency) |
| `services/` | env-only config, multi-provider LLM factory (OpenAI/Gemini/Groq), injection detection, PII redaction, catalog + order read-models |
| `agents/` | Pydantic contracts (`RouteDecision`, `TrackInfo`, `OrderSummary`, `SupportResponse`) + intake/router/specialist nodes |
| `graph/` | annotated `SupportState` TypedDict + LangGraph pipeline with conditional routing |
| `database/` | SQLite: artists, genres, albums, tracks (36 seeded), customers, invoices + lines |

## LLM providers

One env var switches providers — OpenAI, Gemini 2.0 Flash, or Groq
`openai/gpt-oss-20b`. Provider, model, key, and timeout all come from the
environment (see `.env.example`); nothing is hardcoded. With no key set, the
pipeline runs in clearly-labelled offline mode (keyword router + templates,
LLM calls never attempted). Retries use exponential backoff (3 attempts).

## Quickstart

```bash
make install          # create .venv and install pinned requirements
make seed             # create + seed the SQLite store database
cp .env.example .env  # fill in at least one LLM API key
make test             # 39 unit + e2e tests (no network, no keys needed)
make lint             # ruff
make run              # launch the Gradio app on 127.0.0.1:7861
```

## Test evidence

- `make test`: **39 passed** — catalog/order read-models against the seeded
  DB, keyword router intent coverage, 26-pattern injection detection,
  PII redaction (email/phone/card/SSN), full pipeline e2e per intent
  (search, order by invoice/email, FAQ, recommendation, handoff,
  injection-blocked, PII-redacted, out-of-scope).
- `make test-all` additionally runs live-LLM router checks (skipped without
  keys) and a Gradio app startup smoke test.
- `make lint`: ruff clean.

## Honest limits

- The seeded catalog/orders are synthetic demo data, not a live store.
- The keyword router is a deterministic fallback; production would use the
  LLM router with evaluation on labelled conversations.
- Built from the published capstone brief for this project; the UpLevel
  portal spec was not re-fetched during this build.
