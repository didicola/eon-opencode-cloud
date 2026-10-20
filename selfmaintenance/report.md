# Self-Maintenance Report (2026-10-20)

| Lane | Status |
|---|---|
| cloud-brain API (`/v1/models`) | UP — 3 models listed |
| AGI engine (`/health`) | UP — score 0.953, cycles 5921/5641 passed |
| fleet nodes (admin.json) | 10/13 OK; alpha, tiny-4, tiny-5 DOWN (no binding) |
| recommended.workers.dev/v1/models | DOWN — DNS failure |

**Recommended action:** Rebind or redeploy workers `alpha`, `tiny-4`, `tiny-5` (no binding).
