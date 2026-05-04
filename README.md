# AI Customer Support Agent

A portfolio-grade, production-shaped customer support agent. Built to demonstrate the *architecture* of modern agentic AI systems — not just an LLM in a `<form>`, but a routed, tool-using, RAG-grounded agent with streaming, citations, escalation, and a real database behind it.

**Stack:** FastAPI · LangGraph · MCP · ChromaDB · Postgres · React/Vite/Tailwind · Docker · Google Gemini 2.5

---

## Why this project is interesting

Most "AI chatbot" demos wire one LLM call to a textarea. This one is structured the way a real support assistant has to be:

- **Routed** — a small LLM (`gemini-2.5-flash-lite`) classifies each turn into `rag` / `tool` / `escalate` before any expensive work runs.
- **Grounded** — RAG over a knowledge base (return policy, shipping, FAQ) using sentence-transformers + ChromaDB, with diversity re-ranking and a relevance threshold so the UI only shows citations the agent actually leaned on.
- **Tool-using** — order lookup, product info, and ticket creation are real Postgres-backed tools, exposed both **in-process** (fast path) and over **MCP** (`mcp.server.fastmcp`) for protocol correctness.
- **Streaming end-to-end** — LangGraph `astream_events(version="v2")` → FastAPI SSE → `fetch` + `ReadableStream` in React. Tokens render as they're produced; router structured-output JSON is filtered out by node name so it never leaks to the UI.
- **Stateful** — per-session message history with bounded eviction, plus a stable `session_id` persisted in `localStorage`.
- **Escalates** — when the router decides a turn needs a human, the agent creates a `TKT-YYYY-NNNN` ticket in Postgres and surfaces it back through the SSE `done` event so the UI can render an escalation banner.

---

## Architecture

```
   ┌──────────────┐    SSE      ┌──────────────────────────┐     ┌─────────────────┐
   │  React UI    │◀───────────▶│  FastAPI /chat/stream    │────▶│  LangGraph      │
   │  (Vite+TW)   │   tokens +  │   (SSE, no-cache)        │     │  StateGraph     │
   └──────────────┘   done evt  └──────────────────────────┘     └────────┬────────┘
                                                                          │
                              ┌───────────────────────────────────────────┤
                              ▼                  ▼                        ▼
                       ┌─────────────┐   ┌────────────────┐      ┌────────────────┐
                       │   router    │   │   retrieve     │      │  tool_executor │
                       │ flash-lite  │   │  ChromaDB +    │      │  (in-proc) +   │
                       │  structured │   │  MiniLM-L6-v2  │      │  MCP server    │
                       │   output    │   │  + diversity   │      └───────┬────────┘
                       └─────────────┘   └────────────────┘              │
                              │                                          ▼
                              │                                   ┌────────────┐
                              ▼                                   │ Postgres   │
                        ┌────────────┐                            │  asyncpg   │
                        │  respond   │  (filtered SSE node)       │  pool +    │
                        │ flash 2.5  │                            │  JSON/JSONB│
                        └────────────┘                            │  codecs    │
                                                                  └────────────┘
```

### Graph

```
START → router ──┬──▶ retrieve ──▶ respond ──▶ END
                 ├──▶ tool_executor ──▶ respond ──▶ END
                 └──▶ escalate ──▶ respond ──▶ END
```

`router` is a `with_structured_output(_RouterDecision)` call returning `Literal["rag","tool","escalate"]`. Unknown intents fall back to `rag` so the agent always has something useful to say.

---

## Tech stack

| Layer       | Choice                                            | Why                                                                |
|-------------|---------------------------------------------------|--------------------------------------------------------------------|
| LLM         | Google Gemini 2.5 Flash + Flash-Lite              | Free tier; two models = two quota pools, dodging 5 req/min limit   |
| Agent       | LangGraph `StateGraph` + `add_messages`           | Explicit nodes/edges, easy to reason about, supports streaming     |
| Tools       | `mcp.server.fastmcp.FastMCP` + plain async fns    | Demonstrates MCP; in-process call path keeps latency low           |
| RAG         | sentence-transformers `all-MiniLM-L6-v2` + Chroma | Local, free, fast; pre-downloaded in Docker image                  |
| API         | FastAPI + SSE (`text/event-stream`)               | Async-native, simple streaming, lifespan-managed asyncpg pool      |
| DB          | Postgres 15 + asyncpg                             | Real RDBMS, JSON/JSONB codec registration, pgcrypto for UUIDs      |
| Frontend    | React 18 + Vite + Tailwind v3                     | Vite proxy = no CORS in dev; relative URLs work in prod too        |
| Infra       | docker-compose                                    | One command from clone to running agent                            |

---

## Quickstart — Docker (recommended)

```bash
# 1. Set your Gemini key (free at https://aistudio.google.com/apikey)
echo "GEMINI_API_KEY=your_key_here" > backend/.env

# 2. Build and start everything
docker-compose up -d --build

# 3. One-shot bootstrap: seed the DB + ingest RAG docs into Chroma
docker-compose run --rm bootstrap

# 4. Open the UI
#    http://localhost:5173
```

That's it. The compose stack provisions Postgres (with schema applied via init scripts), the FastAPI backend (with healthcheck on `/health`), and the Vite dev server (proxying `/chat` and `/health` to the backend over the compose network).

## Quickstart — local dev

```bash
# Postgres only from compose
docker-compose up -d postgres

# Backend
cd backend
python -m venv .venv
source .venv/Scripts/activate         # bash on Windows; .venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env                  # then edit: GEMINI_API_KEY=...
python -m db.seed                     # seed users/products/orders
python -m rag.ingest                  # build the Chroma collection
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

---

## The 5 verified scenarios

A reusable smoke test lives at `backend/_e2e_scenarios.sh`. It hits `/chat/stream` for each canonical path and parses the SSE stream via `_e2e_parse.py`. Calls are paced 18s apart to stay under the Gemini free-tier 5-req/min limit.

```bash
cd backend
bash _e2e_scenarios.sh
```

| # | Path        | Prompt                                                       | Expected                                                                |
|---|-------------|--------------------------------------------------------------|-------------------------------------------------------------------------|
| 1 | RAG         | *What is your return policy?*                                | `sources=['return_policy.txt']`, `escalated=False`                      |
| 2 | Tool        | *Where is order ORD-2024-0001?*                              | Tracking + delivered date from Postgres                                 |
| 3 | Escalate    | *This is ridiculous, you are useless and I want my money NOW!* | `escalated=True`, `ticket_id=TKT-YYYY-NNNN`                           |
| 4 | Tool        | *Tell me about product SKU-001*                              | Name, price, stock from `products` table                                |
| 5 | RAG         | *How long does shipping take?*                               | `sources=['shipping_info.txt']`                                         |

All 5 pass against a live `docker-compose up` deployment.

---

## Project layout

```
customer-support-agent/
├── backend/
│   ├── agent/
│   │   ├── graph.py        # StateGraph build + conditional edges
│   │   ├── nodes.py        # router / retrieve / tool_executor / escalate / respond
│   │   ├── state.py        # AgentState TypedDict (Annotated[messages, add_messages])
│   │   ├── llm.py          # Two cached Gemini clients (response + router)
│   │   └── memory.py       # In-process per-session history, bounded
│   ├── api/
│   │   ├── chat.py         # /chat/stream — SSE driver over astream_events v2
│   │   └── health.py       # /health — Postgres SELECT 1 probe
│   ├── db/
│   │   ├── schema.sql      # users, products, orders, tickets (+ pgcrypto)
│   │   ├── connection.py   # asyncpg pool with JSON/JSONB codec registration
│   │   └── seed.py         # Idempotent seed: 5 users, 10 products, 15 orders
│   ├── rag/
│   │   ├── ingest.py       # DirectoryLoader → splitter → MiniLM → Chroma
│   │   └── retriever.py    # Async retrieve with diversity dedupe + cited_sources
│   ├── tools/
│   │   ├── order_lookup.py
│   │   ├── product_info.py
│   │   ├── ticket_creator.py
│   │   └── mcp_server.py   # FastMCP stdio server for protocol-level demo
│   ├── _e2e_scenarios.sh   # The 5 master-spec scenarios
│   ├── _e2e_parse.py       # SSE parser used by the bash driver
│   ├── config.py           # Pydantic Settings (gemini_api_key, db, chroma_dir, …)
│   ├── main.py             # FastAPI app + lifespan-managed pool + CORS
│   └── Dockerfile          # Pre-downloads the embedding model at build
├── docs/                   # RAG knowledge base (return_policy, shipping_info, faq…)
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # localStorage session id (crypto.randomUUID)
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx       # Sidebar + main pane + suggestion chips
│   │   │   ├── MessageBubble.jsx    # User vs agent styling, gradient avatar
│   │   │   ├── StreamingDots.jsx    # Three staggered bouncing dots
│   │   │   ├── SourceCitations.jsx  # 📄 pills under agent messages
│   │   │   └── EscalationBanner.jsx # Amber banner with ticket id
│   │   ├── hooks/useStream.js       # Optimistic append + AbortController
│   │   └── lib/api.js               # SSE parser over fetch/ReadableStream
│   └── vite.config.js               # /chat + /health proxy via VITE_BACKEND_URL
└── docker-compose.yml      # postgres + backend + bootstrap (one-shot) + frontend
```

---

## Environment variables

| Var                | Where        | Required | Notes                                                       |
|--------------------|--------------|----------|-------------------------------------------------------------|
| `GEMINI_API_KEY`   | `backend/.env` | yes    | Free at https://aistudio.google.com/apikey                  |
| `DATABASE_URL`     | env / compose | yes     | Compose overrides to `postgres:5432`                        |
| `CHROMA_DIR`       | env / compose | no      | Defaults to `./chroma_db`                                   |
| `GEMINI_MODEL`     | `backend/.env` | no     | Defaults to `gemini-2.5-flash`                              |
| `ENVIRONMENT`      | env / compose | no      | `development` / `production`                                |
| `VITE_BACKEND_URL` | compose      | no       | Vite proxy target; defaults to `http://localhost:8000`      |
| `POSTGRES_PASSWORD`| compose      | no       | Defaults to `password`                                      |

---

## Implementation notes

A few decisions worth calling out:

- **Two LLM clients, separate quota pools.** The free Gemini tier caps both `flash` and `flash-lite` at 5 req/min, but the limits are independent. Routing on `flash-lite` means a chat turn costs *one* request from each pool instead of two from the same one — eliminates throttle errors on rapid turns.
- **Filter SSE tokens by `metadata.langgraph_node == "respond"`.** Without this, the router's structured-output JSON (`{"intent":"rag"}` etc.) streams to the UI as visible tokens. Filtering by node name is cleaner than parsing token content.
- **JSON/JSONB asyncpg codec.** Registered in `_init_connection` so writes accept `dict` and reads return `dict` — no manual `json.dumps` / `::jsonb` casting throughout the codebase.
- **Diversity re-rank in RAG.** After top-k similarity, dedupe by source filename so a single doc can't monopolize the citation list.
- **Citation threshold.** Only `relevance_score >= 0.20` chunks become UI pills, so low-quality fillers don't distract from sources the agent actually used.
- **Pre-download the embedding model in the Dockerfile.** Avoids a ~90 MB HuggingFace download on first request inside the container.
- **MCP + in-process tools.** `mcp.server.fastmcp.FastMCP` runs the same tool code over stdio for protocol correctness; the agent calls them in-process to skip the round-trip. Both surfaces, one implementation.

---

## Deployment notes (Railway)

The compose stack is already structured for a Railway deployment:

1. Push the repo. Railway auto-detects `docker-compose.yml`.
2. Provision Postgres as a Railway plugin; copy its `DATABASE_URL` into the backend service env.
3. Set `GEMINI_API_KEY` on the backend service.
4. Run the bootstrap one-shot from the Railway shell: `python -m db.seed && python -m rag.ingest`.
5. The frontend service can be swapped to `npm run build` + a static-files server, or deployed to Vercel/Netlify with `VITE_BACKEND_URL` pointed at the Railway backend URL.

Healthchecks (`/health` on backend, `pg_isready` on Postgres) are already configured so Railway's deploy gating works out of the box.

---

## License

MIT
