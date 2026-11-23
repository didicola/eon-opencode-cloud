# EON Cloud AGI State

Updated: 2026-11-23T23:49:14Z
Worker: agi-cloud-v10 (v10); store=do-storage.
Cycles: 29006. Passed: 28004. Failed: 1002. Score: 96.5%.
Self-mods: 1159. Lessons: 50. Provisions: 32. Goals: 20.
Best prompt: direct. LLM accuracy: 76.7%.

Domains: math 1304/1366 (95.5%); logic 1130/1370 (82.5%); string 1556/1623 (95.9%); compare 3052/3150 (96.9%); alphasort 1250/1266 (98.7%); temporal 1232/1260 (97.8%); causal 1240/1246 (99.5%); spatial 1254/1255 (99.9%); creative 1244/1268 (98.1%).
Last run: 2026-11-23T23:47:08.663Z.
Transfer probe: spatial -> revlex delta 0.4 (base 0.4 / transfer 0.8).
Driver: armed.


Architecture map: https://github.com/didicola/eon-opencode-cloud/blob/main/ARCHITECTURE.md
Known gaps: termux2 .3 last up 2026-10-21, LAN unverified 2026-10-27; ubuntu .72 phone-unreachable; Vercel read-only. /health is a 200-for-all stub; this card uses /self + /state + /driver.
No secrets in this card.