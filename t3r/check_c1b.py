#!/usr/bin/env python3
"""Verify C1b token reached durable edge-brain KV. Read-only; no secrets."""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EVID = os.path.join(HERE, "evidence", "epoch5")
C1 = os.path.join(EVID, "t3r-C1b.json")
OUT = os.path.join(EVID, "t3r-C1b-validity.json")
KVCHECK = "https://eon-edge-brain.eon-sovereign.workers.dev/kvcheck?q="
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"


def token_from(d):
    s = d.get("summary", d)
    for obj in (s.get("M5_retention"), d.get("M5_retention"), s.get("m5"), d.get("m5")):
        if isinstance(obj, dict) and obj.get("token"):
            return obj["token"]
    return d.get("token") or s.get("token")


def check(q):
    url = KVCHECK + urllib.parse.quote(q, safe="")
    p = subprocess.run(
        ["curl", "-sS", "--max-time", "20", "-A", UA, url],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        return {"_err": "curl_exit_%s" % p.returncode, "raw": (p.stderr or "")[:160]}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"_err": "unparseable", "raw": (p.stdout or "")[:160]}


def main():
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(C1):
        print("C1b evidence missing", file=sys.stderr)
        return 1
    raw = open(C1, "rb").read()
    c1_sha = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw.decode("utf-8"))
    q = token_from(d)
    rec = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "c1b_sha256": c1_sha,
        "token": q,
        "attempts": 0,
        "ok": False,
        "last": None,
        "source": "edge-brain /kvcheck",
    }
    if not q:
        rec["error"] = "token missing from C1b evidence"
        json.dump(rec, open(OUT, "w", encoding="utf-8"), indent=1)
        print("C1B VALIDITY FAIL: token missing", file=sys.stderr)
        return 1
    for i in range(8):
        rec["attempts"] = i + 1
        r = check(q)
        rec["last"] = r
        hits = int(r.get("token_hits") or 0) + int(r.get("item_token_hits") or 0)
        print("KVCHECK attempt=%d token_hits=%s item_token_hits=%s items=%s"
              % (i + 1, r.get("token_hits"), r.get("item_token_hits"), r.get("items")), flush=True)
        if hits > 0:
            rec["ok"] = True
            break
        time.sleep(5)
    json.dump(rec, open(OUT, "w", encoding="utf-8"), indent=1)
    print("C1B VALIDITY", "PASS" if rec["ok"] else "FAIL", "->", OUT)
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
