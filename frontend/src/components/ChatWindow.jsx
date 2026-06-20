import { useEffect, useRef, useState } from "react";
import { useStream } from "../hooks/useStream";
import { MessageBubble } from "./MessageBubble";

const SUGGESTIONS = [
  "What is your return policy?",
  "Where is order ORD-2024-0001?",
  "Tell me about product SKU-001",
  "How long does shipping take?",
];

export function ChatWindow({ sessionId }) {
  const { messages, isStreaming, sendMessage } = useStream({ sessionId });
  const [draft, setDraft] = useState("");
  const scrollerRef = useRef(null);

  // Auto-scroll to the bottom whenever a message arrives or grows.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  const lastMessage = messages[messages.length - 1];
  const hasEscalation = !!lastMessage?.escalated;

  const onSubmit = (e) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    sendMessage(text);
  };

  return (
    <div className="flex h-full w-full bg-ink-950 text-ink-100">
      {/* Sidebar */}
      <aside className="hidden w-72 shrink-0 flex-col border-r border-ink-800 bg-ink-900 p-5 md:flex">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500" />
          <div className="text-sm font-semibold">Acme Support</div>
        </div>

        <div className="mt-8">
          <div className="text-[11px] uppercase tracking-wider text-ink-400">Session</div>
          <div className="mt-1 break-all font-mono text-[11px] text-ink-300">{sessionId}</div>
        </div>

        <div className="mt-8">
          <div className="text-[11px] uppercase tracking-wider text-ink-400">Status</div>
          <div className="mt-1 flex items-center gap-2 text-sm">
            <span
              className={
                "inline-block h-2 w-2 rounded-full " +
                (hasEscalation ? "bg-amber-400" : "bg-emerald-400")
              }
            />
            {hasEscalation ? "Escalated to human" : "Online — AI agent"}
          </div>
        </div>

        <div className="mt-auto pt-6 text-[11px] leading-relaxed text-ink-400">
          Built with LangGraph, Gemini 2.5, MCP tools, and ChromaDB RAG.
        </div>
      </aside>

      {/* Main */}
      <main className="flex flex-1 flex-col">
        <header className="border-b border-ink-800 bg-ink-900/60 px-6 py-3 backdrop-blur">
          <div className="text-sm font-semibold">Customer Support</div>
          <div className="text-xs text-ink-400">
            Demo: AI customer support agent built with LangGraph + ChromaDB RAG. Ask about orders, returns, products, or shipping policies.
          </div>
        </header>

        <div ref={scrollerRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {messages.length === 0 && (
              <div className="rounded-xl border border-ink-800 bg-ink-900/60 p-6 text-sm text-ink-300">
                <div className="text-base font-medium text-ink-100">Hi 👋  How can I help?</div>
                <div className="mt-1">Try one of these to get started:</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => sendMessage(s)}
                      disabled={isStreaming}
                      className="rounded-full border border-ink-700 bg-ink-800/60 px-3 py-1 text-xs text-ink-200 hover:border-accent-soft hover:text-white disabled:opacity-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        </div>

        <form
          onSubmit={onSubmit}
          className="border-t border-ink-800 bg-ink-900/60 px-4 py-3 sm:px-6"
        >
          <div className="mx-auto flex max-w-3xl items-center gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Try: What is your return policy? or How do I track my order?"
              disabled={isStreaming}
              autoFocus
              className="flex-1 rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-ink-100 placeholder-ink-400 outline-none focus:border-accent-soft disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={isStreaming || !draft.trim()}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isStreaming ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
