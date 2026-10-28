#!/usr/bin/env python3
"""T3-R epoch-6 cycle selector and runner.

C1 is the single pre-registered retention stimulus; C2/C3 are read-only.
The runner refuses to overwrite evidence, refuses a second C1, records C1/C2
validity, and runs the epoch-6 verifier after C3. No secrets are printed.

C1 may run only after this epoch's pre-registration is committed. C2 opens
>=24h+120s after C1; C3 opens >=24h+120s after C2. The harness enforces the
same windows independently.
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
T3R = os.path.dirname(HERE)
REPO = os.path.dirname(T3R)
EVID = os.path.join(T3R, "evidence", "epoch6")
HARNESS = os.path.join(HERE, "t3r_harness.py")
PREREG = os.path.join(HERE, "T3-R-EPOCH6-PREREG-20261028.md")
VERIFY = os.path.join(HERE, "verify.py")
HOSTS = os.path.join(T3R, "inventory", "epoch4-hosts-20261023.txt")
WEIGHTS = os.path.join(T3R, "weights")

C1 = os.path.join(EVID, "t3r-C1.json")
C2 = os.path.join(EVID, "t3r-C2.json")
C3 = os.path.join(EVID, "t3r-C3.json")
V1 = os.path.join(EVID, "t3r-C1-validity.json")
V2 = os.path.join(EVID, "t3r-C2-validity.json")
V3 = os.path.join(EVID, "t3r-C3-verify.json")

EXPECT = "7bfbdcd6686cf23d0f0dc483975be2e22c22019b28f4787726d5ecca18993d66"
WAIT = 24 * 3600 + 120
EDGE_KVCHECK = "https://eon-edge-brain.eon-sovereign.workers.dev/kvcheck?q="
NOT_BEFORE = dt.datetime(2026, 10, 28, 16, 30, tzinfo=dt.timezone.utc)


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse_ts(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def sha_file(path):
    hh = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            hh.update(chunk)
    return hh.hexdigest()


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=False)
        f.write("\n")


def summary(path):
    d = load(path)
    if d is None:
        return None
    return d.get("summary", d)


def age_ok(path):
    s = summary(path)
    ts = parse_ts((s or {}).get("collected_utc"))
    if not ts:
        print("ERROR: unreadable collected_utc in %s" % path, file=sys.stderr)
        return False
    age = (now_utc() - ts).total_seconds()
    print("AGE %s %.0fs need>=%ss" % (os.path.basename(path), age, WAIT), flush=True)
    return age >= WAIT


def run(cycle, out, receipts, previous=None):
    args = [
        sys.executable, HARNESS, "--execute", "--cycle", str(cycle),
        "--prereg", PREREG, "--hosts", HOSTS, "--weights-dir", WEIGHTS,
        "--out", out, "--receipts", receipts, "--expect-seal", EXPECT,
    ]
    if cycle == 1:
        args.append("--allow-m5-ingest")
    else:
        args += ["--baseline", C1]
        if previous:
            args += ["--previous", previous]
    print("RUN cycle=%d out=%s" % (cycle, out), flush=True)
    return subprocess.call(args, cwd=REPO)


def kvcheck(token):
    """Read-only durable-store confirmation for the C1 token.

    The edge-brain can serve a stale count immediately after learn; /kvcheck
    reads the durable item.  This is a C1 validity precondition, not a pass
    criterion change.
    """
    if not token:
        return {"ok": False, "error": "no token"}
    url = EDGE_KVCHECK + urllib.parse.quote(str(token), safe="")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return {
            "ok": True,
            "know": data.get("know"),
            "items": data.get("items"),
            "token_hits": data.get("token_hits"),
            "item_token_hits": data.get("item_token_hits"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def c1_validity():
    if not os.path.exists(C1):
        return None
    sha = sha_file(C1)
    existing = load(V1)
    if existing and existing.get("c1_sha256") == sha and "kvcheck" in existing:
        return existing
    s = summary(C1)
    r = (s or {}).get("M5_retention", {})
    kv = kvcheck(r.get("token"))
    kv_durable = bool(
        kv.get("ok")
        and (int(kv.get("token_hits") or 0) > 0
             or int(kv.get("item_token_hits") or 0) > 0)
    )
    checks = {
        "learn_acked": r.get("learn_acked") is True,
        "knowledge_increased": r.get("knowledge_increased") is True,
        "immediate_retrievable": r.get("immediate_retrievable") is True,
        "ingest_not_skipped": r.get("ingest_skipped") is False,
        "token_present": bool(r.get("token")),
        "allow_m5_ingest": (s or {}).get("invocation", {}).get("allow_m5_ingest") is True,
        "durable_kvcheck": kv_durable,
    }
    out = {
        "checked_utc": now_utc().isoformat(),
        "c1_sha256": sha,
        "token": r.get("token"),
        "m5": r,
        "kvcheck": kv,
        "checks": checks,
        "ok": all(checks.values()),
    }
    write_json(V1, out)
    return out


def c2_validity():
    if not os.path.exists(C2):
        return None
    sha = sha_file(C2)
    existing = load(V2)
    if existing and existing.get("c2_sha256") == sha:
        return existing
    s1, s2 = summary(C1), summary(C2)
    r1 = (s1 or {}).get("M5_retention", {})
    r2 = (s2 or {}).get("M5_retention", {})
    token = r1.get("token")
    c1_after = int(r1.get("knowledge_after") or 0)
    kb = int(r2.get("knowledge_before") or 0)
    ka = int(r2.get("knowledge_after") or 0)
    checks = {
        "token_matches_C1": r2.get("token") == token,
        "retention_ok": r2.get("ok") is True,
        "retrievable": r2.get("retrievable") is True,
        "search_total": int(r2.get("search_total") or 0) >= 1,
        "ingest_skipped": r2.get("ingest_skipped") is True,
        "search_query": r2.get("search_query") == token,
        "knowledge_non_decreasing": ka >= kb,
        "knowledge_vs_C1": kb >= c1_after,
        "M1_no_regression": int(s2.get("M1_live_routes") or 0) >= int(s1.get("M1_live_routes") or 0),
        "M2_no_regression": int(s2.get("M2_distinct_bodies") or 0) >= int(s1.get("M2_distinct_bodies") or 0),
        "M3_no_regression": int(s2.get("M3_phantoms") or 0) <= int(s1.get("M3_phantoms") or 0),
        "failures_zero": s2.get("failures_recorded") == 0,
    }
    out = {
        "checked_utc": now_utc().isoformat(),
        "c2_sha256": sha,
        "token": r2.get("token"),
        "m5": r2,
        "checks": checks,
        "ok": all(checks.values()),
    }
    write_json(V2, out)
    return out


def verify_c3():
    args = [
        sys.executable, VERIFY,
        "--c1", C1, "--c2", C2, "--c3", C3,
        "--validity1", V1, "--validity2", V2,
        "--prereg", PREREG, "--hosts", HOSTS,
    ]
    proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    text = proc.stdout
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {
            "ok": False,
            "gate_pass_mechanical": False,
            "gate_status": "FAIL",
            "gate_pass_overall": None,
            "error": "verifier output was not JSON",
            "stdout": text,
        }
    parsed["verifier_sha256"] = sha_file(VERIFY)
    write_json(V3, parsed)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    print(json.dumps({
        "verifier_rc": proc.returncode,
        "gate_pass_mechanical": parsed.get("gate_pass_mechanical"),
        "gate_status": parsed.get("gate_status"),
        "out": V3,
    }, indent=1), flush=True)
    return proc.returncode


def main():
    os.makedirs(EVID, exist_ok=True)

    if not os.path.exists(C1):
        if now_utc() < NOT_BEFORE:
            print("WAIT C1 not before %s (now %s)" % (NOT_BEFORE.isoformat(), now_utc().isoformat()))
            return 0
        rc = run(1, C1, C1 + ".receipts.json")
        print("C1 EXIT %d" % rc, flush=True)
        if rc != 0:
            return 1
        v = c1_validity()
        print(json.dumps(v, indent=1), flush=True)
        return 0 if v and v.get("ok") else 1

    v1 = c1_validity()
    if not v1 or not v1.get("ok"):
        print("C1_INVALID: refusing C2/C3", file=sys.stderr)
        print(json.dumps(v1, indent=1), flush=True)
        return 1

    if not os.path.exists(C2):
        if not age_ok(C1):
            print("WAIT C2 window not open")
            return 0
        rc = run(2, C2, C2 + ".receipts.json", previous=C1)
        print("C2 EXIT %d" % rc, flush=True)
        if rc != 0:
            return 1
        v2 = c2_validity()
        print(json.dumps(v2, indent=1), flush=True)
        return 0 if v2 and v2.get("ok") else 1

    v2 = c2_validity()
    if not v2 or not v2.get("ok"):
        print("C2_INVALID: refusing C3", file=sys.stderr)
        print(json.dumps(v2, indent=1), flush=True)
        return 1

    if not os.path.exists(C3):
        if not age_ok(C2):
            print("WAIT C3 window not open")
            return 0
        rc = run(3, C3, C3 + ".receipts.json", previous=C2)
        print("C3 EXIT %d" % rc, flush=True)
        if rc != 0:
            return 1
        verify_c3()
        done = load(V3) or {}
        return 0 if done.get("checks") is not None else 1

    if not os.path.exists(V3):
        verify_c3()
        done = load(V3) or {}
        return 0 if done.get("checks") is not None else 1

    done = load(V3) or {}
    print(json.dumps({
        "state": "COMPLETE",
        "gate_pass_mechanical": done.get("gate_pass_mechanical"),
        "gate_status": done.get("gate_status"),
        "gate_pass_overall": done.get("gate_pass_overall"),
        "b10": done.get("b10_zero_hint_attestation"),
        "out": V3,
    }, indent=1), flush=True)
    return 0 if done.get("checks") is not None else 1


if __name__ == "__main__":
    sys.exit(main())
