#!/usr/bin/env bash
# eon-admin.sh — fleet snapshot for the cloud lane.
# Token: read from env MCP_ADMIN_TOKEN; never printed, never echoed.
# Output: one sanitized JSON object on stdout.
set -uo pipefail

if [ -z "${MCP_ADMIN_TOKEN:-}" ]; then
  echo '{"ok":false,"error":"MCP_ADMIN_TOKEN not set"}'
  exit 0
fi

python3 - <<'PY'
import json, os, re, time, urllib.request, urllib.error

URL = "https://eon-mcp.eon-sovereign.workers.dev/mcp"
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"
TOK = os.environ["MCP_ADMIN_TOKEN"]

def call(tool, extra=None):
    args = dict(extra or {})
    args["auth"] = TOK
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as x:
            raw = x.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"http {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"ok": False, "error": "unparseable response"}
    j = json.loads(m.group(0))
    if "error" in j and "result" not in j:
        return {"ok": False, "error": str(j["error"])[:300]}
    res = j.get("result", {})
    if "content" in res:
        text = "\n".join(c.get("text", "") for c in res.get("content", []))
        try:
            return {"ok": True, "result": json.loads(text)}
        except Exception:
            return {"ok": True, "result": text[:4000]}
    return {"ok": True, "result": res}

out = {
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "fleet_health": call("fleet_health"),
    "brain_status": call("brain_status"),
}
print(json.dumps(out, default=str)[:20000])
PY
