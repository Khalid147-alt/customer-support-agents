import { useMemo } from "react";
import { ChatWindow } from "./components/ChatWindow";

const SESSION_KEY = "support-agent.session-id";

function getOrCreateSessionId() {
  if (typeof window === "undefined") return "ssr-no-session";
  let id = window.localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = (window.crypto && window.crypto.randomUUID && window.crypto.randomUUID()) || `session-${Date.now()}`;
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export default function App() {
  // Stable session id for the lifetime of this browser. Backend uses it as the memory key.
  const sessionId = useMemo(getOrCreateSessionId, []);

  return (
    <div className="h-full">
      <ChatWindow sessionId={sessionId} />
    </div>
  );
}
