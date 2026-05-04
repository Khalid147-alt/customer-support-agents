// Three bouncing dots — shown while we're waiting for the first token.
export function StreamingDots() {
  return (
    <div className="flex items-end gap-1 py-1.5" aria-label="Agent is thinking">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="block h-1.5 w-1.5 rounded-full bg-ink-300 animate-bounce-dot"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
  );
}
