// Minimal SSE streaming client for /chat/stream.
//
// We use fetch + ReadableStream rather than EventSource because the backend
// expects POST. Each event is `data: <json>\n\n`; the terminal sentinel is
// the literal `data: [DONE]\n\n`.
//
// BASE is empty in dev (Vite proxy handles /chat and /health) and the full
// HuggingFace Space URL in production (set via VITE_BACKEND_URL at build time).

const BASE = import.meta.env.VITE_BACKEND_URL || "";

/**
 * Stream a chat completion from the FastAPI backend.
 *
 * @param {Object} params
 * @param {string} params.message            User's input.
 * @param {string} params.session_id         Stable per-conversation id.
 * @param {(t:string)=>void} params.onToken  Called for every token chunk.
 * @param {(meta:{sources:string[],escalated:boolean,ticket_id:?string})=>void} params.onDone
 * @param {(err:Error)=>void} [params.onError]
 * @param {AbortSignal} [params.signal]
 */
export async function streamChat({ message, session_id, onToken, onDone, onError, signal }) {
  let res;
  try {
    res = await fetch(`${BASE}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify({ message, session_id }),
      signal,
    });
  } catch (err) {
    onError?.(err);
    return;
  }

  if (!res.ok || !res.body) {
    onError?.(new Error(`Stream error: HTTP ${res.status}`));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line.
      let sepIdx;
      while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);

        // Each event line starts with "data: ".
        for (const line of rawEvent.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);

          if (data === "[DONE]") {
            return; // graceful end
          }

          let payload;
          try {
            payload = JSON.parse(data);
          } catch {
            continue;
          }

          if (payload.type === "token") {
            onToken?.(payload.content || "");
          } else if (payload.type === "done") {
            onDone?.({
              sources:   payload.sources || [],
              escalated: !!payload.escalated,
              ticket_id: payload.ticket_id ?? null,
            });
          } else if (payload.type === "error") {
            onError?.(new Error(payload.message || "Stream error"));
          }
        }
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") onError?.(err);
  }
}
