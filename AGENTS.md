# Customer Support Agent — AGENTS.md

## What this project is
Production AI customer support agent. LangGraph agent loop with MCP tools + RAG.

## Stack
- Backend: FastAPI (async Python 3.11), LangGraph, langchain-google-genai
- LLM: **Google Gemini 2.5 Flash** (`gemini-2.5-flash`) via `ChatGoogleGenerativeAI`
- Tools: MCP protocol (mcp Python SDK)
- RAG: ChromaDB + HuggingFace `all-MiniLM-L6-v2`
- DB: PostgreSQL via asyncpg (no ORM)
- Frontend: React 18 + Vite + TailwindCSS

> Note: the original master spec called for Anthropic Claude. We deliberately use Google Gemini 2.5 here (free tier). All LLM call sites must use `langchain-google-genai`, not `langchain-anthropic`.

## Agent architecture
StateGraph with these nodes:

```
router → (conditional) → rag_lookup | mcp_tools | escalate
rag_lookup → respond
mcp_tools  → respond
escalate   → respond
respond    → END
```

## Key files
- `agent/state.py` — `AgentState` TypedDict; single source of truth for all agent state.
- `agent/graph.py` — The LangGraph `StateGraph`. Imports nodes from `nodes.py`.
- `agent/nodes.py` — All node functions. Each is `async def` and takes/returns an `AgentState` dict.
- `agent/prompts.py` — All system prompts as constants.
- `agent/memory.py` — Conversation memory (Redis or in-memory dict fallback).
- `tools/mcp_server.py` — MCP server. Tools: `order_status`, `create_ticket`, `get_product_info`.
- `rag/ingest.py` — Loads `/docs/`, chunks (500/50), embeds, persists to ChromaDB.
- `rag/retriever.py` — MMR retriever (`k=4, fetch_k=10`); returns docs with source metadata.
- `api/chat.py` — POST `/chat/stream`; SSE streaming endpoint.
- `db/connection.py` — asyncpg pool lifecycle.
- `config.py` — pydantic-settings; loads `.env`.

## Conventions
- All nodes are `async def`.
- All DB calls use the asyncpg pool from `db/connection.py`.
- Secrets from `.env` via `config.py` (`pydantic-settings`).
- No hardcoded prompts in node code — keep them in `agent/prompts.py`.
- **Never use OpenAI or Anthropic.** Gemini only.
- Frontend: functional components + hooks. No class components.

## Build order (do not skip steps)
1. **Project structure + config + .env** ← Phase 1 (current)
2. DB schema + asyncpg connection + seed data ← Phase 1 (current)
3. AgentState + LangGraph skeleton (compiles, no logic)
4. MCP tool servers (testable independently)
5. RAG ingestion + ChromaDB + retriever
6. Wire nodes: router, rag_lookup, mcp_tools, escalate, respond
7. FastAPI SSE streaming endpoint
8. React chat UI + `useStream` hook
9. Integration test: full message flow end-to-end
10. Docker-compose + README polish

## Phase 1 status
- [x] Folder structure + stubs
- [x] `config.py` (pydantic-settings)
- [x] `db/schema.sql`
- [x] `db/connection.py` (asyncpg pool)
- [x] `db/seed.py` (5 users, 10 products, 15 orders)
- [x] `requirements.txt`, `.env.example`, `Dockerfile`, `docker-compose.yml`

## Do NOT
- Use LCEL chains for the agent loop — use a LangGraph `StateGraph`.
- Block the event loop — async everywhere in FastAPI.
- Hardcode API keys.
- Use synchronous DB calls in async routes.
- Skip error handling — every node must catch and degrade gracefully.

## Local dev quickstart (Phase 1)
```bash
# 1. Start postgres
docker-compose up -d postgres

# 2. Create venv and install backend deps
cd backend
python -m venv .venv
.venv/Scripts/activate    # Windows bash
pip install -r requirements.txt

# 3. Copy env and fill in keys
cp .env.example .env

# 4. Seed the DB
python -m db.seed
```
