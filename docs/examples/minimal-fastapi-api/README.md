# Minimal FastAPI API (Spec + Gatekeeper)

This spec is designed to exercise the Python test pipeline (pytest) and a tiny SQLite-backed API.

## Quick Start (Windows)

```powershell
$proj = "G:\Apps\demo-minimal-fastapi"
mkdir $proj -Force | Out-Null
mkdir "$proj\prompts" -Force | Out-Null

copy "G:\Apps\autocoder\docs\examples\minimal-fastapi-api\app_spec.txt" "$proj\prompts\app_spec.txt"
copy "G:\Apps\autocoder\docs\examples\minimal-fastapi-api\autocoder.yaml" "$proj\autocoder.yaml"

python -c "from pathlib import Path; from autocoder.agent.prompts import scaffold_project_prompts; scaffold_project_prompts(Path(r'$proj'))"

autocoder agent --project-dir $proj
```

## Notes

- The `{VENV_PY}` placeholder in `autocoder.yaml` is resolved by Gatekeeper to a project-local venv python when available.

