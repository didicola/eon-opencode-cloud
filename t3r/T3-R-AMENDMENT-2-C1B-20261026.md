# T3-R AMENDMENT 2 — C1b RE-BASELINE AFTER C1 INVALIDATION

Date: 2026-10-25 (UTC)
Status: **C1 INVALID — C1b REQUIRED — NO PASS YET**

## Why

The T3-R C1 token was not durable. The account-wide Cloudflare KV write quota
returned `429 / 10048` at 21:55Z; the edge-brain catches KV write failure
silently. C1's `knowledge_after=68` was isolate-local memory, not retained
state in the active KV lane. The full-map-per-isolate design is a secondary
risk, but the measured cause of this loss is quota-blocked persistence. The D1
fallback write was not verified; it is not the configured retrieval path when
KV returns a store.

C1 remains a historical artifact only. It is **not** a pass baseline and C2/C3
must not run from it.

## Owner approval

The owner explicitly approved **“Patch edge-brain + C1b”** on 2026-10-25 after
the C1 invalidation evidence was presented. This approval covers:

- the `eon-edge-brain` per-item persistence patch and deploy;
- a new C1b baseline after the KV quota reset;
- the already-approved cloud/GitHub runner for C1b/C2/C3.

It does **not** approve any change to the T3-R pass criteria, the production
23/24 adapter, QStack, or any owner-only B10 attestation.

## C1b baseline

- Earliest start: **2026-10-26T00:00:30Z** (after the daily KV write reset).
- Use the frozen T3-R harness (`t3r_harness.py`, sha256
  `a4826b7e0d0a91f37e1f20cded196a77f83b1f91e7532aa76ca6658fdca93661`), the
  original pre-registration, inventory, and weights.
- Fresh token; `--cycle 1 --allow-m5-ingest` only once.
- Immediately verify durable KV with
  `GET https://eon-edge-brain.eon-sovereign.workers.dev/kvcheck?q=<token>`.
  Require `token_hits > 0` or `item_token_hits > 0`. If both are zero, C1b is
  invalid; C2/C3 remain off.
- The C1b artifact is named `t3r-C1b.json`; the old `t3r-C1.json` is not
  overwritten and remains historical.

## C2/C3

- C2 at C1b `collected_utc + 24h + 120s`, read-only, no
  `--allow-m5-ingest`.
- C3 at C2 `collected_utc + 24h + 120s`, read-only.
- The gate criteria are unchanged: token retention is primary; M1/M2/M3 are
  no-regression guards; WSC-1 weights unchanged; M4 quarantined; coverage and
  cost recorded as diagnostics.
- B10 owner zero-hint attestation and final sign-off remain required; a
  mechanical pass is provisional only.

## Patch record

- Live `eon-edge-brain` pure source before patch: 29165 B, sha256
  `a47f70b1ddd4350862615a046677f69345acde28e67309ed177d811955a9753b`.
- Patched source: sha256
  `dbae56023051266e5185bd3f42e04926a3cf65fa455aee3b86338b27e7c3ef03`.
- Deploy HTTP 200; etag
  `972306e3dcd69401978f3f7d755e3d9a42915dc69b05592aa5e7310a3ddbc5bc`;
  bindings preserved (`D1_TOKEN`, `GEMINI_KEY`, `GROQ_KEY`, `KV`).
- Unit test passed with two stale isolates and a simulated full-map
  overwrite; fresh and stale isolates both recovered the token from
  `brain-item:`.
- Live `/kvcheck` currently shows `items:0` because KV writes remain
  quota-blocked; it must show the C1b token after reset.

## No secrets

No credential values are recorded here. The retention token is a public
stimulus. The admin token remains in `~/eon-tmp/.adm` (600) and, for the cloud
runner, in the encrypted `MCP_ADMIN_TOKEN` repository secret.
