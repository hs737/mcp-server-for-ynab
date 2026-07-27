#!/usr/bin/env bash
#
# Verify the server speaks MCP over streamable-HTTP, using only curl.
#
# This is the "can an agent actually connect to it" check. It starts the server
# on a throwaway port, walks the protocol handshake by hand, and asserts the
# things a client depends on: a session id is issued, tools/list returns a
# catalog, tools/call returns content, an unknown tool is reported as a tool
# error rather than a crash, and a request without a session is rejected.
#
# Usage:
#   ./scripts/mcp_http_check.sh [port]
#
# Requires YNAB_API_KEY (and YNAB_PLAN_ID for the tools/call step).
# Exits 0 when every assertion passes, 1 otherwise.

set -uo pipefail

PORT="${1:-8765}"
HOST="127.0.0.1"
URL="http://${HOST}:${PORT}/mcp"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"

HEADERS="$(mktemp)"
LOG="$(mktemp)"
FAILURES=0
SERVER_PID=""

cleanup() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
  rm -f "$HEADERS" "$LOG"
}
trap cleanup EXIT

pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1"; FAILURES=$((FAILURES + 1)); }

check() { # check <description> <expected> <actual>
  if [ "$2" = "$3" ]; then pass "$1 ($3)"; else fail "$1 (expected $2, got $3)"; fi
}

# An MCP streamable-HTTP response is an SSE stream; the JSON-RPC payload is on
# the "data:" line.
rpc() { # rpc <session-or-empty> <body>
  local session="$1"
  local args=(-s -D "$HEADERS" -H "Content-Type: application/json"
              -H "Accept: application/json, text/event-stream")
  [ -n "$session" ] && args+=(-H "Mcp-Session-Id: $session")
  curl "${args[@]}" -d "$2" "$URL" | grep '^data: ' | sed 's/^data: //' | tail -1
}

if [ -z "${YNAB_API_KEY:-}" ]; then
  echo "ERROR: YNAB_API_KEY is not set. Load your .env first." >&2
  exit 1
fi

echo "Starting server on ${HOST}:${PORT}"
"$PYTHON" -m ynab_mcp.cli.main http --host "$HOST" --port "$PORT" > "$LOG" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 60); do
  grep -q "Application startup complete" "$LOG" && break
  sleep 0.5
done
if ! grep -q "Application startup complete" "$LOG"; then
  echo "ERROR: server did not start. Log:" >&2
  cat "$LOG" >&2
  exit 1
fi

echo
echo "1. initialize"
BODY=$(rpc "" '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"mcp-http-check","version":"1.0"}}}')
STATUS=$(head -1 "$HEADERS" | tr -d '\r' | awk '{print $2}')
SESSION=$(grep -i '^mcp-session-id:' "$HEADERS" | tr -d '\r' | awk '{print $2}')
check "HTTP status" "200" "$STATUS"
if [ -n "$SESSION" ]; then pass "session id issued"; else fail "no Mcp-Session-Id header"; fi
PROTOCOL=$(echo "$BODY" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["result"]["protocolVersion"])' 2>/dev/null)
if [ -n "$PROTOCOL" ]; then pass "protocolVersion negotiated ($PROTOCOL)"; else fail "no protocolVersion in result"; fi

echo
echo "2. notifications/initialized"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" -H "Mcp-Session-Id: $SESSION" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' "$URL")
check "HTTP status" "202" "$STATUS"

echo
echo "3. tools/list"
TOOLS=$(rpc "$SESSION" '{"jsonrpc":"2.0","id":2,"method":"tools/list"}')
COUNT=$(echo "$TOOLS" | "$PYTHON" -c 'import json,sys; print(len(json.load(sys.stdin)["result"]["tools"]))' 2>/dev/null)
if [ -n "$COUNT" ] && [ "$COUNT" -gt 0 ]; then pass "catalog returned ($COUNT tools)"; else fail "no tools returned"; fi
SCHEMA_OK=$(echo "$TOOLS" | "$PYTHON" -c '
import json, sys
tools = json.load(sys.stdin)["result"]["tools"]
print(all("inputSchema" in t and t.get("description") for t in tools))
' 2>/dev/null)
check "every tool has a schema and description" "True" "$SCHEMA_OK"

echo
echo "4. tools/call"
if [ -n "${YNAB_PLAN_ID:-}" ]; then
  CALL=$(rpc "$SESSION" '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"overview_available_tools","arguments":{}}}')
  CALL_OK=$(echo "$CALL" | "$PYTHON" -c '
import json, sys
res = json.load(sys.stdin)["result"]
print(bool(res["content"]) and not res.get("isError"))
' 2>/dev/null)
  check "tool returned content without error" "True" "$CALL_OK"
else
  echo "  SKIP  YNAB_PLAN_ID not set"
fi

echo
echo "5. unknown tool is a tool error, not a transport failure"
UNKNOWN=$(rpc "$SESSION" '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"no_such_tool","arguments":{}}}')
IS_ERROR=$(echo "$UNKNOWN" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["result"].get("isError"))' 2>/dev/null)
check "isError" "True" "$IS_ERROR"

echo
echo "6. request without a session id is rejected"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/list"}' "$URL")
check "HTTP status" "400" "$STATUS"

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "MCP HTTP check: all assertions passed"
  exit 0
fi
echo "MCP HTTP check: $FAILURES assertion(s) failed"
exit 1
