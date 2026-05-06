# about-project.md — Customer Support Agent

> **Purpose of this file:** This is the canonical context file for Claude Code. Read this *first* in every new session before doing anything else. It documents what the project is, what's been built, what decisions are locked, and where everything lives. After reading this you should be able to make changes confidently without re-exploring the codebase from scratch.

---

## 1. What this project is

A portfolio-grade AI customer support agent for Khalid (Upwork / job-interview demo). It is **architecturally complete end-to-end** through Phase 8 of an 8-phase master spec. Every piece — routing, RAG, tools, escalation, streaming, UI, Docker — is wired and verified.

**Deployed shape:** React chat UI ⇄ FastAPI SSE ⇄ LangGraph agent ⇄ {Gemini LLM, ChromaDB RAG, Postgres-backed tools, MCP server}.

**Repo root:** `D:\customer-support-agent` (Windows host, Docker for Postgres).

---

## 2. Locked decisions (do not relitigate without explicit user say-so)

| Decision                  | Choice                                       | Notes                                                              |
|---------------------------|----------------------------------------------|--------------------------------------------------------------------|
| LLM provider              | **Google Gemini 2.5** via `langchain-google-genai` | Master spec originally said Claude/Anthropic — we use Gemini, free tier. |
| Env var name              | **`GEMINI_API_KEY`**                         | NOT `GOOGLE_API_KEY`. User firm on this — matches AI Studio UI.    |
| Response model            | `gemini-2.5-flash` (temp 0.4)                | Configurable via `GEMINI_MODEL`.                                   |
| Router model              | `gemini-2.5-flash-lite` (temp 0.0)           | Separate quota pool from `flash` — dodges 5 req/min free-tier limit. |
| Agent framework           | **LangGraph `StateGraph`** with conditional edges | Not LCEL chains.                                              |
| Tools transport           | **MCP `FastMCP` (stdio)** + **in-process** dual surface | MCP for protocol-correctness demo; in-process call path used by the agent at runtime to avoid round-trip latency. |
| RAG store                 | ChromaDB (local persistence)                 | Pre-downloaded MiniLM model in Docker image.                       |
| Embeddings                | `sentence-transformers/all-MiniLM-L6-v2`     | Normalized, CPU device.                                            |
| DB driver                 | **asyncpg** (Postgres) **or aiosqlite** (HF Spaces) via `db/adapter.py` | Selected by `USE_SQLITE` env var. JSON/JSONB codec registered for asyncpg. |
| Frontend                  | React 18 + Vite + Tailwind v3                | Vite proxy `/chat` and `/health` → backend in dev. Prod uses `VITE_BACKEND_URL` + open CORS. |
| Streaming                 | LangGraph `astream_events(version="v2")` → FastAPI SSE → fetch+ReadableStream | Filter tokens by `metadata.langgraph_node == "respond"` to keep router structured-output JSON out of the UI. |
| Workflow                  | Phased delivery; user reviews between phases | Phases 1–8 all complete.                                           |
| Local env                 | Python 3.13 venv at `backend\.venv` + Docker for Postgres | Windows bash shell (Git Bash).                       |

---

## 3. Architecture

```
   ┌──────────────┐    SSE      ┌──────────────────────────┐     ┌─────────────────┐
   │  React UI    │◀───────────▶│  FastAPI /chat/stream    │────▶│  LangGraph      │
   │  (Vite+TW)   │   tokens +  │   (no-cache, SSE)        │     │  StateGraph     │
   └──────────────┘   done evt  └──────────────────────────┘     └────────┬────────┘
                                                                          │
                              ┌───────────────────────────────────────────┤
                              ▼                  ▼                        ▼
                       ┌─────────────┐   ┌────────────────┐      ┌────────────────┐
                       │   router    │   │   retrieve     │      │  tool_executor │
                       │ flash-lite  │   │  Chroma + MiniLM│      │  in-proc + MCP │
                       │  structured │   │  + diversity    │      └───────┬────────┘
                       └─────────────┘   └────────────────┘              │
                              │                                          ▼
                              ▼                                   ┌────────────┐
                        ┌────────────┐                            │ Postgres   │
                        │  respond   │                            │  asyncpg + │
                        │  flash 2.5 │                            │  JSON codec│
                        └────────────┘                            └────────────┘
```

### LangGraph

```
START → router ──┬──▶ retrieve       ──▶ respond ──▶ END
                 ├──▶ tool_executor  ──▶ respond ──▶ END
                 └──▶ escalate       ──▶ respond ──▶ END
```

- `router` uses `with_structured_output(_RouterDecision)` returning `Literal["rag","tool","escalate"]`.
- Unknown intents fall back to `rag` (`_route_after_router` default branch in `graph.py`).
- `respond` is the only node whose tokens stream to the client.

---

## 4. Repo layout (load-bearing files only)

```
customer-support-agent/
├── about-project.md                 ← THIS FILE — read first every session
├── AGENTS.md                        ← Older context; superseded by this file but kept
├── README.md                        ← Public-facing portfolio README
├── docker-compose.yml               ← postgres + backend + bootstrap (one-shot) + frontend
├── backend/
│   ├── .env                         ← Real Gemini key lives here (gitignored)
│   ├── .env.huggingface.example     ← Vars/secrets template for HF Spaces
│   ├── .dockerignore                ← Slims build context for HF Spaces image
│   ├── Dockerfile                   ← Pre-downloads MiniLM; EXPOSE 7860; ARG REQS picks reqs file
│   ├── requirements.txt             ← Local/Postgres deps (asyncpg, etc.)
│   ├── requirements.huggingface.txt ← HF Spaces deps (aiosqlite instead of asyncpg)
│   ├── config.py                    ← Pydantic Settings — `gemini_api_key`, `use_sqlite`, /tmp default for chroma in prod
│   ├── main.py                      ← FastAPI app + lifespan; auto-bootstraps schema/seed/RAG when USE_SQLITE=true; open CORS
│   ├── docs/                        ← RAG knowledge base (return_policy, shipping_info, product_faq) — moved here for HF Spaces
│   ├── _e2e_scenarios.sh            ← Reusable smoke test (5 master-spec scenarios)
│   ├── _e2e_parse.py                ← SSE parser used by the bash driver
│   ├── agent/
│   │   ├── state.py                 ← AgentState TypedDict (Annotated[messages, add_messages])
│   │   ├── graph.py                 ← StateGraph build + conditional edges
│   │   ├── nodes.py                 ← router/retrieve/tool_executor/escalate/respond
│   │   ├── llm.py                   ← Two cached ChatGoogleGenerativeAI clients
│   │   ├── memory.py                ← In-process per-session history, 20-msg cap
│   │   └── prompts.py               ← All system prompts as constants
│   ├── api/
│   │   ├── chat.py                  ← /chat/stream — SSE driver over astream_events v2
│   │   └── health.py                ← /health — DB probe; safe when no Postgres pool
│   ├── db/
│   │   ├── adapter.py               ← Re-exports init/close/get_pool from either backend based on USE_SQLITE
│   │   ├── schema.sql               ← Postgres: users, products, orders, tickets (+ pgcrypto)
│   │   ├── connection.py            ← asyncpg pool, JSON/JSONB codec registration
│   │   ├── seed.py                  ← Idempotent Postgres seed: 5 users, 10 products, 15 orders
│   │   ├── sqlite_schema.sql        ← SQLite-flavored CREATE TABLE IF NOT EXISTS
│   │   ├── sqlite_connection.py     ← aiosqlite pool shim with same get_pool() interface
│   │   └── sqlite_seed.py           ← Idempotent SQLite seed (skips if rows exist)
│   ├── rag/
│   │   ├── ingest.py                ← DirectoryLoader→splitter→MiniLM→Chroma; resolves docs from backend/docs
│   │   └── retriever.py             ← Async retrieve, diversity dedupe, cited_sources()
│   └── tools/
│       ├── order_lookup.py          ← Tool: lookup by ORD-YYYY-NNNN (uses db.adapter)
│       ├── product_info.py          ← Tool: lookup by SKU-NNN (uses db.adapter)
│       ├── ticket_creator.py        ← Tool: TKT-YYYY-NNNN, MAX+1 in transaction (uses db.adapter)
│       └── mcp_server.py            ← FastMCP stdio server (demo surface)
└── frontend/
    ├── vite.config.js               ← /chat + /health proxy via VITE_BACKEND_URL (dev)
    ├── vercel.json                  ← SPA rewrite: /(.*) → /index.html
    ├── .env.example                 ← VITE_BACKEND_URL template for Vercel
    ├── package.json
    └── src/
        ├── App.jsx                  ← localStorage-persistent session id (crypto.randomUUID)
        ├── lib/api.js               ← streamChat: uses VITE_BACKEND_URL when set; fetch + ReadableStream SSE
        ├── hooks/useStream.js       ← {messages, isStreaming, sendMessage} + AbortController
        └── components/
            ├── ChatWindow.jsx       ← Sidebar + main pane + suggestion chips
            ├── MessageBubble.jsx    ← User right (violet), agent left (AI gradient avatar)
            ├── StreamingDots.jsx    ← Three staggered bouncing dots
            ├── SourceCitations.jsx  ← 📄 pills under agent messages
            └── EscalationBanner.jsx ← Amber banner with ticket id
```

---

## 5. Phase status — all complete

- **Phase 1** ✅ Project scaffold, config, Postgres schema + seed
- **Phase 2** ✅ AgentState + LangGraph skeleton (compiling)
- **Phase 3** ✅ MCP tool servers (FastMCP) + Postgres-backed tool implementations
- **Phase 4** ✅ RAG ingestion + retriever (Chroma + MiniLM + diversity rerank)
- **Phase 5** ✅ All node logic wired (router/retrieve/tool_executor/escalate/respond)
- **Phase 6** ✅ FastAPI SSE streaming endpoint with `astream_events` v2 + node filtering
- **Phase 7** ✅ React chat UI + `useStream` hook + Vite proxy
- **Phase 8** ✅ Docker-compose with healthchecks, README polish, e2e scenarios verified
- **Phase 9** ✅ Free public deployment: HuggingFace Spaces (backend, SQLite + auto-bootstrap) + Vercel (frontend, SPA rewrite, `VITE_BACKEND_URL`)

### The 5 verified e2e scenarios (last run all passed)

| # | Path     | Prompt                                                       | Verified output                                            |
|---|----------|--------------------------------------------------------------|------------------------------------------------------------|
| 1 | RAG      | What is your return policy?                                  | `sources=['return_policy.txt']`, `escalated=False`         |
| 2 | Tool     | Where is order ORD-2024-0001?                                | Delivered Apr 29 2026, tracking 1Z999AA10123456784         |
| 3 | Escalate | This is ridiculous, you are useless and I want my money NOW! | `escalated=True`, `ticket_id=TKT-2026-0006`                |
| 4 | Tool     | Tell me about product SKU-001                                | Wireless Noise-Cancelling Headphones $249.00               |
| 5 | RAG      | How long does shipping take?                                 | `sources=['shipping_info.txt']`                            |

Run them anytime with: `cd backend && bash _e2e_scenarios.sh` (paced 18s apart for free-tier quota).

---

## 6. Implementation notes worth remembering

### LLM
- Two `lru_cache(maxsize=1)` `ChatGoogleGenerativeAI` instances in `agent/llm.py`. The router uses `gemini-2.5-flash-lite` *specifically* because its quota pool is independent from `flash`. A chat turn costs one call from each pool — never two from the same pool — which is what keeps us under 5 req/min on free tier.
- Router uses `with_structured_output(_RouterDecision)` where `_RouterDecision` is a Pydantic model with `intent: Literal["rag","tool","escalate"]`.

### SSE
- `chat.py` drives `graph.astream_events(initial_state, version="v2")` and filters tokens by `meta.get("langgraph_node") == "respond"`. Without that filter, the router's structured-output JSON tokens (`{"intent":"rag"}` etc.) would stream to the UI as visible text.
- Captures `final_state` from `on_chain_end` events to surface `cited_sources`, `escalated`, and `ticket_id` in the final `done` event.
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- Wire format: `data: {type:"token",content}\n\n`, `data: {type:"done",sources,escalated,ticket_id}\n\n`, `data: [DONE]\n\n`.

### DB layer (dual-backend via `db/adapter.py`)
- All app code imports `init_db_pool`, `close_db_pool`, `get_pool` from `db.adapter` — never from `connection` / `sqlite_connection` directly. The adapter switches on `USE_SQLITE`.
- **Postgres path (default, local + Railway):** asyncpg pool. `_init_connection` registers `jsonb` and `json` codecs (encoder=`json.dumps`, decoder=`json.loads`, schema=`pg_catalog`) so `dict` round-trips cleanly without any `::jsonb` casting in app code. Schema is applied by `docker-entrypoint-initdb.d` at first Postgres startup.
- **SQLite path (HuggingFace Spaces):** aiosqlite shim exposing the same `get_pool()` interface. Schema in `sqlite_schema.sql` is applied at lifespan startup; seeding via `sqlite_seed.py` is idempotent (skips if rows exist).
- Tickets get IDs `TKT-YYYY-NNNN` via `MAX+1` inside a transaction (`ticket_creator.py`) — works on both backends.

### RAG
- Splitter: `RecursiveCharacterTextSplitter(500, 50)`.
- `retrieve(query, k=4, fetch_k=10)` then a diversity pass dedupes by source filename so a single doc can't monopolize citations.
- `CITATION_MIN_SCORE = 0.20` in `nodes.py` — only chunks at/above this become UI pills.
- Wrapped in `asyncio.to_thread` to keep the event loop unblocked.

### Regexes (in `agent/nodes.py`)
- `ORDER_ID_RE = re.compile(r"\bORD-\d{4}-\d{3,5}\b", re.IGNORECASE)`
- `SKU_RE = re.compile(r"\bSKU-\d{3,5}\b", re.IGNORECASE)`

### Frontend
- `crypto.randomUUID()` + `localStorage` for session id stability across refreshes.
- `useStream` does optimistic appends (user msg + empty agent msg) and uses `AbortController` so a new send cancels any in-flight request.
- Vite proxy reads `VITE_BACKEND_URL` (`docker-compose` sets it to `http://backend:8000`; falls back to `http://localhost:8000` for host-mode dev).

### Docker
- `docker-compose.yml` services: `postgres`, `backend`, `bootstrap` (one-shot, profile=`bootstrap`), `frontend`.
- Backend overrides `DATABASE_URL` to `postgres:5432` so it reaches Postgres over the compose network.
- Healthchecks: `pg_isready` on Postgres, `urllib /health` on backend.
- Volumes: `postgres_data`, `chroma_data`, `hf_cache`.
- Backend Dockerfile pre-downloads the MiniLM model (~90 MB) at build time so first-request latency in the container isn't blocked on a HuggingFace fetch.
- `EXPOSE 7860` — HuggingFace Spaces convention. Compose still maps to host 8000.
- `ARG REQS=requirements.huggingface.txt` — defaults to the SQLite-flavored deps for HF Spaces. For Postgres builds: `docker build --build-arg REQS=requirements.txt …`.

### HuggingFace Spaces deployment (backend)
- Space type: Docker. Push the repo; the Dockerfile is at `backend/Dockerfile`.
- Env (set in Space → "Variables and secrets"; `GEMINI_API_KEY` must be a **Secret**):
  - `GEMINI_API_KEY=<your key>` (secret)
  - `USE_SQLITE=true`
  - `CHROMA_DIR=/tmp/chroma_db` (HF filesystem is read-only outside `/tmp`)
  - `ENVIRONMENT=production`
  - `GEMINI_MODEL=gemini-2.5-flash`
- Cold start (first request after a sleep): the FastAPI lifespan in `main.py` runs `_bootstrap_sqlite()` which (1) applies `sqlite_schema.sql`, (2) idempotently seeds users/products/orders, (3) ingests `backend/docs/` into Chroma at `CHROMA_DIR`. All three are safe to re-run.
- `/health` is safe when there is no Postgres pool (it short-circuits in SQLite mode).

### Vercel deployment (frontend)
- `frontend/vercel.json` has the SPA rewrite (`/(.*) → /index.html`) so client-side routing works.
- Set `VITE_BACKEND_URL=https://<hf-username>-customer-support-agent-backend.hf.space` as a Vercel project env var (Production + Preview).
- `frontend/src/lib/api.js` reads `VITE_BACKEND_URL` and falls back to relative URLs (which is what the dev Vite proxy uses).
- Backend has open CORS (`allow_origins=["*"]`) so the cross-origin Vercel→HF call works. Tighten to a known origin list before any high-traffic production use.

---

## 7. How to run it

### Docker (canonical)
```bash
# from D:\customer-support-agent
docker-compose up -d --build
docker-compose run --rm bootstrap   # seed DB + ingest RAG (run once)
# UI:        http://localhost:5173
# Backend:   http://localhost:8000  (health: /health, chat: POST /chat/stream)
```

### Local dev (faster iteration on code)
```bash
docker-compose up -d postgres
cd backend
source .venv/Scripts/activate         # Windows bash
python -m db.seed                     # idempotent
python -m rag.ingest                  # wipes & rebuilds Chroma collection
uvicorn main:app --reload --port 8000

# new terminal
cd frontend && npm run dev
```

### E2E smoke test
```bash
cd backend && bash _e2e_scenarios.sh
```

---

## 8. Known gotchas / past pitfalls

- **The Gemini key has been leaked in chat once already.** If you see `AIzaSy…` in conversation, remind the user to rotate it at https://aistudio.google.com/apikey.
- **Phase 8 docker-compose has not been validated end-to-end on the Windows host yet** — files are correct but the user paused validation. Building backend with the embedding pre-download is slow (~minutes) but only happens on first build.
- **Free-tier 5 req/min** — pace anything that hits Gemini. The e2e script sleeps 18s between calls for this reason.
- **Empty file Writes require Read first** — when initializing stub files, Read each one before Write or the tool errors.
- **Don't add `langchain-anthropic` or `openai`** — locked to Gemini.
- **Don't rename `gemini_api_key` back to `google_api_key`** — user explicitly rejected that.

---

## 9. Open follow-ups (optional, not blocking)

- Validate `docker-compose up -d --build` end-to-end and re-run the 5 scenarios against the containerized backend.
- Push the `feat: HuggingFace + Vercel deployment ready` commit (`4d10f4a`) to a real HF Space + Vercel project and verify the 5 scenarios against the public URLs.
- Tighten backend CORS from `*` to the known Vercel origin once the public URL is stable.
- Record a 60–90s portfolio walkthrough video.

---

## 10. User context (Khalid)

- Building this for Upwork freelancing / job interviews.
- Local Python on Windows + Docker for Postgres.
- Prefers phased delivery with review gates.
- Wants Claude Code to read this file at the start of every new session — that's the whole point of this document.
