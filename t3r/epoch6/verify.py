#!/usr/bin/env python3
"""Read-only T3-R epoch-6 verifier.

Implements the frozen T3-R retention bar against a fresh C1/C2/C3 set.
It never writes evidence, never calls MCP, and never dispatches a run.

The epoch-5 verifier required exact equality of knowledge counts between C2
and C3. The frozen bar only requires knowledge non-regression (K_before >=
K1_after). This verifier implements the bar and records non-decreasing reads;
it does not carry forward the extra exact-equality check. It also applies the
same no-regression/failure checks to C2 and C3, as the pre-registration states.

Usage:
  python3 verify.py
  python3 verify.py --c1 ... --c2 ... --c3 ... --prereg ... --hosts ...

Exit codes: 0 all checks pass; 1 one or more checks fail; 2 input missing.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T3R = os.path.dirname(HERE)
REPO = os.path.dirname(T3R)
EVID = os.path.join(T3R, "evidence", "epoch6")

DEFAULT_C1 = os.path.join(EVID, "t3r-C1.json")
DEFAULT_C2 = os.path.join(EVID, "t3r-C2.json")
DEFAULT_C3 = os.path.join(EVID, "t3r-C3.json")
DEFAULT_V1 = os.path.join(EVID, "t3r-C1-validity.json")
DEFAULT_V2 = os.path.join(EVID, "t3r-C2-validity.json")
DEFAULT_PREREG = os.path.join(HERE, "T3-R-EPOCH6-PREREG-20261028.md")
DEFAULT_HOSTS = os.path.join(T3R, "inventory", "epoch4-hosts-20261023.txt")

EXPECTED_HARNESS = "7bfbdcd6686cf23d0f0dc483975be2e22c22019b28f4787726d5ecca18993d66"
EXPECTED_TOOL = "2be911896c2fcdf1a627dbbe7d3c828998da1aa4dee950ce1f3e2dfcd066876d"
EXPECTED_HOSTS = "40dab1c02fcf1fe883972ec7e617aae0de8983372d716463faeb30ea01dd358c"
EXPECTED_WSC = "01f7432e488702b191347cf9a6b0625a922c96c1ee917db553f199c5aaf5869f"
WAIT = 24 * 3600 + 120


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


def ts(value):
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def add(checks, name, ok, detail):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


def entry(entries, basename):
    for e in entries or []:
        if os.path.basename(str(e.get("path", ""))) == basename:
            return e
    return None


def receipt_check(checks, name, receipt_path, evidence_path, cycle,
                  prereg_path, required_inputs):
    r = load(receipt_path)
    if r is None:
        add(checks, name, False, "receipt missing: %s" % receipt_path)
        return
    detail = {}
    ok = True
    detail["tool_sha256"] = r.get("tool_sha256")
    ok = ok and r.get("tool_sha256") == EXPECTED_TOOL
    detail["harness_sha256"] = r.get("harness_sha256")
    ok = ok and r.get("harness_sha256") == EXPECTED_HARNESS
    detail["preregistration_sha256"] = r.get("preregistration_sha256")
    try:
        prereg_sha = sha_file(prereg_path)
    except OSError as e:
        prereg_sha = "missing: %s" % e
    ok = ok and r.get("preregistration_sha256") == prereg_sha
    ok = ok and r.get("cycle") == cycle
    out = entry(r.get("outputs"), os.path.basename(evidence_path))
    detail["output"] = out
    try:
        ev_sha = sha_file(evidence_path)
    except OSError as e:
        ev_sha = "missing: %s" % e
    ok = ok and bool(out) and out.get("sha256") == ev_sha
    missing = []
    for p in required_inputs:
        e = entry(r.get("inputs"), os.path.basename(p))
        try:
            want = sha_file(p)
        except OSError:
            want = None
        if not e or e.get("sha256") != want:
            missing.append(os.path.basename(p))
    detail["missing_or_bad_inputs"] = missing
    ok = ok and not missing
    add(checks, name, ok, detail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c1", default=DEFAULT_C1)
    ap.add_argument("--c2", default=DEFAULT_C2)
    ap.add_argument("--c3", default=DEFAULT_C3)
    ap.add_argument("--validity1", default=DEFAULT_V1)
    ap.add_argument("--validity2", default=DEFAULT_V2)
    ap.add_argument("--prereg", default=DEFAULT_PREREG)
    ap.add_argument("--hosts", default=DEFAULT_HOSTS)
    ap.add_argument("--skip-time", action="store_true")
    args = ap.parse_args()

    c1, c2, c3 = load(args.c1), load(args.c2), load(args.c3)
    v1, v2 = load(args.validity1), load(args.validity2)
    for label, obj in (("C1", c1), ("C2", c2), ("C3", c3)):
        if obj is None:
            print(json.dumps({"ok": False, "error": label + " missing",
                              "path": getattr(args, label.lower())}, indent=1))
            return 2
    if v1 is None:
        print(json.dumps({"ok": False, "error": "C1 validity missing",
                          "path": args.validity1}, indent=1))
        return 2
    if v2 is None:
        print(json.dumps({"ok": False, "error": "C2 validity missing",
                          "path": args.validity2}, indent=1))
        return 2
    if not os.path.exists(args.prereg):
        print(json.dumps({"ok": False, "error": "prereg missing",
                          "path": args.prereg}, indent=1))
        return 2
    if not os.path.exists(args.hosts):
        print(json.dumps({"ok": False, "error": "hosts missing",
                          "path": args.hosts}, indent=1))
        return 2

    s1, s2, s3 = c1.get("summary", {}), c2.get("summary", {}), c3.get("summary", {})
    r1 = s1.get("M5_retention", {})
    r2 = s2.get("M5_retention", {})
    r3 = s3.get("M5_retention", {})
    token = r1.get("token")
    prereg_sha = sha_file(args.prereg)
    checks = []

    add(checks, "cycles", [s1.get("cycle"), s2.get("cycle"), s3.get("cycle")] == [1, 2, 3],
        "got %r" % [s1.get("cycle"), s2.get("cycle"), s3.get("cycle")])
    add(checks, "epoch_label", all(s.get("epoch") == "T3-R" for s in (s1, s2, s3)),
        [s.get("epoch") for s in (s1, s2, s3)])
    for label, s in (("C1", s1), ("C2", s2), ("C3", s3)):
        add(checks, label + "_harness", s.get("harness_sha256") == EXPECTED_HARNESS,
            "%s vs %s" % (s.get("harness_sha256"), EXPECTED_HARNESS))
        add(checks, label + "_prereg", s.get("preregistration_sha256") == prereg_sha,
            "%s vs %s" % (s.get("preregistration_sha256"), prereg_sha))
        add(checks, label + "_hosts", s.get("hosts_sha256") == EXPECTED_HOSTS,
            "%s vs %s" % (s.get("hosts_sha256"), EXPECTED_HOSTS))
        add(checks, label + "_zero_hint",
            "no --hint" in str(s.get("zero_hint_guard", "")),
            str(s.get("zero_hint_guard")))
        add(checks, label + "_M4_quarantined", s.get("M4_quarantined") is True,
            "quarantined=%s totalPeers=%s" % (s.get("M4_quarantined"), s.get("M4_totalPeers")))
        add(checks, label + "_WSC", s.get("weights_hash_computed") == EXPECTED_WSC,
            "%s vs %s" % (s.get("weights_hash_computed"), EXPECTED_WSC))
        add(checks, label + "_WSC_reproducible", s.get("weights_hash_reproducible") is True,
            "reproducible=%s flag=%s" % (s.get("weights_hash_reproducible"),
                                         s.get("weights_hash_method_flag")))

    add(checks, "C1_validity_ok", v1.get("ok") is True,
        "ok=%s c1_sha256=%s" % (v1.get("ok"), v1.get("c1_sha256")))
    add(checks, "C1_validity_hash", v1.get("c1_sha256") == sha_file(args.c1),
        "%s vs %s" % (v1.get("c1_sha256"), sha_file(args.c1)))
    kv = v1.get("kvcheck") or {}
    add(checks, "C1_durable_kvcheck",
        kv.get("ok") is True and (int(kv.get("token_hits") or 0) > 0
                                   or int(kv.get("item_token_hits") or 0) > 0),
        "kvcheck=%s" % kv)
    add(checks, "C2_validity_ok", v2.get("ok") is True,
        "ok=%s c2_sha256=%s" % (v2.get("ok"), v2.get("c2_sha256")))
    add(checks, "C2_validity_hash", v2.get("c2_sha256") == sha_file(args.c2),
        "%s vs %s" % (v2.get("c2_sha256"), sha_file(args.c2)))

    add(checks, "C1_allow_ingest", s1.get("invocation", {}).get("allow_m5_ingest") is True,
        "invocation=%s" % (s1.get("invocation", {}),))
    add(checks, "C2_no_ingest", s2.get("invocation", {}).get("allow_m5_ingest") is False,
        "invocation=%s" % (s2.get("invocation", {}),))
    add(checks, "C3_no_ingest", s3.get("invocation", {}).get("allow_m5_ingest") is False,
        "invocation=%s" % (s3.get("invocation", {}),))

    add(checks, "C1_learn_acked", r1.get("learn_acked") is True,
        "learn_acked=%s learned=%s" % (r1.get("learn_acked"), r1.get("learn")))
    add(checks, "C1_knowledge_increased", r1.get("knowledge_increased") is True,
        "before=%s after=%s" % (r1.get("knowledge_before"), r1.get("knowledge_after")))
    add(checks, "C1_immediate_retrievable", r1.get("immediate_retrievable") is True,
        "immediate=%s total=%s" % (r1.get("immediate_retrievable"),
                                   r1.get("immediate_search_total")))
    add(checks, "C1_token_present", bool(token) and str(token).startswith("T3R-"),
        "token=%s" % token)

    c1_after = int(r1.get("knowledge_after") or 0)
    for label, r in (("C2", r2), ("C3", r3)):
        add(checks, label + "_token_matches_C1", r.get("token") == token,
            "%s vs %s" % (r.get("token"), token))
        add(checks, label + "_retention_ok", r.get("ok") is True, "ok=%s" % r.get("ok"))
        add(checks, label + "_retrievable", r.get("retrievable") is True,
            "retrievable=%s" % r.get("retrievable"))
        add(checks, label + "_search_total", int(r.get("search_total") or 0) >= 1,
            "search_total=%s" % r.get("search_total"))
        add(checks, label + "_ingest_skipped", r.get("ingest_skipped") is True,
            "ingest_skipped=%s" % r.get("ingest_skipped"))
        add(checks, label + "_search_query", r.get("search_query") == token,
            "%s vs %s" % (r.get("search_query"), token))
        kb = int(r.get("knowledge_before") or 0)
        ka = int(r.get("knowledge_after") or 0)
        add(checks, label + "_knowledge_non_decreasing", ka >= kb,
            "before=%s after=%s" % (kb, ka))
        add(checks, label + "_knowledge_vs_C1", kb >= c1_after,
            "before=%s C1_after=%s" % (kb, c1_after))

    if args.skip_time:
        add(checks, "C2_window", True, "skipped")
        add(checks, "C3_window", True, "skipped")
    else:
        try:
            due2 = ts(s1.get("collected_utc")) + dt.timedelta(seconds=WAIT)
            got2 = ts(s2.get("collected_utc"))
            add(checks, "C2_window", got2 >= due2,
                "C2=%s due=%s" % (got2.isoformat(), due2.isoformat()))
            due3 = ts(s2.get("collected_utc")) + dt.timedelta(seconds=WAIT)
            got3 = ts(s3.get("collected_utc"))
            add(checks, "C3_window", got3 >= due3,
                "C3=%s due=%s" % (got3.isoformat(), due3.isoformat()))
        except Exception as e:
            add(checks, "C2_window", False, "timestamp parse: %s" % e)
            add(checks, "C3_window", False, "timestamp parse: %s" % e)

    m1b = int(s1.get("M1_live_routes") or 0)
    m2b = int(s1.get("M2_distinct_bodies") or 0)
    m3b = int(s1.get("M3_phantoms") or 0)
    for label, s in (("C2", s2), ("C3", s3)):
        add(checks, label + "_M1_no_regression",
            int(s.get("M1_live_routes") or 0) >= m1b,
            "%s vs C1=%s" % (s.get("M1_live_routes"), m1b))
        add(checks, label + "_M2_no_regression",
            int(s.get("M2_distinct_bodies") or 0) >= m2b,
            "%s vs C1=%s" % (s.get("M2_distinct_bodies"), m2b))
        add(checks, label + "_M3_no_regression",
            int(s.get("M3_phantoms") or 0) <= m3b,
            "%s vs C1=%s" % (s.get("M3_phantoms"), m3b))
        add(checks, label + "_failures_zero",
            s.get("failures_recorded") == 0,
            "failures_recorded=%s failures=%s" % (s.get("failures_recorded"),
                                                  s.get("failures")))

    receipt_check(checks, "C1_receipt", args.c1 + ".receipts.json", args.c1, 1,
                  args.prereg, [args.prereg, args.hosts])
    receipt_check(checks, "C2_receipt", args.c2 + ".receipts.json", args.c2, 2,
                  args.prereg, [args.prereg, args.hosts, args.c1])
    receipt_check(checks, "C3_receipt", args.c3 + ".receipts.json", args.c3, 3,
                  args.prereg, [args.prereg, args.hosts, args.c1, args.c2])

    ok = all(c["ok"] for c in checks)
    out = {
        "ok": ok,
        "epoch": "T3-R-EPOCH6",
        "gate_pass_mechanical": ok,
        "gate_status": "PASS" if ok else "FAIL",
        "gate_pass_overall": None,
        "b10_zero_hint_attestation": "UNSIGNED",
        "c1_collected_utc": s1.get("collected_utc"),
        "c2_collected_utc": s2.get("collected_utc"),
        "c3_collected_utc": s3.get("collected_utc"),
        "summary": {
            "token": token,
            "C1": {"M1": m1b, "M2": m2b, "M3": m3b,
                   "knowledge_before": r1.get("knowledge_before"),
                   "knowledge_after": r1.get("knowledge_after")},
            "C2": {"M1": s2.get("M1_live_routes"), "M2": s2.get("M2_distinct_bodies"),
                   "M3": s2.get("M3_phantoms"),
                   "failures_recorded": s2.get("failures_recorded"),
                   "knowledge_before": r2.get("knowledge_before"),
                   "knowledge_after": r2.get("knowledge_after")},
            "C3": {"M1": s3.get("M1_live_routes"), "M2": s3.get("M2_distinct_bodies"),
                   "M3": s3.get("M3_phantoms"),
                   "failures_recorded": s3.get("failures_recorded"),
                   "knowledge_before": r3.get("knowledge_before"),
                   "knowledge_after": r3.get("knowledge_after")},
            "WSC": s3.get("weights_hash_computed"),
        },
        "checks": checks,
        "note": ("Mechanical T3-R epoch-6 check only. B10 zero-hint owner "
                 "attestation and final owner sign-off remain; no pass is "
                 "claimed here. The epoch-5 verifier's exact knowledge-equality "
                 "check is not carried forward; the frozen bar requires "
                 "non-regression."),
    }
    print(json.dumps(out, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
