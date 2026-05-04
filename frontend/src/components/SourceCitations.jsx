// Pill badges shown beneath an agent message that used RAG.
export function SourceCitations({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {sources.map((src) => (
        <span
          key={src}
          className="inline-flex items-center gap-1 rounded-full border border-ink-700 bg-ink-800/60 px-2 py-0.5 text-[11px] font-medium text-ink-200"
          title={`Source document: ${src}`}
        >
          <span aria-hidden="true">📄</span>
          {src}
        </span>
      ))}
    </div>
  );
}
