#!/usr/bin/env python3
"""Refresh EON cloud knowledge cards only when material facts change.

Reads tokens from env (CI) or local 600-mode files (manual), pulls live state,
updates GitHub cards, re-ingests the updated raw URLs into the edge brain, and
pins a short refresh note into ghost memory.

CI: .github/workflows/eon-knowledge-refresh.yml (every 6h) supplies
GH_TOKEN, BETTERSTACK_TOKEN, EON_ADM_TOKEN.

Manual:
  python3 ~/eon-tmp/refresh-eon-knowledge.py
"""
import base64
import datetime
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request

H = os.environ.get("EON_HOME", "/data/data/com.termux/files/home")
MCP = H + "/eon-tmp/mcpcall.sh"
MCP_URL = os.environ.get("EON_MCP_URL", "https://eon-mcp.eon-sovereign.workers.dev/mcp")
REPO = "didicola/eon-opencode-cloud"
BRANCH = "main"
EON_MONITOR_IDS = {"5100725", "5100726", "5100727", "5100728", "5100729"}
HEARTBEAT_ID = "513053"
STATUS_PAGE_ID = "268175"
UA = "Mozilla/5.0 (Linux; Android 14) EON-Knowledge/1.0"


def read_token(path, pattern):
    raw = open(path).read().strip()
    m = re.search(pattern, raw)
    return m.group(1) if m else raw


GH_TOKEN = os.environ.get("GH_TOKEN") or read_token(H + "/eon-tmp/.ghtok", r"(ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)")
BS_TOKEN = os.environ.get("BETTERSTACK_TOKEN") or read_token(H + "/eon-tmp/.bstok", r"([A-Za-z0-9._\-]{20,})")
EON_ADM_TOKEN = os.environ.get("EON_ADM_TOKEN", "").strip()


def http_json(url, headers=None, method="GET", body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        raw = r.read().decode()
        return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}
    except Exception as e:
        return 0, {"err": type(e).__name__ + ": " + str(e)[:200]}


def gh(method, path, body=None):
    return http_json(
        "https://api.github.com" + path,
        headers={
            "Authorization": "Bearer " + GH_TOKEN,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
        body=body,
        timeout=40,
    )


def bs_get(path):
    return http_json(
        "https://uptime.betterstack.com" + path,
        headers={"Authorization": "Bearer " + BS_TOKEN},
        timeout=30,
    )


def mcp_direct(tool, args, timeout=120):
    """Call the MCP endpoint directly (CI path) with the admin token."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": {**args, "auth": EON_ADM_TOKEN}},
    }
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        raw = r.read().decode()
    except urllib.error.HTTPError as e:
        return {"http": e.code, "raw": e.read().decode()[:400]}
    except Exception as e:
        return {"err": type(e).__name__ + ": " + str(e)[:200]}
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"raw": raw[:500]}
    try:
        j = json.loads(m.group(0))
    except Exception:
        return {"raw": raw[:500]}
    res = j.get("result", {})
    if "content" in res:
        text = "\n".join(c.get("text", "") for c in res.get("content", []))
        try:
            return json.loads(text)
        except Exception:
            return {"text": text[:1000]}
    if "error" in j:
        return {"rpc_error": j["error"]}
    return res


def mcp(tool, args, timeout=120):
    if EON_ADM_TOKEN:
        return mcp_direct(tool, args, timeout)
    try:
        p = subprocess.run(
            [MCP, tool, json.dumps(args)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = p.stdout.strip()
        try:
            return json.loads(out)
        except Exception:
            return {"raw": out[:500], "stderr": p.stderr[:200]}
    except subprocess.TimeoutExpired:
        return {"timeout": timeout}
    except Exception as e:
        return {"err": type(e).__name__ + ": " + str(e)[:150]}


def strip_updated(text):
    return "\n".join(
        line for line in text.replace("\r\n", "\n").splitlines()
        if not line.startswith("Updated:")
    ).strip()


def build_monitoring():
    st, monitors = bs_get("/api/v2/monitors?per_page=50")
    rows = []
    if st == 200:
        by_id = {m.get("id"): m for m in monitors.get("data", [])}
        for mid in sorted(EON_MONITOR_IDS):
            m = by_id.get(mid)
            if not m:
                rows.append(f"- {mid} unknown — not found")
                continue
            a = m.get("attributes", {})
            rows.append(
                f"- {mid} {a.get('status','?')} @{a.get('check_frequency','?')}s — "
                f"{a.get('pronounceable_name','?')} — {a.get('url','?')}"
            )
    else:
        rows.append(f"- monitor API error: HTTP {st}")
    st_h, hb = bs_get(f"/api/v2/heartbeats/{HEARTBEAT_ID}")
    hba = hb.get("data", {}).get("attributes", {}) if st_h == 200 else {}
    hb_line = (
        f"Heartbeat {HEARTBEAT_ID} — {hba.get('name','?')} — "
        f"{hba.get('period','?')}s period / {hba.get('grace','?')}s grace — {hba.get('status','?')}."
    )
    st_p, sp = bs_get(f"/api/v2/status-pages/{STATUS_PAGE_ID}")
    spa = sp.get("data", {}).get("attributes", {}) if st_p == 200 else {}
    status_url = f"https://{spa.get('subdomain','eon-arch')}.betteruptime.com"
    aggregate = spa.get("aggregate_state", "unknown")

    return f"""# EON Monitoring Card

Status page: {status_url} ({aggregate})

Better Stack monitors (60-second checks):
{chr(10).join(rows)}

{hb_line}

Catalog relations are paid-only (API 403, upgrade required). The MCP OAuth scope is read-only; writes use a local API token that is never published. No secrets are in this card."""


def build_agi():
    st_self, self_state = http_json("https://eon-agi.eon-sovereign.workers.dev/self")
    st_state, state = http_json("https://eon-agi.eon-sovereign.workers.dev/state")
    st_driver, driver = http_json("https://eon-agi.eon-sovereign.workers.dev/driver")
    if st_state != 200 or not isinstance(state, dict):
        return f"""# EON Cloud AGI State

Live state unavailable: HTTP {st_state}. No stale numbers are written; retry later."""
    if st_self != 200 or not isinstance(self_state, dict):
        self_state = {}
    if st_driver != 200 or not isinstance(driver, dict):
        driver = {}

    h = dict(state)
    h.update(self_state)
    cycles = state.get("cycles", h.get("cycles", 0))
    passed = state.get("passed", h.get("passed", 0))
    failed = state.get("failed", h.get("failed", max(0, cycles - passed)))
    score = self_state.get("score", h.get("score", (passed / cycles if cycles else "?")))
    try:
        score_pct = f"{float(score) * 100:.1f}%"
    except Exception:
        score_pct = str(score)

    lessons = self_state.get("lessons_count")
    if lessons is None:
        lessons = len(state.get("lessons") or [])
    goals = state.get("goals") if isinstance(state.get("goals"), list) else []
    if not goals:
        goals = self_state.get("goals") if isinstance(self_state.get("goals"), list) else []
    provisions = state.get("provision_goals") if isinstance(state.get("provision_goals"), list) else []
    if not provisions:
        provisions = self_state.get("provisions") if isinstance(self_state.get("provisions"), list) else []

    llm = state.get("llm") or {}
    try:
        llm_pct = f"{100.0 * float(llm.get('correct', 0)) / float(llm.get('tried', 1)):.1f}%"
    except Exception:
        llm_pct = "n/a"

    domains = state.get("domains") or {}
    parts = []
    if isinstance(domains, dict):
        for name in ("math", "logic", "string", "compare", "alphasort",
                     "temporal", "causal", "spatial", "creative"):
            d = domains.get(name)
            if not isinstance(d, dict):
                continue
            n = d.get("n", 0)
            c = d.get("correct", 0)
            pct = f"{100.0 * c / n:.1f}%" if n else "n/a"
            parts.append(f"{name} {c}/{n} ({pct})")
    domain_line = "; ".join(parts) if parts else "?"

    transfer = state.get("transfer") or self_state.get("transfer") or {}
    transfer_line = "none"
    if transfer:
        transfer_line = (
            f"{transfer.get('from','?')} -> {transfer.get('to','?')} "
            f"delta {transfer.get('delta','?')} "
            f"(base {transfer.get('base_acc','?')} / transfer {transfer.get('transfer_acc','?')})"
        )

    driver_line = "unknown"
    if driver:
        # /driver returns the alarm's *next due* timestamp, which is volatile by design.
        # Rendering it would make this card change on every refresh (and trigger a
        # needless knowledge write), so we render only the stable armed boolean.
        driver_line = "armed" if driver.get("armed") else "not armed"

    last_run = state.get("last_run") or "?"
    stale_line = ""
    try:
        import datetime as _dt
        lr = _dt.datetime.fromisoformat(str(last_run).replace("Z", "+00:00"))
        age = _dt.datetime.now(_dt.timezone.utc) - lr
        if age.total_seconds() > 86400:
            # Deliberately no live age here: a ticking age would make this card
            # change on every refresh and trigger a pointless knowledge write.
            stale_line = (
                f"State: **STALE** — no advancement observed since {last_run}."
            )
    except Exception:
        stale_line = ""

    return f"""# EON Cloud AGI State

Worker: {h.get('service','eon-agi')} ({h.get('version','?')}); store=do-storage.
Cycles: {cycles}. Passed: {passed}. Failed: {failed}. Score: {score_pct}.
Self-mods: {h.get('mods','?')}. Lessons: {lessons}. Provisions: {len(provisions)}. Goals: {len(goals)}.
Best prompt: {h.get('best_prompt','?')}. LLM accuracy: {llm_pct}.

Domains: {domain_line}.
Last run: {last_run}.
Transfer probe: {transfer_line}.
Driver: {driver_line}.
{stale_line}

Architecture map: https://github.com/{REPO}/blob/{BRANCH}/ARCHITECTURE.md
Known gaps: termux2 .3 last up 2026-10-21, LAN unverified 2026-10-27; ubuntu .72 phone-unreachable; Vercel read-only. /health is a 200-for-all stub; this card uses /self + /state + /driver.
No secrets in this card."""


def update_file(name, material, topic):
    st, cur = gh("GET", f"/repos/{REPO}/contents/{name}")
    current = ""
    sha = None
    if st == 200 and isinstance(cur, dict):
        sha = cur.get("sha")
        try:
            current = base64.b64decode(cur.get("content", "")).decode("utf-8", "replace")
        except Exception:
            current = ""
    if strip_updated(current) == strip_updated(material):
        return {"file": name, "changed": False}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    title, rest = material.split("\n", 1)
    new_text = title + f"\n\nUpdated: {now}" + rest
    body = {
        "message": f"chore: refresh EON knowledge {now}",
        "content": base64.b64encode(new_text.encode()).decode(),
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha
    st, b = gh("PUT", f"/repos/{REPO}/contents/{name}", body)
    if st not in (200, 201):
        return {"file": name, "changed": False, "error": f"HTTP {st}", "body": b}
    commit = (b.get("commit") or {}).get("sha")
    raw = f"https://raw.githubusercontent.com/{REPO}/{commit}/{name}"
    time.sleep(2)
    learned = mcp("brain_learn", {"url": raw, "topic": topic}, timeout=120)
    return {
        "file": name,
        "changed": True,
        "commit": commit,
        "raw": raw,
        "learned": learned.get("learned"),
        "key": learned.get("key"),
        "size": learned.get("size"),
    }


def main():
    results = [
        update_file("EON-MONITORING.md", build_monitoring(), "EON monitoring"),
        update_file("EON-AGI-STATE.md", build_agi(), "EON AGI state"),
    ]
    changed = [r for r in results if r.get("changed")]
    if changed:
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        parts = []
        for r in changed:
            parts.append(f"{r['file']} commit {r.get('commit')} learned {r.get('learned')} key {r.get('key')}")
        text = f"EON KNOWLEDGE REFRESH {now}: " + "; ".join(parts) + ". Cards re-ingested; no secrets."
        pin = mcp("ghost_remember", {"text": text[:600], "pin": True}, timeout=90)
        print(json.dumps({"changed": changed, "pin": pin}, indent=2))
    else:
        print(json.dumps({"changed": [], "note": "no material change"}, indent=2))


if __name__ == "__main__":
    main()
