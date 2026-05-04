// Amber banner shown above an escalated agent message.
export function EscalationBanner({ ticketId }) {
  return (
    <div
      role="alert"
      className="mt-2 flex items-start gap-2 rounded-md border border-amber-700/50 bg-amber-900/30 px-3 py-2 text-sm text-amber-100"
    >
      <span aria-hidden="true" className="mt-0.5">⚠️</span>
      <div className="flex-1">
        <div className="font-medium">Connecting you to a human agent…</div>
        {ticketId && (
          <div className="text-xs text-amber-200/80">
            Ticket created:{" "}
            <span className="font-mono font-semibold">{ticketId}</span>
          </div>
        )}
      </div>
    </div>
  );
}
