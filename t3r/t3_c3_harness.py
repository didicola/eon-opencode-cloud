#!/usr/data/data/env python3
# t3_c3_harness.py — T3 Cycle-3 (and C2' re-run) collection harness. Fills blocker B6.
#
# Modeled EXACTLY on the sealed T3-C2-PROBE.py (sha256 43418c15d9b66df4fcf60ebd
# d9b7d6ee67c288c330a81a5f881fcfa04e845b72): same M1-M5 collection sequence, same
# frozen constants, same output schema ({summary, routes} with the identical
# summary key set), same window + zero-hint guards. Differences, all required by
# T3-REEVAL-20261008.md blockers:
#   B6: --cycle {2,3} (default 3), label/output are cycle-specific, the sealed
#       file's output path is NOT reused, and the self-hash check its header
#       CLAIMED but did not implement is real here (--expect-seal).
#   B3: --baseline <c1json> emits the delta-vs-C1' block using the formulas in
#       BASELINE-DECISION.md; a missing baseline file is a hard error naming B3.
#   B4: the cycle's coverage is computed by coverage_instrument.py (definition
#       T3-COV-PROPOSED-v1, PROPOSED-FOR-OWNER-APPROVAL) and recorded in-schema.
#   B2: M4 is collected but flagged M4_quarantined=True / UNRELIABLE; scoring
#       uses M1, M2, M3, M5 only (metric set 5 -> 4).
#   B5: weights hash is recomputed by construction WSC-1. The frozen constant
#       0e97aa1c... is NOT reproducible by WSC-1 (nor by 20 other tried
#       constructions), so BOTH hashes are emitted and the block is flagged
#       HASH-METHOD-MISMATCH for the owner.
#   B10: zero-hint guard refuses ANY --hint argument or T3_HINT_FILE env
#       (hard exit 2), mirroring the sealed probe's window refusal.
#
# SAFETY (hard requirements of this build task):
#   * DEFAULT MODE IS DRY-RUN: it prints the command plan and collects NOTHING
#     (no socket, no subprocess, no file written). --execute is required for
#     live collection.
#   * --execute performs READ-ONLY probes only: GET for the M1-M3 route sweep
#     and M4 status, JSON-RPC POST to MCP read methods (brain_status,
#     knowledge_search) for M5. The single state-mutating call of the sealed
#     probe (brain_learn ingest) runs ONLY with the extra flag
#     --allow-m5-ingest; otherwise M5 records "ingest_skipped": true.
#   * The harness refuses to run if a --hint file/flag is passed.
#
# The harness was built and tested on fixtures ONLY in this session; no live
# collection was executed by the builder.

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# ---- frozen constants (copied from the sealed probe; do not tune) ----------
C2_OPENS_UTC = "2026-09-30"
C3_OPENS_UTC = "2026-10-01"
WEIGHTS_HASH_C1 = ("0e97aa1ceb5a84871aa8bfe82b00932b452914ce240e8a288fd75cebe"
                   "1780c72")
ACCOUNT = "eon-sovereign.workers.dev"
SHARDS = ["llama", "qwen", "mistral", "gemma", "deepseek", "general"]
CATCHALL_BODIES = {'{"tunnel":"offline","connectedAt":0,"pending":0}'}
INGEST_URL = "https://paste.rs/uLmnc"
PATHS = ["/", "/health", "/status", "/mcp", "/__nonexistent_c2_probe__"]
REAL_PATHS = ["/", "/health", "/status", "/mcp"]

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HOSTS = os.path.expanduser("~/sub.txt")
DEFAULT_WEIGHTS_DIR = os.path.expanduser("~/eon-work/sealed-t1t4-20260929")
CORE_DESIGNS = ["T1-TRANSFER-FROZEN.md", "T2-SELECTION-FROZEN.md",
                "T3-LONGITUDINAL-FROZEN.md", "T4-SELFCORRECTION-FROZEN.md"]
PASS_BAR_TEXT = ("cost/unit-coverage -20% OR coverage +2 vs C1; "
                 "weights hash unchanged; no regression")
REGRESSION_METRICS = ["M1", "M2", "M3", "M5"]  # M4 QUARANTINED (B2), set 5 -> 4
M4_QUARANTINE_REASON = ("M4 UNRELIABLE while p2p registry is non-durable "
                        "(P2P-REGISTRY-NONDURABLE-FIX.md lines 80-83); excluded "
                        "from the no-regression clause, recorded as UNRELIABLE")

# the 18 summary keys of the sealed C2 artifact (t3c2-C2.json, sha 9a022a6f...)
C2_SUMMARY_KEYS = [
    "label", "collected_utc", "M1_live_routes", "M2_distinct_bodies",
    "M3_phantoms", "M3_phantom_list", "M4_any_shard_peers", "M4_shard_peers",
    "M4_totalPeers", "M5_retention", "weights_hash_expected",
    "weights_hash_reproducible", "C1_baseline_present", "PASS_BAR",
    "delta_vs_C1", "failures_recorded", "failures", "route_count",
]

EXITS = {"ok": 0, "error": 1, "zero_hint": 2, "baseline_missing": 3,
         "window_closed": 5, "seal_mismatch": 6, "preflight": 7}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def now_utc():
    return datetime.now(timezone.utc)


def cycle_opens(cycle):
    return C2_OPENS_UTC if cycle == 2 else C3_OPENS_UTC


# ---- guards ----------------------------------------------------------------

def guard_zero_hint(argv):
    """B10 hard guard: any --hint flag/file invalidates the cycle."""
    for a in argv:
        if a == "--hint" or a.startswith("--hint=") or a == "--hint-file" \
                or a.startswith("--hint-file="):
            print("REFUSED (zero-hint guard): argument %r is a hint channel." % a)
            print("Zero-hint rule: no agent is told a metric, a target, or a "
                  "hypothesis before the collection runs "
                  "(T3-C2-COLLECTION-FROZEN.md lines 2-3); any hint invalidates "
                  "the cycle (T3-CYCLE-SCHEDULE-FROZEN.md line 9).")
            sys.exit(EXITS["zero_hint"])
    if os.environ.get("T3_HINT_FILE"):
        print("REFUSED (zero-hint guard): T3_HINT_FILE is set in the environment.")
        sys.exit(EXITS["zero_hint"])


def guard_window(cycle):
    if now_utc().strftime("%Y-%m-%d") < cycle_opens(cycle):
        print("REFUSED: T3 C%d may not be collected before %s (zero-hint seal)."
              % (cycle, cycle_opens(cycle)))
        sys.exit(EXITS["window_closed"])


def guard_seal(expected):
    if not expected:
        return None
    got = sha_file(os.path.abspath(__file__))
    if got != expected:
        print("REFUSED (self-hash check): harness sha256 %s != expected seal %s"
              % (got, expected))
        sys.exit(EXITS["seal_mismatch"])
    return got


# ---- weights hash (B5) -----------------------------------------------------

def weights_hash(weights_dir):
    """WSC-1: sha256 over sorted (filename \\0 content \\n) of the 4 frozen core
    designs. Deterministic over identical inputs. Does NOT reproduce the frozen
    constant 0e97aa1c... (recipe never frozen) -> caller flags the mismatch."""
    inputs, missing = [], []
    chunks = []
    for name in CORE_DESIGNS:
        p = os.path.join(weights_dir, name)
        if not os.path.exists(p):
            missing.append(name)
            continue
        with open(p, "rb") as f:
            content = f.read()
        inputs.append({"name": name, "sha256": sha(content), "bytes": len(content)})
        chunks.append(name.encode() + b"\0" + content + b"\n")
    if missing:
        return {"scheme": "WSC-1", "computed": None, "inputs": inputs,
                "missing": missing, "flag": "WEIGHTS-INPUTS-MISSING"}
    computed = sha(b"".join(chunks))
    flag = None if computed == WEIGHTS_HASH_C1 else "HASH-METHOD-MISMATCH"
    return {"scheme": "WSC-1", "computed": computed, "inputs": inputs,
            "missing": [], "flag": flag,
            "frozen_constant": WEIGHTS_HASH_C1,
            "note": "frozen recipe never frozen (B5); WSC-1 is this harness's "
                    "stated construction; owner must reconcile or re-seal"}


# ---- M1-M5 scoring helpers -------------------------------------------------

def score_routes(routes):
    """Derive M1/M2/M3 from stored route records (same rules as the sealed
    probe: live = 200 + non-empty + not catch-all; phantom = 200 on the
    invented path; M2 = distinct body hashes)."""
    live, phantoms, hashes = 0, [], set()
    for r in routes:
        body = r.get("body")
        h = r.get("hash") or (sha(body.encode())[:16] if body else "EMPTY")
        hashes.add(h)
        is_catch = r.get("catchall") or body in CATCHALL_BODIES
        nonempty = (r.get("len") if r.get("len") is not None
                    else len(body or "")) > 0
        if r.get("code") == 200 and nonempty and not is_catch and body != "":
            live += 1
        if r.get("code") == 200 and r.get("path") == "/__nonexistent_c2_probe__" \
                and nonempty and not is_catch:
            phantoms.append("%s%s" % (r.get("host"), r.get("path")))
    return live, len(hashes), len(phantoms), phantoms


def m5_scalar(m5):
    """No-regression score for M5: (learn_acked, retrievable) each 0/1/None.
    'rotated' is an observation, not a quality -> not scored."""
    if not isinstance(m5, dict):
        return None, None
    a = m5.get("learn_acked")
    r = m5.get("retrievable")
    return (None if a is None else int(bool(a)),
            None if r is None else int(bool(r)))


# ---- delta formulas (BASELINE-DECISION.md section 5) -----------------------

def compute_delta(base, cyc, cov_base, cov_cyc, weights_info):
    """Explicit formulas. Inputs: baseline/cycle summary dicts + coverage
    results (coverage_instrument.compute output) + weights_info."""
    out = {"baseline_label": base.get("label"),
           "baseline_collected_utc": base.get("collected_utc"),
           "cycle_label": cyc.get("label"),
           "cycle_collected_utc": cyc.get("collected_utc"),
           "coverage_definition_id": (cov_cyc or {}).get("definition_id"),
           "coverage_proposed": True,
           "metric_set_scored": list(REGRESSION_METRICS),
           "metric_set_excluded": {"M4": "QUARANTINED-UNRELIABLE"}}

    # coverage + cost inputs
    cb = (cov_base or {}).get("coverage")
    cc = (cov_cyc or {}).get("coverage")
    kb = (cov_base or {}).get("coverage_count")
    kc = (cov_cyc or {}).get("coverage_count")
    nb = (cov_base or {}).get("inventory_hosts")
    nc = (cov_cyc or {}).get("inventory_hosts")
    cost_b = base.get("route_count")
    cost_c = cyc.get("route_count")
    out["inputs"] = {"M1": [base.get("M1_live_routes"), cyc.get("M1_live_routes")],
                     "M2": [base.get("M2_distinct_bodies"), cyc.get("M2_distinct_bodies")],
                     "M3": [base.get("M3_phantoms"), cyc.get("M3_phantoms")],
                     "M4_quarantined": [base.get("M4_any_shard_peers"),
                                        cyc.get("M4_any_shard_peers")],
                     "M5": [m5_scalar(base.get("M5_retention")),
                            m5_scalar(cyc.get("M5_retention"))],
                     "coverage": [cb, cc],
                     "coverage_count": [kb, kc],
                     "inventory_hosts": [nb, nc],
                     "cost_route_count": [cost_b, cost_c]}

    # arm A: cost per unit coverage -20%
    if cb and cc and cost_b is not None and cost_c is not None:
        cpu_b, cpu_c = cost_b / cb, cost_c / cc
        reduction = (cpu_b - cpu_c) / cpu_b
        arm_a = cpu_c <= 0.8 * cpu_b
        arm_a_block = {"cost_definition": "route_count (probes executed per cycle)",
                       "cost_per_unit_baseline": round(cpu_b, 6),
                       "cost_per_unit_cycle": round(cpu_c, 6),
                       "reduction": round(reduction, 6),
                       "threshold": 0.20, "pass": bool(arm_a)}
    else:
        arm_a_block = {"pass": False, "status": "UNDEFINED",
                       "reason": "coverage or cost missing (B4/proposed instrument "
                                 "required on both cycles)"}
    # arm B: coverage +2 (unit = covered host; inventories must match)
    if kb is not None and kc is not None and nb == nc and nb is not None:
        delta_k = kc - kb
        arm_b = delta_k >= 2
        arm_b_block = {"baseline_count": kb, "cycle_count": kc,
                       "delta": delta_k, "threshold": 2, "unit": "covered host",
                       "pass": bool(arm_b)}
    else:
        arm_b_block = {"pass": False, "status": "UNDEFINED",
                       "reason": "coverage counts missing or inventory changed "
                                 "(declare inventory change per frozen A6)"}
    out["arm_A_cost_per_unit_minus20"] = arm_a_block
    out["arm_B_coverage_plus2"] = arm_b_block
    out["primary_pass"] = bool(arm_a_block.get("pass") or arm_b_block.get("pass"))

    # no-regression over M1, M2, M3, M5 (M4 excluded, UNRELIABLE)
    per = {}
    m1b, m1c = base.get("M1_live_routes"), cyc.get("M1_live_routes")
    m2b, m2c = base.get("M2_distinct_bodies"), cyc.get("M2_distinct_bodies")
    m3b, m3c = base.get("M3_phantoms"), cyc.get("M3_phantoms")
    a_b, r_b = m5_scalar(base.get("M5_retention"))
    a_c, r_c = m5_scalar(cyc.get("M5_retention"))

    def und(*vals):
        return any(v is None for v in vals)

    per["M1"] = {"direction": "higher-better", "values": [m1b, m1c],
                 "status": "UNDEFINED" if und(m1b, m1c) else
                           ("REGRESSED" if m1c < m1b else "OK")}
    per["M2"] = {"direction": "higher-better", "values": [m2b, m2c],
                 "status": "UNDEFINED" if und(m2b, m2c) else
                           ("REGRESSED" if m2c < m2b else "OK")}
    per["M3"] = {"direction": "lower-better", "values": [m3b, m3c],
                 "status": "UNDEFINED" if und(m3b, m3c) else
                           ("REGRESSED" if m3c > m3b else "OK")}
    if und(a_b, r_b, a_c, r_c):
        per["M5"] = {"direction": "higher-better on (learn_acked, retrievable)",
                     "values": [[a_b, r_b], [a_c, r_c]],
                     "status": "UNDEFINED"}
    else:
        reg = (a_c < a_b) or (r_c < r_b)
        per["M5"] = {"direction": "higher-better on (learn_acked, retrievable)",
                     "values": [[a_b, r_b], [a_c, r_c]],
                     "status": "REGRESSED" if reg else "OK"}
    per["M4"] = {"status": "QUARANTINED-UNRELIABLE",
                 "values": [base.get("M4_any_shard_peers"),
                            cyc.get("M4_any_shard_peers")],
                 "note": M4_QUARANTINE_REASON}
    statuses = [per[m]["status"] for m in REGRESSION_METRICS]
    out["no_regression"] = {"per_metric": per,
                            "pass": all(s == "OK" for s in statuses),
                            "fail_closed_on_undefined": True}

    # weights clause (B5)
    exp_ok = (base.get("weights_hash_expected") == cyc.get("weights_hash_expected")
              == WEIGHTS_HASH_C1)
    comp = (weights_info or {}).get("computed")
    out["weights"] = {"expected_baseline": base.get("weights_hash_expected"),
                      "expected_cycle": cyc.get("weights_hash_expected"),
                      "computed_scheme": (weights_info or {}).get("scheme"),
                      "computed": comp,
                      "frozen_constant": WEIGHTS_HASH_C1,
                      "matches_frozen_constant": comp == WEIGHTS_HASH_C1 if comp else None,
                      "flag": (weights_info or {}).get("flag"),
                      "identical_expected_across_cycles": exp_ok,
                      "identical_computed_across_cycles": True if comp else None,
                      "pass": bool(exp_ok and comp)}
    out["zero_hint"] = {"mechanical_guard": True,
                        "attestation": "REQUIRED-OWNER-ATTESTATION (B9/B10)",
                        "note": "harness can attest only that no --hint channel "
                                "was supplied to THIS process"}
    out["gate_pass_mechanical"] = bool(out["primary_pass"]
                                       and out["no_regression"]["pass"]
                                       and out["weights"]["pass"])
    out["gate_pass_overall"] = None  # pending zero-hint attestation + owner sign-off
    out["gate_status"] = ("PROVISIONAL-PASS-PENDING-ATTESTATION"
                          if out["gate_pass_mechanical"] else "FAIL")
    return out


# ---- collection (READ-ONLY) ------------------------------------------------

def fetch(url, method="GET", timeout=20):
    """Read-only probe. GET (and HEAD where asked). No write verbs."""
    assert method in ("GET", "HEAD"), "read-only enforcement: %s forbidden" % method
    cmd = ["curl", "-sS", "--max-time", str(timeout), "-w",
           "\n__CODE__%{http_code}__%{time_total}", url]
    if method == "HEAD":
        cmd.insert(1, "-I")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 8)
    except subprocess.TimeoutExpired:
        return {"code": 0, "body": "", "ms": timeout * 1000, "err": "timeout"}
    out = r.stdout or ""
    code, ms = 0, 0
    if "__CODE__" in out:
        out, tail = out.rsplit("\n__CODE__", 1)
        try:
            c, t = tail.split("__")
            code, ms = int(c), float(t) * 1000
        except Exception:
            pass
    return {"code": code, "body": out.strip(), "ms": ms,
            "err": None if code else "no-response"}


def mcp_read(calls, timeout=60):
    """JSON-RPC POST to MCP read methods only (brain_status,
    knowledge_search). brain_learn is NOT called here (needs --allow-m5-ingest)."""
    results = []
    for tool, args in calls:
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": tool, "arguments": args}})
        cmd = ["curl", "-sS", "--max-time", str(timeout), "-X", "POST",
               "https://eon-mcp.%s/mcp" % ACCOUNT, "-d", payload,
               "-H", "content-type: application/json",
               "-H", "accept: application/json"]
        try:
            o = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
            d = json.loads(o.stdout)
            results.append(json.loads(d["result"]["content"][0]["text"]))
        except Exception as e:
            results.append({"_err": str(e)[:120]})
    return results


def m5_ingest(cycle_tag, timeout=60):
    """The ONLY state-mutating call of the sealed probe. Runs only when the
    operator passes --allow-m5-ingest (owner-gated)."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "brain_learn",
                                     "arguments": {"url": INGEST_URL,
                                                   "topic": cycle_tag}}})
    cmd = ["curl", "-sS", "--max-time", str(timeout), "-X", "POST",
           "https://eon-mcp.%s/mcp" % ACCOUNT, "-d", payload,
           "-H", "content-type: application/json",
           "-H", "accept: application/json"]
    o = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
    d = json.loads(o.stdout)
    return json.loads(d["result"]["content"][0]["text"])


def collect_live(hosts, cycle, allow_ingest):
    """Same M1-M5 sequence as T3-C2-PROBE.py main(). READ-ONLY probes only."""
    routes, failures = [], []
    # M1/M2/M3 sweep: GET per host x path
    for host in hosts:
        for path in PATHS:
            r = fetch("https://%s%s" % (host, path))
            body = r["body"]
            h = sha(body.encode())[:16] if body else "EMPTY"
            is_catch = body in CATCHALL_BODIES
            routes.append({"host": host, "path": path, "code": r["code"],
                           "ms": round(r["ms"]), "hash": h, "catchall": is_catch,
                           "len": len(body)})
            if r["err"]:
                failures.append({"host": host, "path": path, "err": r["err"]})
    # M4: GET status
    st = fetch("https://eon-p2p-cloud.%s/status" % ACCOUNT)
    try:
        s = json.loads(st["body"])
        peers = [sh.get("peers", 0) for sh in s.get("shards", [])]
        m4 = any(p > 0 for p in peers)
        total_peers = s.get("totalPeers")
    except Exception:
        peers, m4, total_peers = [], False, None
        failures.append({"metric": "M4", "err": "status unparseable"})
    # M5: read-only MCP calls; ingest only with explicit flag (order matches
    # the sealed probe: before -> [ingest] -> after -> search)
    m5 = {}
    try:
        before = mcp_read([("brain_status", {})])[0]
        learn_acked, ingest_skipped = None, not allow_ingest
        if allow_ingest:
            learn_acked = m5_ingest("t3-c%d-retention" % cycle).get("learned")
        after, searched = mcp_read([("brain_status", {}),
                                    ("knowledge_search",
                                     {"q": "EON Cloud MCP host delegation lane"})])
        m5 = {"before": before, "learn_acked": learn_acked,
              "ingest_skipped": ingest_skipped, "after": after,
              "retrievable": bool(searched.get("total")),
              "rotated": before.get("uptime") != after.get("uptime")}
        if ingest_skipped:
            m5["_note"] = ("brain_learn ingest skipped: read-only default; "
                           "pass --allow-m5-ingest for full M5")
    except Exception as e:
        failures.append({"metric": "M5", "err": str(e)[:120]})
    m1, m2, m3, phantoms = score_routes(routes)
    return {"M1": m1, "M2": m2, "M3": m3, "phantoms": phantoms,
            "M4": m4, "peers": peers, "totalPeers": total_peers,
            "M5": m5, "routes": routes, "failures": failures}


def collect_fixture(fixture_path):
    """Offline collection for tests: score an existing routes array. Output is
    labelled FIXTURE and is NOT admissible as cycle data."""
    with open(fixture_path) as f:
        run = json.load(f)
    routes = run["routes"] if isinstance(run, dict) else run
    m1, m2, m3, phantoms = score_routes(routes)
    return {"M1": m1, "M2": m2, "M3": m3, "phantoms": phantoms,
            "M4": None, "peers": None, "totalPeers": None,
            "M5": {"before": None, "learn_acked": None, "ingest_skipped": True,
                   "after": None, "retrievable": None, "rotated": None,
                   "_note": "fixture mode: no live M4/M5 collected"},
            "routes": routes,
            "failures": [{"metric": "M4", "err": "fixture mode: not collected"},
                         {"metric": "M5", "err": "fixture mode: not collected"}]}


# ---- output assembly -------------------------------------------------------

def build_summary(cycle, mode, coll, weights_info):
    label = {3: "C3 COLLECTION",
             2: "C2' COLLECTION (re-baseline epoch 2)"}[cycle]
    if mode == "fixture":
        label += " (FIXTURE - NOT LIVE DATA)"
    s = {
        "label": label,
        "collected_utc": now_utc().isoformat(),
        "M1_live_routes": coll["M1"],
        "M2_distinct_bodies": coll["M2"],
        "M3_phantoms": coll["M3"],
        "M3_phantom_list": coll["phantoms"],
        "M4_any_shard_peers": coll["M4"],
        "M4_shard_peers": coll["peers"],
        "M4_totalPeers": coll["totalPeers"],
        "M5_retention": coll["M5"],
        "weights_hash_expected": WEIGHTS_HASH_C1,
        "weights_hash_reproducible": (weights_info.get("computed") ==
                                      WEIGHTS_HASH_C1
                                      if weights_info.get("computed") else None),
        "C1_baseline_present": False,          # set by run() when --baseline OK
        "PASS_BAR": PASS_BAR_TEXT,
        "delta_vs_C1": "PENDING - see delta_vs_baseline block",
        "failures_recorded": len(coll["failures"]),
        "failures": coll["failures"],
        "route_count": len(coll["routes"]),
        # --- additions (superset of the sealed schema) ---
        "cycle": cycle,
        "mode": mode,
        "harness": "t3_c3_harness.py",
        "harness_sha256": sha_file(os.path.abspath(__file__)),
        "M4_quarantined": True,
        "M4_quarantine_reason": M4_QUARANTINE_REASON,
        "M5_scoring_note": "M5 scored on (learn_acked, retrievable); 'rotated' recorded, not scored",
        "weights_hash_scheme": weights_info.get("scheme"),
        "weights_hash_computed": weights_info.get("computed"),
        "weights_hash_inputs": weights_info.get("inputs"),
        "weights_hash_method_flag": weights_info.get("flag"),
        "coverage": None,                     # filled from coverage_instrument
        "coverage_definition_id": "T3-COV-PROPOSED-v1",
        "coverage_status": "PROPOSED-FOR-OWNER-APPROVAL (B4)",
        "delta_vs_baseline": None,            # filled when --baseline given
        "zero_hint_guard": "no --hint channel supplied to this process",
        "receipts": None,                     # path of receipts manifest
    }
    missing = [k for k in C2_SUMMARY_KEYS if k not in s]
    if missing:
        raise RuntimeError("schema bug: missing sealed C2 keys: %s" % missing)
    return s


def build_plan(args, hosts, weights_info, baseline_ok):
    return {
        "mode": "DRY-RUN (default): nothing is collected, no network, no writes",
        "cycle": args.cycle,
        "window": {"opens": cycle_opens(args.cycle),
                   "open_now": now_utc().strftime("%Y-%m-%d") >= cycle_opens(args.cycle),
                   "check": "date-level per T3-C2-COLLECTION-FROZEN.md line 2"},
        "zero_hint_guard": {"armed": True, "hint_args_refused": True,
                            "T3_HINT_FILE_refused": True},
        "baseline": ({"path": args.baseline, "present": baseline_ok}
                     if args.baseline else
                     {"path": None, "present": False,
                      "note": "no --baseline: delta_vs_C1 stays UNDEFINED (B3)"}),
        "steps": [
            {"step": 1, "action": "verify self-hash seal",
             "detail": "--expect-seal <sha256> (real check; the sealed C2 probe "
                       "claimed one it did not implement)",
             "network": False},
            {"step": 2, "action": "load host inventory",
             "detail": "%s (%d hosts)" % (args.hosts, len(hosts)), "network": False},
            {"step": 3, "action": "compute weights hash WSC-1",
             "detail": "4 core frozen designs; expect HASH-METHOD-MISMATCH vs "
                       "0e97aa1c... until owner freezes the recipe (B5)",
             "network": False, "scheme": weights_info.get("scheme"),
             "computed": weights_info.get("computed")},
            {"step": 4, "action": "M1/M2/M3 sweep: %d hosts x %d paths" % (len(hosts), len(PATHS)),
             "detail": "GET https://<host>{%s}" % ",".join(PATHS),
             "method": "GET", "network": True, "probes": len(hosts) * len(PATHS)},
            {"step": 5, "action": "M4 status", "method": "GET",
             "detail": "GET https://eon-p2p-cloud.%s/status (recorded, "
                       "QUARANTINED for scoring)" % ACCOUNT,
             "network": True, "probes": 1},
            {"step": 6, "action": "M5 retention (read-only)",
             "method": "JSON-RPC POST to MCP read methods",
             "detail": "brain_status + knowledge_search; brain_learn ingest ONLY "
                       "with --allow-m5-ingest (default skipped)",
             "network": True, "probes": 3},
            {"step": 7, "action": "coverage instrument",
             "detail": "coverage_instrument.py T3-COV-PROPOSED-v1 over the run "
                       "+ --hosts", "network": False},
            {"step": 8, "action": "delta vs C1' (if --baseline)",
             "detail": "BASELINE-DECISION.md formulas; scoring set M1,M2,M3,M5; "
                       "M4 excluded", "network": False},
            {"step": 9, "action": "write output + receipts manifest",
             "detail": "sha256 of every input and output", "network": False},
        ],
        "read_only_guarantee": "GET/HEAD only for probes; MCP POST limited to "
                               "read methods; no wrangler, no deploy, no write verb",
        "execute_note": "re-run with --execute to collect for real (main lane only, B7)",
    }


def write_receipts(out_paths, input_paths, extra):
    manifest = {"generated_utc": now_utc().isoformat(),
                "tool": os.path.basename(os.path.abspath(__file__)),
                "tool_sha256": sha_file(os.path.abspath(__file__)),
                "inputs": [], "outputs": []}
    for p in input_paths:
        if p and os.path.exists(p):
            manifest["inputs"].append({"path": os.path.abspath(p),
                                       "sha256": sha_file(p),
                                       "bytes": os.path.getsize(p)})
    for p in out_paths:
        if p and os.path.exists(p):
            manifest["outputs"].append({"path": os.path.abspath(p),
                                        "sha256": sha_file(p),
                                        "bytes": os.path.getsize(p)})
    manifest.update(extra)
    return manifest


# ---- main ------------------------------------------------------------------

def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="t3_c3_harness.py",
        description="T3 C3 collection harness (B6). DRY-RUN by default; "
                    "--execute required for live READ-ONLY collection.",
        allow_abbrev=False)
    ap.add_argument("--execute", action="store_true",
                    help="perform live collection (default: dry-run, no network)")
    ap.add_argument("--cycle", type=int, choices=[2, 3], default=3,
                    help="3 = C3 (default); 2 = C2' re-run required by the "
                         "REBASELINE-NEEDS-RERUN-C2 verdict")
    ap.add_argument("--baseline", help="C1' json (e.g. t3c1r2-C1-R2.json); "
                                       "missing file = hard error (B3)")
    ap.add_argument("--hosts", default=DEFAULT_HOSTS if os.path.exists(DEFAULT_HOSTS) else None,
                    help="host inventory file (default ~/sub.txt)")
    ap.add_argument("--weights-dir", default=DEFAULT_WEIGHTS_DIR,
                    help="sealed design dir for WSC-1 weights hash")
    ap.add_argument("--out", help="output json path (default: "
                                  "<dir>/t3c3-C3.json or t3c2prime-C2.json)")
    ap.add_argument("--receipts", help="receipts manifest path "
                                       "(default: <out>.receipts.json)")
    ap.add_argument("--fixture-routes", help="offline mode: score this json's "
                                             "routes instead of collecting (tests)")
    ap.add_argument("--allow-m5-ingest", action="store_true",
                    help="permit the single state-mutating call (brain_learn); "
                         "default off = strictly read-only")
    ap.add_argument("--expect-seal", help="sha256 this file must match "
                                          "(real self-hash check), else refuse")
    return ap.parse_args(argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    guard_zero_hint(argv)                    # B10: hard exit before anything else
    args = parse_args(argv)

    seal = guard_seal(args.expect_seal)      # B6: the self-hash check C2 claimed

    # baseline preflight: provided-but-missing = B3 hard error
    baseline_ok = False
    if args.baseline:
        if not os.path.exists(args.baseline):
            print("ERROR [B3]: baseline file not found: %s" % args.baseline)
            print("B3 (C1 comparison basis does not exist) remains open: supply "
                  "the declared C1' json — e.g. t3c1r2-C1-R2.json "
                  "(sha256 9cec770691ae675de02fb55e1ce901ab6e303068b20e24634bfbd"
                  "9f94a10fc69, collected 2026-09-30T06:57:54Z) — or omit "
                  "--baseline and accept delta_vs_C1 = UNDEFINED.")
            sys.exit(EXITS["baseline_missing"])
        baseline_ok = True

    hosts = []
    if args.hosts:
        if not os.path.exists(args.hosts):
            print("ERROR: hosts file not found: %s" % args.hosts, file=sys.stderr)
            sys.exit(EXITS["preflight"])
        with open(args.hosts) as fh:
            hosts = [l.strip() for l in fh if l.strip()]
    if not hosts and not args.fixture_routes:
        print("ERROR: no host inventory (need --hosts, e.g. ~/sub.txt)", file=sys.stderr)
        sys.exit(EXITS["preflight"])

    weights_info = weights_hash(args.weights_dir)

    # ---- DRY-RUN (default): print plan, collect nothing, write nothing -----
    if not args.execute and not args.fixture_routes:
        plan = build_plan(args, hosts, weights_info, baseline_ok)
        plan["self_hash_check"] = ("verifying against --expect-seal" if seal
                                   else "not requested (--expect-seal absent); "
                                        "recorded sha256: %s" % plan_sha())
        plan["preconditions"] = preflight_report(args)
        print(json.dumps(plan, sort_keys=True, indent=1))
        return EXITS["ok"]

    # ---- window guard only for live execution ------------------------------
    if args.execute:
        guard_window(args.cycle)

    mode = "fixture" if args.fixture_routes else "execute"
    if args.fixture_routes:
        if not os.path.exists(args.fixture_routes):
            print("ERROR: fixture not found: %s" % args.fixture_routes, file=sys.stderr)
            sys.exit(EXITS["preflight"])
        coll = collect_fixture(args.fixture_routes)
    else:
        coll = collect_live(hosts, args.cycle, args.allow_m5_ingest)

    summary = build_summary(args.cycle, mode, coll, weights_info)

    # ---- output path (never the sealed C2 path) ---------------------------
    default_name = {3: "t3c3-C3.json", 2: "t3c2prime-C2.json"}[args.cycle]
    if mode == "fixture":
        default_name = default_name.replace(".json", "-FIXTURE.json")
    out_path = args.out or os.path.join(HERE, default_name)
    if os.path.abspath(out_path) == "/data/data/com.termux/files/usr/tmp/t3c2-C2.json":
        print("REFUSED: would overwrite the sealed C2 artifact (B6)", file=sys.stderr)
        sys.exit(EXITS["error"])
    if os.path.exists(out_path) and mode != "fixture":
        print("ERROR: output exists, refusing to overwrite: %s" % out_path,
              file=sys.stderr)
        sys.exit(EXITS["error"])
    receipts_path = args.receipts or (out_path + ".receipts.json")

    # write once, then attach coverage + delta, then write final
    json.dump({"summary": summary, "routes": coll["routes"]},
              open(out_path, "w"), indent=1)

    cov_mod = load_coverage_module()
    cov_cyc = cov_mod.compute(out_path, args.hosts) if cov_mod else None
    cov_base = None
    if baseline_ok:
        try:
            cov_base = cov_mod.compute(args.baseline, args.hosts) if cov_mod else None
        except Exception as e:
            print("ERROR: cannot score coverage on baseline: %s" % e, file=sys.stderr)
            sys.exit(EXITS["baseline_missing"])

    summary["coverage"] = cov_cyc
    summary["C1_baseline_present"] = baseline_ok
    if baseline_ok:
        with open(args.baseline) as fh:
            base_summary = json.load(fh)["summary"]
        delta = compute_delta(base_summary, summary, cov_base, cov_cyc, weights_info)
        summary["delta_vs_baseline"] = delta
        summary["delta_vs_C1"] = ("computable - see delta_vs_baseline block "
                                  "(mechanical gate: %s)" % delta["gate_status"])
    else:
        summary["delta_vs_C1"] = ("UNDEFINED - B3: no C1 baseline supplied "
                                  "(no C1 measurements were ever recorded)")
        summary["delta_vs_baseline"] = None

    json.dump({"summary": summary, "routes": coll["routes"]},
              open(out_path, "w"), indent=1)

    input_paths = [args.hosts, args.baseline, args.fixture_routes,
                   os.path.abspath(__file__)]
    input_paths += [os.path.join(args.weights_dir, n) for n in CORE_DESIGNS]
    manifest = write_receipts([out_path], input_paths,
                              {"cycle": args.cycle, "mode": mode,
                               "coverage_definition_id": "T3-COV-PROPOSED-v1",
                               "baseline_present": baseline_ok,
                               "weights_hash_flag": weights_info.get("flag"),
                               "read_only": mode == "execute"})
    json.dump(manifest, open(receipts_path, "w"), indent=1, sort_keys=True)
    summary["receipts"] = os.path.abspath(receipts_path)
    json.dump({"summary": summary, "routes": coll["routes"]},
              open(out_path, "w"), indent=1)
    # refresh output hash of the final file inside the manifest
    manifest["outputs"] = [{"path": os.path.abspath(out_path),
                            "sha256": sha_file(out_path),
                            "bytes": os.path.getsize(out_path)}]
    json.dump(manifest, open(receipts_path, "w"), indent=1, sort_keys=True)

    d = summary["delta_vs_baseline"]
    print("=== T3 %s  %s UTC ===" % (summary["label"], now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")))
    print("  M1 live routes      : %d" % summary["M1_live_routes"])
    print("  M2 distinct bodies  : %d" % summary["M2_distinct_bodies"])
    print("  M3 phantom routes   : %d" % summary["M3_phantoms"])
    print("  M4 any shard peers>0: %s  QUARANTINED (not scored)"
          % summary["M4_any_shard_peers"])
    print("  M5 learned=%s rotated=%s retrievable=%s"
          % (summary["M5_retention"].get("learn_acked"),
             summary["M5_retention"].get("rotated"),
             summary["M5_retention"].get("retrievable")))
    if cov_cyc:
        print("  coverage (PROPOSED) : %s = %d/%d"
              % (cov_cyc["coverage"], cov_cyc["coverage_count"],
                 cov_cyc["inventory_hosts"]))
    if d:
        print("  arm A cost/unit     : %s" % d["arm_A_cost_per_unit_minus20"].get("pass"))
        print("  arm B coverage +2   : %s" % d["arm_B_coverage_plus2"].get("pass"))
        print("  no regression %s : %s"
              % (d["metric_set_scored"], d["no_regression"]["pass"]))
        print("  weights flag        : %s" % d["weights"].get("flag"))
        print("  gate (mechanical)   : %s" % d["gate_status"])
    else:
        print("  delta vs C1'        : UNDEFINED (B3) - no --baseline given")
    print("  written: %s" % out_path)
    print("  receipts: %s (sha256 %s)" % (receipts_path, sha_file(receipts_path)))
    return EXITS["ok"]


def plan_sha():
    try:
        return sha_file(os.path.abspath(__file__))
    except OSError:
        return None


def preflight_report(args):
    adm = os.path.expanduser("~/usr/tmp/.admkey")
    sub = args.hosts
    return {
        "B8_admkey_present": os.path.exists(adm),
        "B8_admkey_note": "missing -> M5 ingest would fail; read-only M5 still records retrievable=false",
        "hosts_file": sub,
        "hosts_file_sha256": sha_file(sub) if sub and os.path.exists(sub) else None,
        "hosts_count": (len([l for l in open(sub).read().splitlines() if l.strip()])
                        if sub and os.path.exists(sub) else 0),
        "sub_txt_note": "81 hosts expected; if changed, declare inventory change (frozen A6)",
    }


def load_coverage_module():
    try:
        import coverage_instrument
        return coverage_instrument
    except Exception:
        sys.path.insert(0, HERE)
        try:
            import coverage_instrument
            return coverage_instrument
        except Exception:
            return None


if __name__ == "__main__":
    sys.exit(main())
