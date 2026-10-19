# VS Code / editor agents on the EON matrix

Matrix endpoint: `https://cloud-brain.eon-sovereign.workers.dev/v1` (OpenAI-compatible ·
`Authorization: Bearer eon-cloud` · model = any alias — the gateway picks the adjusted
model server-side, that is why it is called adjusted: you cannot exhaust it by wrong name).

The GitHub workflow `.github/workflows/agents-matrix.yml` proves this stack headlessly
on free runners (daily smoke at 06:43Z + manual dispatch). For YOUR desktop editor:

## 1) Claude Code (CLI + VS Code extension)
- Install the router: `npm i -g @musistudio/claude-code-router` (config at
  `~/.claude-code-router/config.json` — same shape as in the workflow).
- `ccr start` (serves 127.0.0.1:3456), then set environment:
  `ANTHROPIC_BASE_URL=http://127.0.0.1:3456` and `ANTHROPIC_AUTH_TOKEN=ccr-local`
- The Claude Code extension inherits this env → the whole extension runs on the matrix, $0.

## 2) Codex (CLI + VS Code extension)
- `~/.codex/config.toml`:
  ```toml
  model = "deepseek-chat"
  model_provider = "eon"
  approval_policy = "never"
  sandbox_mode = "read-only"

  [model_providers.eon]
  name = "EON Cloud Brain"
  base_url = "https://cloud-brain.eon-sovereign.workers.dev/v1"
  env_key = "EON_API_KEY"
  wire_api = "chat"
  ```
- `EON_API_KEY=eon-cloud` in env → `codex` CLI and the Codex extension both use it.

## 3) Continue / Cline / Roo Code (VS Code AI extensions)
- Provider: **OpenAI Compatible**
- Base URL: `https://cloud-brain.eon-sovereign.workers.dev/v1`
- API key: `eon-cloud`
- Model: `deepseek-chat` (alias; the gateway resolves to the adjusted model)

## 4) MCP — 37 EON tools (incl. memory) for ANY of the above
- Run `scripts/mcp-auth-bridge.py` locally with `MCP_ADMIN_TOKEN` in its env
  (the token never leaves that process; clients never see it).
- Point the editor's MCP client at `http://127.0.0.1:8788/mcp`.

## Adding more agents ("and others")
The workflow takes `agent` + `task` inputs; new CLIs slot in the same way
(OpenAI-compatible base URL + optional MCP bridge). Proven so far: opencode,
claude-code, codex. Best-effort: aider. Next candidates: gemini-cli fork,
cline headless, custom scripts.
