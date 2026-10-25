# T4 SELF-CORRECTION — FROZEN DESIGN (pre-registered 2026-09-29, sealed before any run)
Bar: 4/4 faults detected + rerouted + recovered + reported in frozen taxonomy AND zero false `ok`. Else FAIL.
Fault classes (frozen): DEAD-LANE (phantom/deleted worker), POISONED-CACHE (body truncation hides marker),
WIPED-STATE (empty roster/file committed), QUOTA-TRIP (API 429/401 delusions).
Snapshot: roster + worker states sealed (sha256) at run start; faults injected on the sealed snapshot only.
Oracle: independent re-check of raw logs; FALSE-OK = any healthy-report on an injected-fault state.
Known from rehearsal (2026-09-28): 3/4 detected cleanly, 2 false-oks => bar FAIL if repeated.
Pre-registered expectation: likely FAIL on first proper run (zero-false-ok is the hard clause); record honestly.
