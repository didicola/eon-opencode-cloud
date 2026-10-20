# EON Monitoring Card — 2026-10-20

Status page: https://eon-arch.betteruptime.com

Better Stack monitors (60-second checks, all up):
- 5100725 — EON host /api/health — https://eon-host-own-c7f3.vercel.app/api/health
- 5100726 — EON host /api/status — https://eon-host-own-c7f3.vercel.app/api/status
- 5100727 — EON matrix keeper /status — https://eon-matrix-keeper.eon-sovereign.workers.dev/status
- 5100728 — EON artifact agent /healthz — https://artifact-agent.eon-sovereign.workers.dev/healthz
- 5100729 — EON VRAM diary /read — https://eon-vram.eon-sovereign.workers.dev/read?addr=0xa0007000

Heartbeat 513053 — EON termux1 phone — period 900s, grace 2700s, status up.

Better Stack Catalog relations are paid-only (API 403, upgrade required). The MCP OAuth scope is read-only; writes use a local API token that is never published. No secrets are in this card.
