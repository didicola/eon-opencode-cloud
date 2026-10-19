# freebuff-cloud — freebuff agent runner (EON cloud, zero local machines)

Run the official freebuff CLI entirely on GitHub Actions (public repo = free minutes).
No phone, no twin, no ubuntu — the task executes server-side.

## Usage (owner)

1. GitHub → `didicola/eon-opencode-cloud` → **Actions** → **freebuff-cloud** → **Run workflow**
2. Fill in:
   - `task` — the coding task text (required)
   - `repo_url` — optional git URL to clone into `work/` first
   - `max_minutes` — cap for the turn (default 30)
3. Read the transcript in the run **Summary** + artifact `freebuff-out`.

## How it works

- `run_freebuff.py` — PTY driver: launches `freebuff --trust-agents` in `work/`,
  types the task, captures the full TUI stream (raw + ANSI-cleaned), classifies
  the outcome (ran / login_required / timeout).
- Exit codes: `0` ran · `2` startup failure · `3` timeout · `4` login gate.

## Auth (secrets, optional)

- `FREEBUFF_CREDS_B64` — base64 of freebuff `credentials.json` (full mode).
  Seeded to `~/.config/manicode/credentials.json` in the runner.
- `FREEBUFF_API_KEY` — authToken value (fallback; exported as `CODEBUFF_API_KEY`).

Without secrets the CLI hits the login gate; the log marks `login_required`.

## Notes

- Tasks with newlines are flattened to one line for the TUI input.
- Artifacts: `freebuff.txt` (cleaned transcript), `freebuff.raw` (raw bytes).
