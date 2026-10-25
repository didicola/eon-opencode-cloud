#!/usr/bin/env python3
# T3-R HARNESS — Retention successor to T3 epoch 4.
#
# The frozen T3 epoch-4 improvement bar is mathematically saturated and remains
# CLOSED / NO CLAIM. This file does NOT retune that bar and does NOT rewrite any
# epoch-4 artifact. It implements a new, separately pre-registered gate:
#
#   primary:  C1 learns a unique token; C2 and C3 (>=24h apart) retrieve it.
#   guards:   M1/M2/M3 no regression vs C1; WSC-1 weights hash unchanged;
#             C1 ingest acknowledged and knowledge count increased.
#   excluded: M4 (quarantined); coverage/cost are recorded diagnostics only.
#
# The M5 probe is deliberately paired: the token is embedded at the start of a
# fetchable base64 document and the same token is searched. Epoch 4 ingested
# https://example.com but searched for an unrelated EON phrase, so its
# "retrievable:false" was a probe defect, not a retention measurement.
#
# SAFETY:
#   * DRY-RUN by default; --execute is required for network access.
#   * C1 requires --allow-m5-ingest for the single brain_learn call.
#   * C2/C3 are read-only: they only search for the token stored in C1.
#   * The admin token is read from ~/eon-tmp/.adm inside the process and is
#     never printed. The retention token is not a secret.
#   * No worker deploy, no wrangler, no QStack/cloud mutation.

import argparse
import base64
import datetime as _dt
import hashlib
import json
import os
import secrets
import stat
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import t3_c3_harness as h  # noqa: E402

ACCOUNT = h.ACCOUNT
ADMIN_TOKEN_FILE = os.path.expanduser("~/eon-tmp/.adm")
DEFAULT_PREREG = os.path.join(HERE, "T3-R-PREREG-20261025.md")
DEFAULT_HOSTS = os.path.join(HERE, "inventory", "epoch4-hosts-20261023.txt")
DEFAULT_WEIGHTS = os.path.expanduser("~/eon-work/sealed-t1t4-20260929")
EPOCH_DIR = os.path.join(HERE, "evidence", "epoch5")

# New gate constant: WSC-1 over the four frozen designs, computed 2026-10-25.
# The old T3 constant 0e97aa1c... is NOT used; B5 remains an unresolved
# historical mismatch and is recorded, not silently reconciled.
EXPECTED_WEIGHTS = ("01f7432e488702b191347cf9a6b0625a922c96c1ee917db553f199c5aaf5869f")
PASS_BAR_TEXT = (
    "C2 and C3 retrieve the C1 token; M1/M2/M3 no regression vs C1; "
    "WSC-1 weights unchanged; C1 ingest acknowledged + knowledge increased. "
    "M4 quarantined; coverage/cost diagnostic only."
)
M5_AUTH_LANE = "eon-mcp admin token via ~/eon-tmp/.adm (mode 600); never printed"
M4_QUARANTINE = "QUARANTINED — eon-p2p-cloud /status totalPeers=0 across all 6 shards"
TOKEN_PREFIX = "T3R"
TOKEN_HOST = "https://httpbin.org/base64/"


def sha_file(path):
    hh = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            hh.update(chunk)
    return hh.hexdigest()


def now_utc():
    return _dt.datetime.now(_dt.timezone.utc)


def parse_ts(s):
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def guard_zero_hint(argv):
    for a in argv:
        if a == "--hint" or a.startswith("--hint=") or a == "--hint-file" \
                or a.startswith("--hint-file="):
            print("REFUSED (zero-hint guard): %r is a hint channel." % a,
                  file=sys.stderr)
            sys.exit(2)
    if os.environ.get("T3_HINT_FILE"):
        print("REFUSED (zero-hint guard): T3_HINT_FILE is set.", file=sys.stderr)
        sys.exit(2)


def guard_seal(expected):
    actual = sha_file(os.path.abspath(__file__))
    if expected and expected != actual:
        print("ERROR [seal]: expected %s actual %s" % (expected, actual),
              file=sys.stderr)
        sys.exit(6)
    return actual


def guard_window(cycle, previous_path):
    if cycle == 1:
        return
    if not previous_path:
        raise RuntimeError("cycle %d needs --previous" % cycle)
    prev = json.load(open(previous_path, encoding="utf-8"))
    ps = prev.get("summary", prev).get("collected_utc")
    pt = parse_ts(ps)
    if not pt:
        raise RuntimeError("previous collected_utc unreadable")
    delta = now_utc() - pt
    if delta.total_seconds() < 24 * 3600:
        print("ERROR [window]: cycle %d opens after 24h; previous=%s age=%s"
              % (cycle, ps, delta), file=sys.stderr)
        sys.exit(5)


def read_admin_token():
    if not os.path.exists(ADMIN_TOKEN_FILE):
        raise RuntimeError("M5 auth file missing: ~/eon-tmp/.adm")
    mode = stat.S_IMODE(os.stat(ADMIN_TOKEN_FILE).st_mode)
    if mode & 0o077:
        raise RuntimeError("M5 auth file mode is %o; expected 600" % mode)
    tok = open(ADMIN_TOKEN_FILE, encoding="utf-8").read().strip()
    if not tok:
        raise RuntimeError("M5 auth file empty")
    return tok


def mcp_tool(name, args, timeout=60):
    """JSON-RPC tool call with admin auth over stdin; token never printed."""
    tok = read_admin_token()
    a = dict(args)
    a["auth"] = tok
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": a},
    })
    cmd = [
        "curl", "-sS", "--max-time", str(timeout), "-X", "POST",
        "https://eon-mcp.%s/mcp" % ACCOUNT,
        "-H", "content-type: application/json",
        "-H", "accept: application/json, text/event-stream",
        "-H", "user-agent: Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36",
        "--data-binary", "@-",
    ]
    try:
        r = subprocess.run(cmd, input=payload, capture_output=True, text=True,
                           timeout=timeout + 15)
    except Exception as e:
        return {"_err": "curl exception %s" % e.__class__.__name__}
    if r.returncode != 0:
        return {"_err": "curl exit %s" % r.returncode}
    raw = r.stdout or ""
    try:
        d = json.loads(raw)
    except Exception:
        d = None
        for line in reversed(raw.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    d = json.loads(line)
                    break
                except Exception:
                    pass
    if not d:
        return {"_err": "unparseable MCP response"}
    try:
        return json.loads(d["result"]["content"][0]["text"])
    except Exception:
        return {"_err": "MCP result envelope missing content"}


def mcp_status():
    return mcp_tool("brain_status", {})


def mcp_search(q):
    return mcp_tool("knowledge_search", {"q": q})


def search_with_retry(q, attempts=3, delay=2):
    last = {"total": 0, "results": []}
    for i in range(attempts):
        last = mcp_search(q)
        if last.get("total", 0) > 0:
            return last
        if i + 1 < attempts:
            import time
            time.sleep(delay)
    return last


def make_token(cycle):
    return "%s-%s-%s" % (TOKEN_PREFIX, now_utc().strftime("%Y%m%dT%H%M%SZ"),
                         secrets.token_hex(4))


def token_document(token):
    return (token + " EON retention probe. The exact token must remain "
            "retrievable after ingest.")


def token_url(token):
    text = token_document(token)
    b64 = base64.b64encode(text.encode()).decode()
    return TOKEN_HOST + urllib.parse.quote(b64, safe="")


def matched(search, token):
    for r in (search or {}).get("results", []) or []:
        if token in (r.get("content") or "") or token in (r.get("topic") or ""):
            return True
    return False


def m5_collect(cycle, baseline_summary=None, allow_ingest=False):
    print("PROGRESS M5 cycle=%d status-before" % cycle,
          file=sys.stderr, flush=True)
    before = mcp_status()
    print("PROGRESS M5 cycle=%d knowledge-before=%r"
          % (cycle, before.get("knowledge")), file=sys.stderr, flush=True)
    if before.get("_err"):
        return {"ok": False, "error": before.get("_err"),
                "learn_acked": None, "retrievable": None}
    if cycle == 1:
        if not allow_ingest:
            return {"ok": False, "error": "C1 requires --allow-m5-ingest",
                    "learn_acked": None, "retrievable": None}
        token = make_token(cycle)
        print("PROGRESS M5 cycle=1 learn token_len=%d url_host=%s"
              % (len(token), urllib.parse.urlparse(token_url(token)).netloc),
              file=sys.stderr, flush=True)
        learn = mcp_tool("brain_learn", {"url": token_url(token),
                                        "topic": token})
        print("PROGRESS M5 cycle=1 learned=%r"
              % learn.get("learned"), file=sys.stderr, flush=True)
        after = mcp_status()
        print("PROGRESS M5 cycle=1 knowledge-after=%r"
              % after.get("knowledge"), file=sys.stderr, flush=True)
        print("PROGRESS M5 cycle=1 immediate-search", file=sys.stderr,
              flush=True)
        immediate = search_with_retry(token)
        ok_learn = bool(learn.get("learned"))
        kb = before.get("knowledge")
        ka = after.get("knowledge")
        m5 = {
            "ok": bool(ok_learn and not learn.get("_err")),
            "cycle": cycle,
            "token": token,
            "token_url": token_url(token),
            "learn": {k: learn.get(k) for k in
                      ("learned", "key", "kind", "size", "via", "ok", "_err")
                      if k in learn},
            "learn_acked": ok_learn,
            "ingest_skipped": False,
            "knowledge_before": kb,
            "knowledge_after": ka,
            "knowledge_increased": (isinstance(kb, int) and isinstance(ka, int)
                                    and ka > kb),
            "immediate_search_total": immediate.get("total"),
            "immediate_retrievable": matched(immediate, token),
            "immediate_result": (immediate.get("results") or [{}])[0],
            "retrievable": None,  # retention is measured in C2/C3
            "rotated": None,
            "search_query": token,
        }
        m5["ok"] = bool(m5["ok"] and m5["knowledge_increased"]
                        and m5["immediate_retrievable"])
        return m5

    # C2/C3: read-only retention check.
    token = ((baseline_summary or {}).get("M5_retention") or {}).get("token")
    if not token:
        return {"ok": False, "error": "baseline token missing",
                "learn_acked": None, "retrievable": None, "cycle": cycle}
    print("PROGRESS M5 cycle=%d retention-search token_len=%d"
          % (cycle, len(token)), file=sys.stderr, flush=True)
    search = search_with_retry(token)
    print("PROGRESS M5 cycle=%d search_total=%r"
          % (cycle, search.get("total")), file=sys.stderr, flush=True)
    after = mcp_status()
    kb = before.get("knowledge")
    ka = after.get("knowledge")
    base_ka = ((baseline_summary or {}).get("M5_retention") or {}).get(
        "knowledge_after")
    hit = matched(search, token)
    nondecreasing = (isinstance(kb, int) and isinstance(base_ka, int)
                     and kb >= base_ka)
    m5 = {
        "ok": bool(hit and nondecreasing),
        "cycle": cycle,
        "token": token,
        "search_query": token,
        "learn_acked": ((baseline_summary or {}).get("M5_retention") or {}).get(
            "learn_acked"),
        "ingest_skipped": True,
        "retrievable": bool(hit),
        "search_total": search.get("total"),
        "search_result": (search.get("results") or [{}])[0],
        "knowledge_before": kb,
        "knowledge_after": ka,
        "baseline_knowledge_after": base_ka,
        "knowledge_nondecreasing": nondecreasing,
        "rotated": (before.get("uptime") != after.get("uptime")
                    if before.get("uptime") is not None else None),
    }
    return m5


def collect_routes(hosts):
    routes, failures = [], []
    total = len(hosts) * len(h.PATHS)
    done = 0
    print("PROGRESS routes 0/%d" % total, file=sys.stderr, flush=True)
    for host in hosts:
        for path in h.PATHS:
            done += 1
            if done % 25 == 0 or done == total:
                print("PROGRESS routes %d/%d host=%s"
                      % (done, total, host), file=sys.stderr, flush=True)
            r = h.fetch("https://%s%s" % (host, path))
            body = r["body"]
            hh = h.sha(body.encode())[:16] if body else "EMPTY"
            is_catch = body in h.CATCHALL_BODIES
            routes.append({"host": host, "path": path, "code": r["code"],
                           "ms": round(r["ms"]), "hash": hh,
                           "catchall": is_catch, "len": len(body)})
            if r["err"]:
                failures.append({"host": host, "path": path, "err": r["err"]})
    st = h.fetch("https://eon-p2p-cloud.%s/status" % ACCOUNT)
    try:
        s = json.loads(st["body"])
        peers = [sh.get("peers", 0) for sh in s.get("shards", [])]
        m4 = any(p > 0 for p in peers)
        total_peers = s.get("totalPeers")
    except Exception:
        peers, m4, total_peers = [], False, None
        failures.append({"metric": "M4", "err": "status unparseable"})
    m1, m2, m3, phantoms = h.score_routes(routes)
    return {"M1": m1, "M2": m2, "M3": m3, "phantoms": phantoms,
            "M4": m4, "peers": peers, "totalPeers": total_peers,
            "routes": routes, "failures": failures}


def build_summary(cycle, coll, m5, weights_info, prereg_path, baseline_path,
                  previous_path, harness_sha):
    labels = {1: "T3-R C1 BASELINE", 2: "T3-R C2", 3: "T3-R C3"}
    summary = {
        "label": labels[cycle],
        "collected_utc": now_utc().isoformat(),
        "M1_live_routes": coll["M1"],
        "M2_distinct_bodies": coll["M2"],
        "M3_phantoms": coll["M3"],
        "M3_phantom_list": coll["phantoms"],
        "M4_any_shard_peers": coll["M4"],
        "M4_shard_peers": coll["peers"],
        "M4_totalPeers": coll["totalPeers"],
        "M5_retention": m5,
        "weights_hash_expected": EXPECTED_WEIGHTS,
        "weights_hash_reproducible": (
            weights_info.get("computed") == EXPECTED_WEIGHTS
            if weights_info.get("computed") else None),
        "C1_baseline_present": bool(baseline_path),
        "PASS_BAR": PASS_BAR_TEXT,
        "delta_vs_C1": "PENDING - see delta_vs_baseline block",
        "failures_recorded": len(coll["failures"]),
        "failures": coll["failures"],
        "route_count": len(coll["routes"]),
        "route_coverage": round(coll["M1"] / max(1, len(coll["routes"])), 6),
        "cycle": cycle,
        "epoch": "T3-R",
        "mode": "execute",
        "harness": "t3r_harness.py",
        "harness_sha256": harness_sha,
        "M4_quarantined": True,
        "M4_quarantine_reason": M4_QUARANTINE,
        "M5_scoring_note": (
            "C1 learns a unique token; C2/C3 retrieve the same token after "
            ">=24h. Immediate C1 search is a sanity check, not retention."),
        "M5_auth_lane": M5_AUTH_LANE,
        "weights_hash_scheme": weights_info.get("scheme"),
        "weights_hash_computed": weights_info.get("computed"),
        "weights_hash_inputs": weights_info.get("inputs"),
        "weights_hash_method_flag": ("OK" if
                                     weights_info.get("computed") == EXPECTED_WEIGHTS
                                     else "WEIGHTS-CHANGED"),
        "coverage": None,
        "coverage_definition_id": "T3-COV-PROPOSED-v1",
        "coverage_status": "DIAGNOSTIC-ONLY (not a pass criterion)",
        "delta_vs_baseline": None,
        "zero_hint_guard": "no --hint channel supplied to this process",
        "zero_hint_owner_attestation": "PENDING (B10)",
        "preregistration_path": os.path.abspath(prereg_path),
        "preregistration_sha256": sha_file(prereg_path),
        "baseline_path": os.path.abspath(baseline_path) if baseline_path else None,
        "baseline_sha256": sha_file(baseline_path) if baseline_path else None,
        "previous_path": os.path.abspath(previous_path) if previous_path else None,
        "previous_sha256": sha_file(previous_path) if previous_path else None,
        "receipts": None,
    }
    missing = [k for k in h.C2_SUMMARY_KEYS if k not in summary]
    if missing:
        raise RuntimeError("schema bug: missing sealed C2 keys: %s" % missing)
    return summary


def compute_delta(base_s, cyc_s, weights_info, cov_base, cov_cyc):
    out = {
        "baseline_label": base_s.get("label"),
        "baseline_collected_utc": base_s.get("collected_utc"),
        "cycle_label": cyc_s.get("label"),
        "cycle_collected_utc": cyc_s.get("collected_utc"),
        "gate": "T3-R",
        "primary": "retention across cycles",
        "coverage_diagnostic": {
            "baseline": (cov_base or {}).get("coverage"),
            "cycle": (cov_cyc or {}).get("coverage"),
            "definition": (cov_cyc or {}).get("definition_id"),
            "note": "diagnostic only; not a pass criterion",
        },
        "inputs": {
            "M1": [base_s.get("M1_live_routes"), cyc_s.get("M1_live_routes")],
            "M2": [base_s.get("M2_distinct_bodies"),
                   cyc_s.get("M2_distinct_bodies")],
            "M3": [base_s.get("M3_phantoms"), cyc_s.get("M3_phantoms")],
            "M4_quarantined": [base_s.get("M4_any_shard_peers"),
                               cyc_s.get("M4_any_shard_peers")],
            "route_coverage": [base_s.get("route_coverage"),
                               cyc_s.get("route_coverage")],
        },
    }
    per = {}
    for key, direction in (("M1_live_routes", "higher"),
                           ("M2_distinct_bodies", "higher"),
                           ("M3_phantoms", "lower")):
        b, c = base_s.get(key), cyc_s.get(key)
        if b is None or c is None:
            status = "UNDEFINED"
        elif direction == "higher":
            status = "REGRESSED" if c < b else "OK"
        else:
            status = "REGRESSED" if c > b else "OK"
        per[key] = {"direction": direction, "values": [b, c],
                    "status": status}
    out["no_regression"] = {
        "per_metric": per,
        "pass": all(v["status"] == "OK" for v in per.values()),
        "fail_closed_on_undefined": True,
    }
    token = (base_s.get("M5_retention") or {}).get("token")
    cyc_m5 = cyc_s.get("M5_retention") or {}
    base_m5 = base_s.get("M5_retention") or {}
    out["retention"] = {
        "token": token,
        "cycle_retrievable": cyc_m5.get("retrievable"),
        "cycle_search_total": cyc_m5.get("search_total"),
        "baseline_learn_acked": base_m5.get("learn_acked"),
        "baseline_knowledge_after": base_m5.get("knowledge_after"),
        "cycle_knowledge_before": cyc_m5.get("knowledge_before"),
        "cycle_knowledge_after": cyc_m5.get("knowledge_after"),
        "pass": bool(token and base_m5.get("learn_acked") is True
                     and cyc_m5.get("retrievable") is True
                     and cyc_m5.get("knowledge_nondecreasing") is True),
    }
    comp = (weights_info or {}).get("computed")
    weights_ok = (comp == EXPECTED_WEIGHTS
                  and base_s.get("weights_hash_computed") == EXPECTED_WEIGHTS
                  and cyc_s.get("weights_hash_computed") == EXPECTED_WEIGHTS)
    out["weights"] = {
        "expected": EXPECTED_WEIGHTS,
        "baseline": base_s.get("weights_hash_computed"),
        "cycle": cyc_s.get("weights_hash_computed"),
        "computed_now": comp,
        "scheme": (weights_info or {}).get("scheme"),
        "old_t3_constant": h.WEIGHTS_HASH_C1,
        "note": "old 0e97... remains unreconciled (B5); T3-R uses WSC-1",
        "pass": bool(weights_ok),
    }
    out["gate_pass_mechanical"] = bool(
        out["retention"]["pass"] and out["no_regression"]["pass"]
        and out["weights"]["pass"])
    out["gate_pass_overall"] = None  # owner attestation B10 + sign-off
    out["gate_status"] = (
        "PROVISIONAL-PASS-PENDING-ATTESTATION"
        if out["gate_pass_mechanical"] else "FAIL")
    out["zero_hint"] = {
        "mechanical_guard": True,
        "attestation": "REQUIRED-OWNER-ATTESTATION (B10)",
        "note": "harness attests only that no --hint channel was supplied",
    }
    return out


def build_plan(args, hosts, weights_info, baseline_ok, previous_ok, harness_sha):
    return {
        "mode": "DRY-RUN — no network, no writes",
        "epoch": "T3-R",
        "cycle": args.cycle,
        "prereg": os.path.abspath(args.prereg),
        "prereg_sha256": sha_file(args.prereg) if os.path.exists(args.prereg) else None,
        "harness_sha256": harness_sha,
        "hosts": len(hosts),
        "paths": h.PATHS,
        "probes": len(hosts) * len(h.PATHS),
        "baseline": os.path.abspath(args.baseline) if args.baseline else None,
        "baseline_present": baseline_ok,
        "previous": os.path.abspath(args.previous) if args.previous else None,
        "previous_present": previous_ok,
        "weights_computed": weights_info.get("computed"),
        "weights_expected": EXPECTED_WEIGHTS,
        "weights_ok": weights_info.get("computed") == EXPECTED_WEIGHTS,
        "M5": ("C1: paired unique-token ingest + immediate sanity search"
               if args.cycle == 1 else
               "C2/C3: read-only search for the C1 token; no ingest"),
        "M5_ingest_requested": bool(args.allow_m5_ingest),
        "M4": M4_QUARANTINE,
        "gate": PASS_BAR_TEXT,
        "execute_note": "pass --execute (C1 also needs --allow-m5-ingest)",
    }


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=False)
        f.write("\n")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    guard_zero_hint(argv)
    ap = argparse.ArgumentParser(
        prog="t3r_harness.py",
        description="T3-R retention successor harness. DRY-RUN by default.",
        allow_abbrev=False)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--cycle", type=int, choices=[1, 2, 3], default=1)
    ap.add_argument("--prereg", default=DEFAULT_PREREG)
    ap.add_argument("--baseline", help="C1 json (required for C2/C3)")
    ap.add_argument("--previous", help="immediately preceding cycle json")
    ap.add_argument("--hosts", default=DEFAULT_HOSTS)
    ap.add_argument("--weights-dir", default=DEFAULT_WEIGHTS)
    ap.add_argument("--out", default=None)
    ap.add_argument("--receipts", default=None)
    ap.add_argument("--allow-m5-ingest", action="store_true")
    ap.add_argument("--expect-seal", default=None)
    args = ap.parse_args(argv)

    harness_sha = guard_seal(args.expect_seal)
    if not os.path.exists(args.prereg):
        print("ERROR: pre-registration file missing", file=sys.stderr)
        return 7
    if not os.path.exists(args.hosts):
        print("ERROR: hosts file missing", file=sys.stderr)
        return 7
    if not os.path.exists(ADMIN_TOKEN_FILE):
        print("ERROR: M5 auth file missing ~/eon-tmp/.adm", file=sys.stderr)
        return 7

    hosts = [l.strip() for l in open(args.hosts, encoding="utf-8")
             if l.strip()]
    weights_info = h.weights_hash(args.weights_dir)
    baseline_ok = bool(args.baseline and os.path.exists(args.baseline))
    previous_ok = bool(args.previous and os.path.exists(args.previous))

    if args.cycle in (2, 3):
        if not baseline_ok:
            print("ERROR: C%d requires --baseline C1" % args.cycle,
                  file=sys.stderr)
            return 3
        if args.cycle == 2:
            args.previous = args.previous or args.baseline
        if not args.previous or not os.path.exists(args.previous):
            print("ERROR: C%d requires --previous" % args.cycle,
                  file=sys.stderr)
            return 7
        previous_ok = True
    if args.cycle == 1 and args.allow_m5_ingest is False:
        # Dry-run may show the plan; execute is refused below.
        pass
    if args.cycle in (2, 3) and args.allow_m5_ingest:
        print("ERROR: C2/C3 are read-only; --allow-m5-ingest is C1-only",
              file=sys.stderr)
        return 2

    if not args.execute:
        print(json.dumps(build_plan(args, hosts, weights_info, baseline_ok,
                                    previous_ok, harness_sha), indent=1))
        return 0

    if not args.expect_seal:
        print("ERROR: --execute requires --expect-seal <frozen harness sha>",
              file=sys.stderr)
        return 7
    if args.cycle == 1 and not args.allow_m5_ingest:
        print("ERROR: C1 requires --allow-m5-ingest", file=sys.stderr)
        return 2

    guard_window(args.cycle, args.previous)

    coll = collect_routes(hosts)
    print("PROGRESS routes-done M1=%s M2=%s M3=%s failures=%s"
          % (coll["M1"], coll["M2"], coll["M3"], len(coll["failures"])),
          file=sys.stderr, flush=True)
    baseline_s = None
    if args.cycle in (2, 3):
        baseline_s = json.load(open(args.baseline, encoding="utf-8"))
        baseline_s = baseline_s.get("summary", baseline_s)
    m5 = m5_collect(args.cycle, baseline_s, bool(args.allow_m5_ingest))
    if m5.get("ok") is False and args.cycle == 1:
        print("ERROR [M5]: C1 ingest failed: %s" % m5.get("error"),
              file=sys.stderr)
        # Still write nothing; a failed baseline is not a valid artifact.
        return 1

    out = args.out or os.path.join(
        EPOCH_DIR, {1: "t3r-C1.json", 2: "t3r-C2.json",
                    3: "t3r-C3.json"}[args.cycle])
    if os.path.exists(out):
        print("ERROR: refusing to overwrite %s" % out, file=sys.stderr)
        return 1

    summary = build_summary(args.cycle, coll, m5, weights_info, args.prereg,
                            args.baseline, args.previous, harness_sha)
    receipts_path = args.receipts or (out + ".receipts.json")
    summary["receipts"] = receipts_path
    summary["hosts_path"] = os.path.abspath(args.hosts)
    summary["hosts_sha256"] = sha_file(args.hosts)
    summary["invocation"] = {
        "hosts": os.path.abspath(args.hosts),
        "hosts_sha256": sha_file(args.hosts),
        "out": os.path.abspath(out),
        "cycle": args.cycle,
        "allow_m5_ingest": bool(args.allow_m5_ingest),
    }

    # Coverage is diagnostic only. Final evidence write happens before receipts.
    cov_mod = h.load_coverage_module()
    cov_cyc = cov_mod.compute(out, args.hosts) if cov_mod and os.path.exists(out) else None
    # The out file does not exist yet on the first pass; write first, then compute.
    write_json(out, {"summary": summary, "routes": coll["routes"]})
    cov_cyc = cov_mod.compute(out, args.hosts) if cov_mod else None
    cov_base = None
    if args.cycle in (2, 3) and cov_mod:
        cov_base = cov_mod.compute(args.baseline, args.hosts)
    summary["coverage"] = cov_cyc
    if args.cycle in (2, 3) and baseline_s:
        summary["delta_vs_C1"] = "COMPUTED - see delta_vs_baseline"
        summary["delta_vs_baseline"] = compute_delta(
            baseline_s, summary, weights_info, cov_base, cov_cyc)
    write_json(out, {"summary": summary, "routes": coll["routes"]})

    extra = {
        "epoch": "T3-R",
        "cycle": args.cycle,
        "harness_sha256": harness_sha,
        "preregistration_sha256": sha_file(args.prereg),
        "M4_quarantined": True,
        "M5_auth_lane": M5_AUTH_LANE,
        "zero_hint_owner_attestation": "PENDING (B10)",
    }
    input_paths = [args.prereg, args.hosts]
    if args.baseline:
        input_paths.append(args.baseline)
    if args.previous:
        input_paths.append(args.previous)
    manifest = h.write_receipts([out], input_paths, extra)
    write_json(receipts_path, manifest)

    print(json.dumps({
        "ok": True,
        "epoch": "T3-R",
        "cycle": args.cycle,
        "out": out,
        "out_sha256": sha_file(out),
        "receipts": receipts_path,
        "receipts_sha256": sha_file(receipts_path),
        "M1": summary["M1_live_routes"],
        "M2": summary["M2_distinct_bodies"],
        "M3": summary["M3_phantoms"],
        "M5": summary["M5_retention"],
        "route_coverage": summary["route_coverage"],
        "coverage_count": (summary.get("coverage") or {}).get("coverage_count"),
        "inventory_hosts": (summary.get("coverage") or {}).get("inventory_hosts"),
        "weights_computed": summary.get("weights_hash_computed"),
        "weights_ok": summary.get("weights_hash_reproducible"),
        "delta": summary.get("delta_vs_baseline"),
        "harness_sha256": harness_sha,
        "preregistration_sha256": sha_file(args.prereg),
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
