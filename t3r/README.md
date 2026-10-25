# T3-R cloud runner

This directory contains the frozen T3-R retention harness and the cloud/GitHub
runner. It is **not** a pass record.

## Current state

- C1 (local, 2026-10-25) is **invalid**: the active edge-brain KV lane lost the
  token because the account-wide KV write quota returned `429/10048`. See
  `T3-R-C1-INVALID-20261025.md`.
- The owner approved an `eon-edge-brain` per-item persistence patch and a new
  C1b baseline. See `T3-R-AMENDMENT-2-C1B-20261026.md`.
- C1b must not start before **2026-10-26T00:00:30Z** (KV quota reset).

## Files

- `t3r_harness.py` — frozen harness, sha256 `a4826b7e…`.
- `t3_c3_harness.py` — sealed scoring/weights/coverage helpers.
- `coverage_instrument.py` — diagnostic coverage instrument.
- `T3-R-PREREG-20261025.md` — frozen pre-registration.
- `T3-R-AMENDMENT-2-C1B-20261026.md` — C1b re-baseline amendment.
- `inventory/epoch4-hosts-20261023.txt` — frozen 100-host inventory.
- `weights/` — the four frozen WSC-1 design files.
- `evidence/epoch5/` — C1b/C2/C3 evidence and C1b validity.

## Automation

`.github/workflows/t3r.yml` runs four times/day:

1. If no C1b and now >= 2026-10-26T00:00:30Z, run C1b (one
   `--allow-m5-ingest`), then verify `/kvcheck?q=<token>` shows a durable
   `token_hits` or `item_token_hits`. If not, write `ok:false` and stop.
2. If C1b is valid and 24h+120s old, run C2 read-only.
3. If C2 is 24h+120s old, run C3 read-only.
4. Commit evidence to this public repo.

`.github/workflows/t3r-probe.yml` is read-only: MCP status plus a full 500-route
probe, no M5 mutation.

The admin token is read from the encrypted `MCP_ADMIN_TOKEN` repository secret
into `~/eon-tmp/.adm` (600) on the runner; it is never printed.

## Not a pass

T3-R has **no pass** until C1b, C2, C3, the frozen gate, B10 owner zero-hint
attestation, and final owner sign-off all complete. The production 23/24
adapter is unchanged.
