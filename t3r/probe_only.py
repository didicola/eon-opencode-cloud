#!/usr/bin/env python3
"""Read-only full route probe from the cloud runner; no M5 mutation."""
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import t3r_harness as h  # noqa: E402

HOSTS = os.path.join(HERE, "inventory", "epoch4-hosts-20261023.txt")
OUT = os.path.join(HERE, "evidence", "epoch5", "t3r-cloud-probe.json")


def main():
    hosts = [l.strip() for l in open(HOSTS, encoding="utf-8") if l.strip()]
    coll = h.collect_routes(hosts)
    rec = {
        "collected_utc": datetime.now(timezone.utc).isoformat(),
        "hosts": len(hosts),
        "M1_live_routes": coll["M1"],
        "M2_distinct_bodies": coll["M2"],
        "M3_phantoms": coll["M3"],
        "M4_any_shard_peers": coll["M4"],
        "M4_shard_peers": coll["peers"],
        "failures": coll["failures"],
        "note": "diagnostic only; no M5, no gate evidence",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps(rec, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
