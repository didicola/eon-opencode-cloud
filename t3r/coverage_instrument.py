#!/usr/bin/env python3
# coverage_instrument.py — T3 coverage metric, fills blocker B4.
#
# STATUS: PROPOSED-FOR-OWNER-APPROVAL. This is NOT the frozen definition.
# The frozen protocol (T3-LONGITUDINAL-FROZEN.md line 4-5) defines coverage as
# "tasks completed per cycle on the T1/T2 families", but the sealed harness
# (T3-C2-PROBE.py) collected M1-M5 only and never counted tasks, so the frozen
# coverage is NOT computable from any artifact that exists (blocker B4,
# T3-REEVAL-20261008.md line 205). This instrument therefore proposes a
# minimal, deterministic surrogate computed from data the sealed harness DID
# record (the per-route probe results), and must be approved by the owner and
# pre-registered before the next cycle (T3-REEVAL-20261008.md A2).
#
# PROPOSED DEFINITION (T3-COV-PROPOSED-v1):
#   coverage(run) = covered_hosts(run) / inventory_hosts(run)
#   A host is COVERED iff at least one of the 4 REAL paths
#   {/, /health, /status, /mcp} returned HTTP 200 with a non-empty body that
#   is not the shared catch-all. The deliberately-invented path
#   /__nonexistent_c2_probe__ is EXCLUDED from the numerator (a 200 there is
#   an M3 phantom, i.e. a defect, never coverage). The "task" unit of the
#   frozen "+2" bar maps to one additional covered host.
#
# Per-shard breakdown: no frozen host->shard mapping exists anywhere in the
# sealed set, so the breakdown uses scheme COV-SHARD-RR1: hosts sorted by
# sha256(hostname) then round-robin assigned to 6 buckets (shard0..shard5).
# The partition is deterministic and hash-stable; the OVERALL coverage does
# not depend on it. Buckets are synthetic indices, NOT the live p2p shards
# (whose only signal, M4, is quarantined as UNRELIABLE).
#
# CLI:  python3 coverage_instrument.py --run <json> [--hosts sub.txt]
#       python3 coverage_instrument.py --self-test
# Output: single JSON object on stdout, sort_keys + fixed rounding so that
# double runs over identical input are byte-identical (hash-stable).

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

DEFINITION_ID = "T3-COV-PROPOSED-v1"
PROPOSED = True
SHARD_SCHEME = "COV-SHARD-RR1"
SHARD_COUNT = 6
REAL_PATHS = ["/", "/health", "/status", "/mcp"]
PHANTOM_PATH = "/__nonexistent_c2_probe__"
CATCHALL_BODIES = {'{"tunnel":"offline","connectedAt":0,"pending":0}'}
ROUND = 6


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_run(path):
    with open(path) as f:
        run = json.load(f)
    if not isinstance(run, dict) or "routes" not in run:
        raise ValueError("run file %s has no 'routes' array (not a T3 collection artifact)" % path)
    if not isinstance(run["routes"], list):
        raise ValueError("'routes' in %s is not a list" % path)
    return run


def load_hosts(path, run):
    if path:
        with open(path) as f:
            hosts = [l.strip() for l in f if l.strip()]
    else:
        hosts = sorted({r.get("host", "") for r in run["routes"] if r.get("host")})
    seen, out = set(), []
    for h in hosts:
        if h and h not in seen:
            seen.add(h)
            out.append(h)
    return out


def covered_hosts(run, inventory):
    live = {r.get("host") for r in run["routes"]
            if r.get("path") in REAL_PATHS
            and r.get("code") == 200
            and (r.get("len") or 0) > 0
            and not r.get("catchall")
            and r.get("body") not in CATCHALL_BODIES}
    return [h for h in inventory if h in live]


def shard_partition(hosts):
    ranked = sorted(hosts, key=lambda h: sha256_bytes(h.encode()))
    buckets = {i: [] for i in range(SHARD_COUNT)}
    for idx, h in enumerate(ranked):
        buckets[idx % SHARD_COUNT].append(h)
    return buckets


def compute(run_path, hosts_path=None):
    run = load_run(run_path)
    inventory = load_hosts(hosts_path, run)
    covered = set(covered_hosts(run, inventory))
    n = len(inventory)
    k = len(covered)
    coverage = round(k / n, ROUND) if n else 0.0

    buckets = shard_partition(inventory)
    per_shard = {}
    for i in sorted(buckets):
        members = buckets[i]
        c = sum(1 for h in members if h in covered)
        per_shard["shard%d" % i] = {
            "covered_hosts": c,
            "inventory_hosts": len(members),
            "coverage": round(c / len(members), ROUND) if members else 0.0,
            "members_sha256": sha256_bytes("\n".join(sorted(members)).encode()),
        }

    out = {
        "definition_id": DEFINITION_ID,
        "proposed_for_owner_approval": PROPOSED,
        "status": "PROPOSED - not the frozen definition; owner must approve and pre-register (B4)",
        "coverage": coverage,
        "coverage_count": k,
        "inventory_hosts": n,
        "covered_host_count": k,
        "real_paths": REAL_PATHS,
        "uncovered_hosts": [h for h in inventory if h not in covered],
        "per_shard": per_shard,
        "shard_scheme": SHARD_SCHEME,
        "shard_scheme_note": "synthetic hash-ordered round-robin partition; no frozen host->shard mapping exists; overall coverage is partition-independent",
        "run_label": run.get("summary", {}).get("label"),
        "run_collected_utc": run.get("summary", {}).get("collected_utc"),
        "inputs": {
            "run_path": os.path.abspath(run_path),
            "run_sha256": sha256_file(run_path),
            "sha256_of_input": sha256_file(run_path),
            "hosts_path": os.path.abspath(hosts_path) if hosts_path else None,
            "hosts_sha256": sha256_file(hosts_path) if hosts_path else None,
        },
    }
    return out


def render(result):
    return json.dumps(result, sort_keys=True, indent=1) + "\n"


def self_test():
    here = os.path.dirname(os.path.abspath(__file__))
    fixture = os.path.join(here, "fixtures", "coverage-selftest-fixture.json")
    if not os.path.exists(fixture):
        print("SELF-TEST FAIL: missing fixture %s" % fixture)
        return 1
    with tempfile.TemporaryDirectory(dir=here) as td:
        run_a = os.path.join(td, "a.json")
        run_b = os.path.join(td, "b.json")
        with open(fixture) as f:
            data = f.read()
        for p in (run_a, run_b):
            with open(p, "w") as f:
                f.write(data)
        env = dict(os.environ)

        def run_cli(p):
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "--run", p],
                               capture_output=True, text=True, env=env)
            if r.returncode != 0:
                print("SELF-TEST FAIL: exit %d: %s" % (r.returncode, r.stderr))
                return None
            return r.stdout

        # double run over the SAME input must be byte-identical
        out1, out2 = run_cli(run_a), run_cli(run_a)
        # a byte-identical copy at a different path must yield the same numbers
        out3 = run_cli(run_b)
    if out1 is None or out2 is None or out3 is None:
        return 1
    if out1 != out2:
        print("SELF-TEST FAIL: double run not byte-identical")
        return 1
    res, res3 = json.loads(out1), json.loads(out3)
    for key in ("coverage", "coverage_count", "inventory_hosts", "per_shard"):
        if res[key] != res3[key]:
            print("SELF-TEST FAIL: moved copy changed %s" % key)
            return 1
    if res["inputs"]["run_sha256"] != res3["inputs"]["run_sha256"]:
        print("SELF-TEST FAIL: input sha mismatch on identical content")
        return 1
    # fixture truth: a,b,d covered (3 of 4); phantom-path 200 on a must NOT count
    expect = {"coverage_count": 3, "inventory_hosts": 4, "coverage": 0.75}
    for key, val in expect.items():
        if res[key] != val:
            print("SELF-TEST FAIL: %s=%r expected %r" % (key, res[key], val))
            return 1
    print("SELF-TEST PASS: deterministic double-run identical; coverage=0.75 (3/4); "
          "phantom-path 200 correctly excluded")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="coverage_instrument.py",
        description="T3 coverage metric (B4) — PROPOSED-FOR-OWNER-APPROVAL, definition %s" % DEFINITION_ID)
    ap.add_argument("--run", help="T3 collection json (summary+routes), e.g. t3c2-C2.json")
    ap.add_argument("--hosts", help="host inventory file (default: hosts recorded in the run; "
                                    "main lane should pass ~/sub.txt explicitly for comparability)")
    ap.add_argument("--self-test", action="store_true", help="build fixture, double-run, assert identical output")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.run:
        ap.error("--run is required (or use --self-test)")
    if not os.path.exists(args.run):
        print("ERROR: run file not found: %s" % args.run, file=sys.stderr)
        return 2

    hosts = args.hosts
    if hosts and not os.path.exists(hosts):
        print("ERROR: hosts file not found: %s" % hosts, file=sys.stderr)
        return 2

    try:
        result = compute(args.run, hosts)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    sys.stdout.write(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
