# Multi-Model Generate (Plan/Spec Drafts)

AutoCoder can draft a **project spec** (`prompts/app_spec.txt`) or a **plan** (`prompts/plan.md`) using external CLIs like **Codex** and **Gemini**, with optional synthesis.

This keeps the coding runtime on **Claude Agent SDK**, while letting other LLMs contribute alternative drafts.

## Web UI

Open the Settings page for a project and use the **Generate** tab:

- `http://127.0.0.1:8888/#/settings/generate`

If `codex`/`gemini` are not on your `PATH`, those agents will be disabled and generation can still work via Claude synthesis.

## CLI

Generate a spec:

```powershell
autocoder generate --project-dir G:\Apps\my-project --kind spec --prompt "Build an SEO affiliate site for one casino game."
```

Generate a plan from a file:

```powershell
autocoder generate --project-dir G:\Apps\my-project --kind plan --prompt-file .\idea.md
```

## Options

- `--agents codex,gemini` (either/both; missing CLIs are skipped)
- `--synthesizer none|claude|codex|gemini`
- `--no-synthesize` (write drafts only)
- `--out <path>` (override output file)
- `--timeout-s 300`

Drafts + metadata are written under:
- `<project>/.autocoder/drafts/<kind>/<timestamp>/`

## Env vars (optional)

- `AUTOCODER_GENERATE_AGENTS=codex,gemini`
- `AUTOCODER_GENERATE_SYNTHESIZER=claude`
- `AUTOCODER_GENERATE_CLAUDE_MODEL=sonnet`
- `AUTOCODER_GENERATE_TIMEOUT_S=300`
