#!/usr/bin/env python3
"""mcp-auth-bridge.py — streamable-HTTP MCP bridge.

Listens on 127.0.0.1:8788 and forwards to the EON MCP server. Two jobs:
  1. inject the admin token as the `auth` argument of every tools/call
     (clients never see the secret), and
  2. strip the `auth` field from tools/list schemas so agents do not stop to
     ask for a token they should never need.
"""
import json, os, sys
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("MCP_UPSTREAM", "https://eon-mcp.eon-sovereign.workers.dev/mcp")
TOKEN = os.environ.get("MCP_ADMIN_TOKEN", "")
PORT = int(os.environ.get("MCP_BRIDGE_PORT", "8788"))
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"


def inject(obj):
    if isinstance(obj, list):
        return [inject(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    if obj.get("method") == "tools/call":
        params = obj.setdefault("params", {})
        args = params.setdefault("arguments", {})
        if TOKEN and not args.get("auth"):
            args["auth"] = TOKEN
    return obj


def strip_auth(payload):
    """Remove the auth property/requirement from tools/list schemas."""
    try:
        result = payload.get("result")
        if not isinstance(result, dict):
            return payload
        tools = result.get("tools")
        if not isinstance(tools, list):
            return payload
        for t in tools:
            for key in ("inputSchema", "input_schema"):
                sch = t.get(key)
                if isinstance(sch, dict):
                    props = sch.get("properties")
                    if isinstance(props, dict):
                        props.pop("auth", None)
                    req = sch.get("required")
                    if isinstance(req, list):
                        sch["required"] = [x for x in req if x != "auth"]
        return payload
    except Exception:
        return payload


def process_response(data: bytes, ctype: str) -> bytes:
    try:
        text = data.decode(errors="replace")
    except Exception:
        return data
    if "text/event-stream" in (ctype or ""):
        out = []
        for line in text.splitlines():
            if line.startswith("data:"):
                raw = line[5:].strip()
                try:
                    obj = strip_auth(json.loads(raw))
                    out.append("data: " + json.dumps(obj, separators=(",", ":")))
                except Exception:
                    out.append(line)
            else:
                out.append(line)
        return ("\n".join(out) + "\n").encode()
    try:
        return json.dumps(strip_auth(json.loads(text))).encode()
    except Exception:
        return data


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("bridge: " + (fmt % args) + "\n")

    def _forward(self, body: bytes):
        req = urllib.request.Request(UPSTREAM, data=body, method="POST")
        for h in ("Content-Type", "Accept", "Mcp-Session-Id", "MCP-Protocol-Version"):
            v = self.headers.get(h)
            if v:
                req.add_header(h, v)
        req.add_header("User-Agent", UA)
        try:
            with urllib.request.urlopen(req, timeout=180) as x:
                return x.status, x.read(), x.headers.get("Content-Type", "application/json"), x.headers.get("Mcp-Session-Id")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type", "application/json"), e.headers.get("Mcp-Session-Id")
        except Exception as e:
            return 502, json.dumps({"error": str(e)[:200]}).encode(), "application/json", None

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        try:
            msg = json.loads(raw)
            body = json.dumps(inject(msg)).encode()
        except Exception:
            body = raw
        code, data, ctype, sid = self._forward(body)
        data = process_response(data, ctype)
        self.send_response(code)
        self.send_header("Content-Type", ctype or "application/json")
        if sid:
            self.send_header("Mcp-Session-Id", sid)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def do_GET(self):
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    sys.stderr.write(f"bridge: listening on 127.0.0.1:{PORT} -> {UPSTREAM} (token={'set' if TOKEN else 'MISSING'})\n")
    srv.serve_forever()
