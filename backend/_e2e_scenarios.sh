#!/usr/bin/env bash
# Run the 5 master-spec scenarios against a live /chat/stream.
# Paces calls 18s apart so we stay under the Gemini free-tier 5-req/min limit.
set -u

URL=${URL:-http://127.0.0.1:8000/chat/stream}
HERE=$(cd "$(dirname "$0")" && pwd)
PARSE="$HERE/_e2e_parse.py"

run() {
  local label=$1
  local message=$2
  local sid=$3
  echo "================================================================"
  echo ">>> $label"
  echo ">>> $message"
  local body
  body=$(printf '%s' "$message" | python -c 'import json,sys; print(json.dumps({"message":sys.stdin.read(),"session_id":"'"$sid"'"}))')
  curl -sN -X POST "$URL" \
    -H "Content-Type: application/json" \
    -d "$body" \
    | python "$PARSE"
}

run "1/5 RAG: return policy"        "What is your return policy?"                                  "e2e-1"
sleep 18
run "2/5 TOOL: order lookup"        "Where is order ORD-2024-0001?"                                "e2e-2"
sleep 18
run "3/5 ESCALATE: angry user"      "This is ridiculous, you are useless and I want my money NOW!" "e2e-3"
sleep 18
run "4/5 TOOL: product info"        "Tell me about product SKU-001"                                "e2e-4"
sleep 18
run "5/5 RAG: shipping"             "How long does shipping take?"                                 "e2e-5"
