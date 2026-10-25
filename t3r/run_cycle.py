#!/usr/bin/env python3
"""Select and run the next due T3-R cycle. No secrets printed."""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EVID = os.path.join(HERE, "evidence", "epoch5")
HARNESS = os.path.join(HERE, "t3r_harness.py")
PREREG = os.path.join(HERE, "T3-R-PREREG-20261025.md")
HOSTS = os.path.join(HERE, "inventory", "epoch4-hosts-20261023.txt")
WEIGHTS = os.path.join(HERE, "weights")
EXPECT = "a4826b7e0d0a91f37e1f20cded196a77f83b1f91e7532aa76ca6658fdca93661"
NOT_BEFORE = datetime(2026, 10, 26, 0, 0, 30, tzinfo=timezone.utc)
WAIT = 24 * 3600 + 120

C1 = os.path.join(EVID, "t3r-C1b.json")
C2 = os.path.join(EVID, "t3r-C2.json")
C3 = os.path.join(EVID, "t3r-C3.json")
VALID = os.path.join(EVID, "t3r-C1b-validity.json")


def now_utc():
    return datetime.now(timezone.utc)


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def summary(path):
    d = json.load(open(path, encoding="utf-8"))
    return d.get("summary", d)


def age_ok(path):
    s = summary(path)
    ts = parse_ts(s.get("collected_utc"))
    if not ts:
        print("ERROR: unreadable collected_utc in", path, file=sys.stderr)
        return False
    age = (now_utc() - ts).total_seconds()
    print("AGE %s %.0fs need>=%ss" % (os.path.basename(path), age, WAIT))
    return age >= WAIT


def run(cycle, out, receipts, baseline=None, previous=None):
    args = [
        sys.executable, HARNESS, "--execute", "--cycle", str(cycle),
        "--prereg", PREREG, "--hosts", HOSTS, "--weights-dir", WEIGHTS,
        "--out", out, "--receipts", receipts, "--expect-seal", EXPECT,
    ]
    if cycle == 1:
        args.append("--allow-m5-ingest")
        args += ["--out", C1, "--receipts", C1 + ".receipts.json"]
    else:
        args += ["--baseline", C1]
        if previous:
            args += ["--previous", previous]
    print("RUN cycle=%d out=%s" % (cycle, out), flush=True)
    return subprocess.call(args, cwd=ROOT)


def main():
    if not os.path.exists(C1):
        if now_utc() < NOT_BEFORE:
            print("WAIT C1b not before %s (now %s)" % (NOT_BEFORE.isoformat(), now_utc().isoformat()))
            return 0
        return run(1, C1, C1 + ".receipts.json")

    if not os.path.exists(VALID):
        print("C1B_VALIDITY_MISSING: refusing C2/C3", file=sys.stderr)
        return 1
    v = json.load(open(VALID, encoding="utf-8"))
    if not v.get("ok"):
        print("C1B_INVALID: refusing C2/C3", file=sys.stderr)
        return 1

    if not os.path.exists(C2):
        if not age_ok(C1):
            print("WAIT C2 window not open")
            return 0
        return run(2, C2, C2 + ".receipts.json", previous=C1)

    if not os.path.exists(C3):
        if not age_ok(C2):
            print("WAIT C3 window not open")
            return 0
        return run(3, C3, C3 + ".receipts.json", previous=C2)

    print("DONE all T3-R cycles present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
