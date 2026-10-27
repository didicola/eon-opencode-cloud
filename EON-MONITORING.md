# EON Monitoring Card

Updated: 2026-10-27T17:57:30Z
Status page: https://eon-arch.betteruptime.com (downtime)

Better Stack monitors (60-second checks):
- 5100725 up @60s — EON host /api/health — https://eon-host-own-c7f3.vercel.app/api/health
- 5100726 up @60s — EON host /api/status — https://eon-host-own-c7f3.vercel.app/api/status
- 5100727 up @60s — EON matrix keeper /status — https://eon-matrix-keeper.eon-sovereign.workers.dev/status
- 5100728 up @60s — EON artifact agent /healthz — https://artifact-agent.eon-sovereign.workers.dev/healthz
- 5100729 down @60s — EON VRAM diary /read — https://eon-vram.eon-sovereign.workers.dev/read?addr=0xa0007000

Heartbeat 513053 — EON termux1 phone — 900s period / 2700s grace — up.

Catalog relations are paid-only (API 403, upgrade required). The MCP OAuth scope is read-only; writes use a local API token that is never published. No secrets are in this card.