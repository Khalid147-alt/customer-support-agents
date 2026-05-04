# Claude Code — project entry point

**Read [`about-project.md`](./about-project.md) at the start of every session, before doing anything else.** It is the canonical context document for this repository: what's built, what's locked, where things live, and how to run it.

After reading `about-project.md`, also skim:
- `README.md` — public-facing overview (architecture diagram, quickstart, e2e scenarios)
- `AGENTS.md` — older context file, kept for history; `about-project.md` supersedes it where they disagree

## Hard rules (do not violate)
- LLM is **Google Gemini 2.5** via `langchain-google-genai`. Never add `langchain-anthropic` or `openai`.
- Env var is **`GEMINI_API_KEY`** (not `GOOGLE_API_KEY`).
- The agent is a **LangGraph `StateGraph`**, not LCEL chains.
- All DB calls go through the asyncpg pool in `backend/db/connection.py`.
- All FastAPI routes are `async`.
- System prompts live in `backend/agent/prompts.py`, not inline in nodes.

If anything in this short list contradicts something else, this file wins.
