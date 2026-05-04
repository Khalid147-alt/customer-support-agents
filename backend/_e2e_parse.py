"""Tiny SSE parser for the e2e shell driver. Reads stdin, prints summary."""
import json
import sys

text = ""
done_event = None
for raw in sys.stdin:
    raw = raw.rstrip()
    if not raw.startswith("data: "):
        continue
    data = raw[6:]
    if data == "[DONE]":
        break
    try:
        ev = json.loads(data)
    except json.JSONDecodeError:
        continue
    if ev.get("type") == "token":
        text += ev["content"]
    elif ev.get("type") == "done":
        done_event = ev

print("RESPONSE:", text.replace("\n", " ")[:300])
if done_event:
    print(
        "DONE:",
        f"sources={done_event.get('sources')}",
        f"escalated={done_event.get('escalated')}",
        f"ticket_id={done_event.get('ticket_id')}",
    )
