# Minimal Next.js SEO Site (Spec + Gatekeeper)

This is a tiny spec you can use to sanity-check AutoCoder on a Node/Next stack without any external APIs.

## Quick Start (Windows)

```powershell
$proj = "G:\Apps\demo-minimal-nextjs-seo"
mkdir $proj -Force | Out-Null
mkdir "$proj\prompts" -Force | Out-Null

copy "G:\Apps\autocoder\docs\examples\minimal-nextjs-seo-site\app_spec.txt" "$proj\prompts\app_spec.txt"
copy "G:\Apps\autocoder\docs\examples\minimal-nextjs-seo-site\autocoder.yaml" "$proj\autocoder.yaml"

# Optional: scaffold the standard prompt files so you can tweak them per-project
python -c "from pathlib import Path; from autocoder.agent.prompts import scaffold_project_prompts; scaffold_project_prompts(Path(r'$proj'))"

autocoder agent --project-dir $proj
```

## Notes

- `autocoder.yaml` tells Gatekeeper what to run (framework-agnostic verification).
- For a quick parallel run (after features exist): `autocoder parallel --project-dir $proj --parallel 3`.

