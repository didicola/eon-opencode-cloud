# EON Cloud AGI State

Updated: 2026-11-25T21:37:40Z
Worker: agi-cloud-v10 (v10); store=do-storage.
Cycles: 30346. Passed: 29256. Failed: 1090. Score: 96.4%.
Self-mods: 1212. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 76.7%.

Domains: math 1368/1430 (95.7%); logic 1185/1433 (82.7%); string 1621/1689 (96.0%); compare 3107/3205 (96.9%); alphasort 1311/1328 (98.7%); temporal 1289/1317 (97.9%); causal 1302/1308 (99.5%); spatial 1316/1318 (99.8%); creative 1303/1327 (98.2%).
Last run: 2026-11-25T21:31:56.480Z.
Transfer probe: spatial -> revlex delta 0.4 (base 0.6 / transfer 1).
Driver: armed.


Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 .3 last up 2026-10-21, LAN unverified 2026-10-27; ubuntu .72 phone-unreachable; Vercel read-only. /health is a 200-for-all stub; this card uses /self + /state + /driver.
No secrets in this card.