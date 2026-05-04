import { useCallback, useRef, useState } from "react";
import { streamChat } from "../lib/api";

/**
 * Conversation hook: holds the message list, drives streaming, exposes sendMessage.
 *
 * Message shape:
 *   {
 *     id: string,
 *     role: "user" | "agent",
 *     content: string,
 *     sources?: string[],         // populated on `done` for agent messages that used RAG
 *     escalated?: boolean,
 *     ticketId?: string|null,
 *     status: "complete" | "streaming" | "error",
 *   }
 */
export function useStream({ sessionId }) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef(null);

  const sendMessage = useCallback(
    async (text) => {
      if (!text?.trim() || isStreaming) return;

      // Cancel any in-flight stream defensively.
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const userId  = crypto.randomUUID();
      const agentId = crypto.randomUUID();

      setMessages((prev) => [
        ...prev,
        { id: userId,  role: "user",  content: text, status: "complete" },
        { id: agentId, role: "agent", content: "",   status: "streaming" },
      ]);
      setIsStreaming(true);

      const updateAgent = (patch) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === agentId ? { ...m, ...patch } : m))
        );
      };

      await streamChat({
        message: text,
        session_id: sessionId,
        signal: controller.signal,
        onToken: (chunk) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === agentId ? { ...m, content: m.content + chunk } : m
            )
          );
        },
        onDone: ({ sources, escalated, ticket_id }) => {
          updateAgent({
            sources,
            escalated,
            ticketId: ticket_id,
            status: "complete",
          });
        },
        onError: (err) => {
          updateAgent({
            content:
              "Sorry — I hit an error while generating that response. Please try again.",
            status: "error",
          });
          // eslint-disable-next-line no-console
          console.error("stream error", err);
        },
      });

      setIsStreaming(false);
      abortRef.current = null;
    },
    [sessionId, isStreaming]
  );

  return { messages, isStreaming, sendMessage };
}
