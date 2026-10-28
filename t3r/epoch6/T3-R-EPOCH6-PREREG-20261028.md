# T3-R EPOCH 6 — RETENTION SUCCESSOR — PRE-REGISTRATION — 2026-10-28

Status: **FROZEN BEFORE C1 COLLECTION — AMENDMENT 1.** This is a new
pre-registered epoch. It does not rewrite the epoch-5 pre-registration, the
epoch-5 evidence, or the epoch-5 verdict. Epoch 5 remains **C3 MECHANICAL FAIL /
T3-R NO PASS**. Amendment 1 was made after a C1 attempt that wrote no evidence;
no valid C1 collection exists yet.

## Owner authorization

The owner was shown the epoch-5 C3 failure analysis (M1 `280 < 283`, M2
`259 < 260`, three no-response routes, all three answering again on a read-only
probe) and was asked whether to authorize a new pre-registered epoch or close
T3-R. The owner answered **“proceed”** on **2026-10-28**. This document records
that answer as authorization to pre-register and run epoch 6.

This is not a retry of epoch-5 C3 and not a retune. Epoch 5 is closed as
**FAIL**; epoch 6 is a fresh C1/C2/C3 collection under the unchanged numerical
bar.

## Amendment 1 — C1 durability poll (2026-10-28T16:55Z)

C1 attempt 1 (`40728339951`, learn at `2026-10-28T16:44:49Z`) wrote **no
evidence**. The harness saw `learned:true` but its immediate `brain_status`
read returned `knowledge 69→69`, so it refused to write a C1 artifact and
returned 1. There is no `t3r-C1.json` from that attempt; C2/C3 were not
attempted.

A read-only durability check after the attempt found the token
`T3R-20261028T164449Z-8f58f126` in the edge-brain store:

- `/status`: `knowledge=70`;
- `/kvcheck?q=T3R-20261028T164449Z-8f58f126`: `know=70`, `items=6`,
  `token_hits=1`, `item_token_hits=1`.

The write was durable; the immediate count read was stale (warm isolate). The
attempt's token is **not used** as the epoch-6 C1 baseline because that attempt
wrote no harness evidence or route summary. It remains an extra durable entry;
a fresh C1 token is generated.

Amendment 1 changes only the C1 read timing and adds a durability
precondition:

- Epoch 6 uses `t3r/epoch6/t3r_harness.py`, a copy of the frozen T3-R harness
  with a bounded **20 s post-learn status poll** before the C1 after-read.
  Every poll is a read-only `brain_status`; the harness still requires
  `K_after > K_before`.
- The epoch-6 runner additionally requires a read-only `/kvcheck` confirmation
  that the fresh C1 token is durable (`token_hits > 0` or
  `item_token_hits > 0`) before C2 is allowed.
- The route probe, paths, timeouts, scoring, M5 stimulus, WSC-1, and pass bar
  are unchanged. This is not a pass-bar retune.
- The epoch-5 harness and epoch-5 evidence are untouched.

New instrument hashes are recorded in “Frozen instruments” below.

## Why a new epoch is required

Epoch-5 C3 failed mechanically because three routes that were live at C2
timed out during C3:

- `agi-arc3-epb-evaluator.eon-sovereign.workers.dev/health`
- `api-anthropic.eon-sovereign.workers.dev/status`
- `api-cloudflare.eon-sovereign.workers.dev/mcp`

They account for M1 `−3` exactly and for M2 `−1` (the `agi-arc3-epb-evaluator`
body was the only unique body among the three; the other two bodies were
duplicated in C2). The frozen bar requires `failures=0`; the failure stands.
Read-only probes after C3 returned 200 for all three, so the C3 event was
transient, but the epoch-5 result is not converted into a pass.

The epoch-5 pre-registration requires a new pre-registered epoch for another
attempt. This is that epoch.

## Inventory and probe (frozen)

- Inventory: `t3r/inventory/epoch4-hosts-20261023.txt`
- Hosts: **100** (all Cloudflare worker scripts at the epoch-4 freeze time)
- Hosts sha256: `40dab1c02fcf1fe883972ec7e617aae0de8983372d716463faeb30ea01dd358c`
- Paths: `/`, `/health`, `/status`, `/mcp`, `/__nonexistent_c2_probe__`
- Route count: **500** (`100 × 5`)
- M1/M2/M3 scoring: unchanged from the sealed harness (`t3_c3_harness.py` /
  `t3r_harness.py`)
- M4: collected but **QUARANTINED** (`eon-p2p-cloud /status totalPeers=0`
  across all 6 shards); not scored.
- Coverage (`T3-COV-PROPOSED-v1`) and route health/cost proxies are recorded
  as **diagnostics only**; they are not pass criteria.

## Primary capability: retention across cycles

At **C1** the harness:

1. reads `brain_status` (`K1_before`);
2. generates a unique token `T3R-<UTC>-<random>`;
3. embeds the exact token at the start of a short document and serves it via
   `https://httpbin.org/base64/<base64>`;
4. calls `brain_learn(url, topic=token)` once (`--allow-m5-ingest`);
5. reads `brain_status` again (`K1_after`);
6. performs an immediate `knowledge_search(token)` as a **sanity check only**.

C1 is valid only if `learned:true`, `K1_after > K1_before`, and the immediate
search returns the exact token. The epoch-6 runner additionally requires a
read-only `/kvcheck` confirmation that the C1 token is durable before C2 is
allowed (Amendment 1). A C1 that writes no evidence is not a collection and
may be retried operationally; a completed C1 that fails these conditions is
recorded **invalid** and stops the epoch (no automatic retry).

At **C2** (≥24 h + 120 s after C1) and **C3** (≥24 h + 120 s after C2), the
harness is read-only:

1. reads `brain_status` (`K_before`);
2. calls `knowledge_search(token)` for the C1 token;
3. reads `brain_status` again (`K_after`);
4. requires the exact token to be present in at least one result, and
   `K_before >= K1_after` (knowledge did not regress).

The token is generated by the harness, not supplied by the operator. It is a
stimulus, not a hint. The zero-hint guard rejects any `--hint` channel or
`T3_HINT_FILE`.

## Pass bar (frozen; unchanged from T3-R)

T3-R epoch-6 mechanical pass at C2 **and** C3 requires all of:

1. **Retention:** `knowledge_search(C1 token)` returns the exact token.
2. **Knowledge non-regression:** `K_before >= K1_after`.
3. **No regression vs C1:** `M1` and `M2` are not below C1; `M3` is not above C1.
4. **Weights unchanged:** WSC-1 computed hash equals
   `01f7432e488702b191347cf9a6b0625a922c96c1ee917db553f199c5aaf5869f` in C1,
   C2, and C3.
5. **M4:** quarantined; recorded only.

A mechanical pass is **PROVISIONAL**; the final gate result is `null` until the
owner signs a new B10 zero-hint attestation and the final report. No pass is
claimed by the harness or the verifier alone.

### Mechanical integrity checks (same bar, complete application)

The verifier applies the bar at **both C2 and C3**, because the bar says
“mechanical pass at C2 and C3”:

- exact token present in C2 and C3; no ingest at C2/C3;
- `K_before >= K1_after` at C2 and C3;
- M1/M2/M3 no regression vs C1 at C2 and C3;
- `failures_recorded == 0` at C2 and C3 (a cycle with no-response routes is not
  a clean measurement);
- WSC-1 unchanged and reproducible;
- M4 quarantined;
- receipts cover the delivered evidence;
- zero-hint guard recorded.

The epoch-5 verifier checked C3 only and additionally required exact equality
of knowledge counts (`K_after == K_before`). The frozen bar does not require
exact equality; it requires non-regression. Epoch 6 therefore records
non-decreasing knowledge reads and does **not** carry forward that extra
equality check. This is an instrument correction, not a lowering of the bar.
The epoch-5 failure remains recorded exactly as it happened.

## WSC-1 weights inputs (frozen)

| file | bytes | sha256 |
|---|---:|---|
| `T1-TRANSFER-FROZEN.md` | 830 | `5ef0537ab3e8a3224a47e475bbabcfa6d28409cec7226e87b13fee4e0f8cfdb5` |
| `T2-SELECTION-FROZEN.md` | 744 | `4c1de8d1be25ef00d475e90bed6f87f6dd6c28f464555b832954eb93c8a757a6` |
| `T3-LONGITUDINAL-FROZEN.md` | 732 | `ecadd9c880d57e93af6e079525ffd901b6a484298626a99e651b95a76f80cd24` |
| `T4-SELFCORRECTION-FROZEN.md` | 801 | `e51f6095006d344f41ed0b2d121badb6d3c7ae22057827dcb112d1dea9986bac` |

WSC-1 = sha256 over sorted `(filename \0 content \n)` for those four files,
yielding `01f7432e488702b191347cf9a6b0625a922c96c1ee917db553f199c5aaf5869f`.
The old `0e97aa1c…` constant remains a historical B5 mismatch, not used.

## Frozen instruments

| instrument | sha256 |
|---|---|
| `t3r/epoch6/t3r_harness.py` | `7bfbdcd6686cf23d0f0dc483975be2e22c22019b28f4787726d5ecca18993d66` |
| `t3r/t3_c3_harness.py` | `2be911896c2fcdf1a627dbbe7d3c828998da1aa4dee950ce1f3e2dfcd066876d` |
| `t3r/coverage_instrument.py` | `98a190c1a8312e949a0396193f53b51c8f56467aeadd2aeaf279c7d855676344` |
| `t3r/inventory/epoch4-hosts-20261023.txt` | `40dab1c02fcf1fe883972ec7e617aae0de8983372d716463faeb30ea01dd358c` |
| `t3r/epoch6/verify.py` | `fb73ea8d3ff9f8599da3cfa9858542fb10d62e99fd6a1291fb3d5faf3b20b0b6` |
| `t3r/epoch6/run_cycle.py` | `1a211ad89ecd7191f24a5dd78b495495962b80cd887af433bcc09d9cc9896cde` |

- Evidence directory: `t3r/evidence/epoch6/`
- C1: `t3r-C1.json` + receipts; C2: `t3r-C2.json` + receipts; C3:
  `t3r-C3.json` + receipts.
- C1/C2 validity artifacts: `t3r-C1-validity.json`,
  `t3r-C2-validity.json`.
- C3 verifier output: `t3r-C3-verify.json`.
- C1 execution must pass `--expect-seal 7bfbdcd6…`; the harness refuses a
  mismatched self-hash.
- Final evidence write happens before receipts; receipts cover the delivered
  evidence exactly.
- The verifier is read-only and never calls MCP. Its output records
  `gate_pass_mechanical`, `gate_status`, `gate_pass_overall:null`, and
  `b10_zero_hint_attestation:"UNSIGNED"`.

## Dispatch and duplicate protection

The epoch is driven by `.github/workflows/t3r-epoch6.yml`:

- concurrency group `t3r-epoch6`, `cancel-in-progress:false`;
- checkout `ref: main`, then `git fetch origin main` and `git reset --hard
  origin/main` before running, so a queued duplicate cannot run against a
  pre-evidence commit;
- the runner refuses to overwrite C1/C2/C3 and refuses a second C1;
- a completed C3 is not rerun; if `t3r-C3-verify.json` is missing, the verifier
  is run read-only to complete the record.

There is no local one-shot dispatch marker for this epoch. The epoch-5
duplicate-dispatch defect (two runs created at `16:02:02Z`; duplicate
`40721930591` canceled before writing a second C3) remains recorded in the
epoch-5 failure analysis. Epoch 6 uses the workflow concurrency + fresh-main
guard instead.

## Cycle schedule

- C1: first successful `t3r-epoch6` dispatch after AMENDMENT 1 is committed;
  target on/after `2026-10-28T17:10:00Z`.
- C2: only ≥24 h + 120 s after C1 `collected_utc`; read-only retention check.
- C3: only ≥24 h + 120 s after C2 `collected_utc`; read-only retention check.

The harness and runner enforce the 24 h windows. No window is bypassed.

## Owner gates still open

- **B10:** new zero-hint owner attestation for epoch 6. The old epoch-5 B10 is
  not reused. The harness can attest only that no `--hint` channel was supplied
  to its own process; the owner must sign the final attestation.
- **B5:** old `0e97aa1c…` remains unreconciled. Epoch 6 freezes WSC-1 but does
  not erase the historical B5 item.
- **M4:** peers remain quarantined; fixing the p2p registry is a separate
  owner/cloud task.
- **Final report/sign-off:** required before any epoch-6 pass is treated as
  final.

## Failure and retry rules

- A completed C1 that fails the C1 validity conditions is recorded invalid and
  stops the epoch; no automatic C1 retry.
- A completed C2 that fails retention, no-regression, or `failures=0` is
  recorded invalid and stops C3; no automatic C2 retry.
- A completed C3 that fails any verifier check is recorded **FAIL**; no retune,
  no automatic C3 rerun.
- Any future attempt after a recorded failure requires a new pre-registration
  and a new owner authorization; it is not a continuation of epoch 6.
- The pass bar and WSC-1 are not changed by a failure.

## Scope safety

- No worker deploy, no `wrangler`, no QStack `8443`/`443`, no `8201`/`8444`
  changes.
- The only mutation is the C1 `brain_learn` knowledge entry (one public
  document). C2/C3 are read-only.
- No production 23/24, Worker, DO, model, weights, WARP, or secret changes.
- No secrets are written to evidence; the admin token is read from
  `~/eon-tmp/.adm` (mode 600) inside the process and never printed. The
  retention token is not a secret.
- No secrets in this document.
