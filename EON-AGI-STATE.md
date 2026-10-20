# EON Cloud AGI State

Updated: 2026-10-20T16:59:15Z
Worker: agi-cloud-v10, persistent=True, store=do-storage, cron=do-alarm+gh-actions.
Cycles: 5721. Passed: 5456. Failed: 265. Score: 95.4%.
Self-mods: 227. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 82%.

Domains: math=84%(n=107) string=79%(n=174) compare=77%(n=271) logic=83%(n=122) spatial=99%(n=80) temporal=86%(n=71) causal=99%(n=70) creative=91%(n=79).
Last run: 2026-10-20T16:51:42.228Z.
Transfer probe: spatial -> revlex delta 0 (applied=False).

Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 offline; ubuntu SSH/ports firewalled, 443 mTLS half-up; Vercel uses read-only Neon role wk_vercel.
No secrets in this card.