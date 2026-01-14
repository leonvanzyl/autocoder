# Multi-Model Review (Codex + Gemini CLIs)

AutoCoder can run an optional **external** code review step in Gatekeeper using local CLIs like **Codex** and **Gemini**.
This keeps the coding runtime on **Claude Agent SDK**, while letting other LLMs provide a second opinion.

## Why external CLIs?

- Separate auth/config per provider
- Read-only review (diff-in → JSON-out)
- Easy to skip if a CLI isn’t installed
- Extensible to more tools later

## Enable (project config)

In the target project’s `autocoder.yaml`:

```yaml
review:
  enabled: true
  mode: gate            # off | advisory | gate
  type: multi_cli       # none | command | claude | multi_cli
  agents: [codex, gemini]
  consensus: majority   # majority | all | any
  timeout: 300
  codex_model: gpt-5.2
  codex_reasoning_effort: high
  gemini_model: gemini-3-pro-preview
```

## Enable (Web UI)

Settings page → **Advanced → Automation → Review**:
- Type: `multi_cli (codex/gemini)`
- Agents: `codex,gemini`
- Consensus: `majority` / `all` / `any`

## Required tooling

- Codex CLI in `PATH` (`codex`)
- Gemini CLI in `PATH` (`gemini`)

If a CLI is missing, AutoCoder will **skip that reviewer** and continue using the remaining ones.

## Output format

Each reviewer must return JSON shaped like:

```json
{
  "approved": true,
  "reason": "short summary",
  "findings": [
    { "severity": "P1", "message": "…", "file": "src/app.ts" }
  ]
}
```
