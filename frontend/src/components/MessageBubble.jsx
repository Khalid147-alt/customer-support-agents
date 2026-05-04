import { EscalationBanner } from "./EscalationBanner";
import { SourceCitations } from "./SourceCitations";
import { StreamingDots } from "./StreamingDots";

function AgentAvatar() {
  return (
    <div
      aria-hidden="true"
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 text-[11px] font-bold text-white shadow-sm"
    >
      AI
    </div>
  );
}

export function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";
  const isEmptyStream = isStreaming && !message.content;

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-sm leading-relaxed text-white shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <AgentAvatar />
      <div className="max-w-[78%] flex-1">
        <div
          className={
            "rounded-2xl rounded-tl-sm border border-ink-700/70 bg-ink-800/70 px-4 py-2.5 text-sm leading-relaxed text-ink-100 shadow-sm " +
            (message.status === "error" ? "border-red-800/60 bg-red-900/30 text-red-100" : "")
          }
        >
          {isEmptyStream ? <StreamingDots /> : <span className="whitespace-pre-wrap">{message.content}</span>}
        </div>

        {message.escalated && <EscalationBanner ticketId={message.ticketId} />}

        {!message.escalated && message.sources && (
          <SourceCitations sources={message.sources} />
        )}
      </div>
    </div>
  );
}
