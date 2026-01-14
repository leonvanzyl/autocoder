# Fortune of Dragons Affiliate Demo Spec

This folder contains a ready-to-use `app_spec.txt` for testing AutoCoder on a realistic SEO/affiliate site.

## Quick Start

```powershell
$proj = \"G:\\Apps\\demo-fod-affiliate\"
mkdir $proj -Force | Out-Null
mkdir \"$proj\\prompts\" -Force | Out-Null
copy \"G:\\Apps\\autocoder\\docs\\examples\\fortune-of-dragons-affiliate\\app_spec.txt\" \"$proj\\prompts\\app_spec.txt\"

# optional: copy templates so you can tweak prompts per-project
python -c \"from pathlib import Path; from autocoder.agent.prompts import scaffold_project_prompts; scaffold_project_prompts(Path(r'$proj'))\"

# run single-agent (first run will generate the feature list)
autocoder agent --project-dir $proj

# or run parallel (after features exist)
autocoder parallel --project-dir $proj --parallel 3 --preset balanced
```

## Notes

- For best results, add runtime artifacts to your project’s `.gitignore` (AutoCoder itself will also ignore them during verification):
  - `.autocoder/`
  - `worktrees/`
  - `agent_system.db` (and `agent_system.db-*`)
- If you don’t want Gatekeeper to require tests for this project, set `AUTOCODER_ALLOW_NO_TESTS=1` (not recommended long-term).
- Parallel runs allocate per-worker ports automatically; workers also export `PORT` and `VITE_PORT` for compatibility with common dev servers.
