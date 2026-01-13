---
name: gsd-to-autocoder-spec
description: |
  Convert GSD codebase mapping to Autocoder app_spec.txt. This skill should be used when
  the user has run /gsd:map-codebase and wants to use Autocoder on an existing project.
  Triggers: "convert to autocoder", "gsd to spec", "create app_spec from codebase",
  "use autocoder on existing project", after /gsd:map-codebase completion.
---

# GSD to Autocoder Spec Converter

Converts `.planning/codebase/*.md` (GSD mapping output) to `prompts/app_spec.txt` (Autocoder format).

## When to Use

- After running `/gsd:map-codebase` on an existing project
- When onboarding an existing codebase to Autocoder
- User wants Autocoder to continue development on existing code

## Prerequisites

The project must have `.planning/codebase/` with these files:
- `STACK.md` - Technology stack (required)
- `ARCHITECTURE.md` - Code architecture (required)
- `STRUCTURE.md` - Directory layout (required)
- `CONVENTIONS.md` - Code conventions (optional)
- `INTEGRATIONS.md` - External services (optional)

## Process

<step name="verify_input">
### Step 1: Verify GSD Mapping Exists

```bash
ls -la .planning/codebase/
```

**Required files:** STACK.md, ARCHITECTURE.md, STRUCTURE.md

If `.planning/codebase/` doesn't exist:
```
GSD codebase mapping not found.

Run /gsd:map-codebase first to analyze the existing codebase.
```
Stop workflow.
</step>

<step name="read_codebase_docs">
### Step 2: Read Codebase Documentation

Read all available GSD documents:

```bash
cat .planning/codebase/STACK.md
cat .planning/codebase/ARCHITECTURE.md
cat .planning/codebase/STRUCTURE.md
cat .planning/codebase/CONVENTIONS.md 2>/dev/null || true
cat .planning/codebase/INTEGRATIONS.md 2>/dev/null || true
```

Extract key information:
- **From STACK.md:** Languages, frameworks, dependencies, runtime, ports
- **From ARCHITECTURE.md:** Patterns, layers, data flow, entry points
- **From STRUCTURE.md:** Directory layout, key file locations, naming conventions
- **From INTEGRATIONS.md:** External APIs, services, databases
</step>

<step name="read_package_json">
### Step 3: Extract Project Metadata

```bash
cat package.json 2>/dev/null | head -20 || echo "No package.json"
```

Extract:
- Project name
- Version
- Main dependencies
</step>

<step name="generate_spec">
### Step 4: Generate app_spec.txt

Create `prompts/` directory:
```bash
mkdir -p prompts
```

**Mapping GSD Documents to Autocoder Spec:**

| GSD Source | Autocoder Target |
|------------|------------------|
| STACK.md Languages | `<technology_stack>` |
| STACK.md Frameworks | `<frontend>`, `<backend>` |
| STACK.md Dependencies | `<prerequisites>` |
| ARCHITECTURE.md Layers | `<core_features>` categories |
| ARCHITECTURE.md Data Flow | `<key_interactions>` |
| ARCHITECTURE.md Entry Points | `<implementation_steps>` |
| STRUCTURE.md Layout | `<ui_layout>` (if frontend) |
| INTEGRATIONS.md APIs | `<api_endpoints_summary>` |
| INTEGRATIONS.md Services | `<prerequisites>` |

**Feature Generation Guidelines:**

1. Analyze existing code structure to infer implemented features
2. Each feature must be testable: "User can...", "System displays...", "API returns..."
3. Group features by category matching architecture layers
4. Target feature counts by complexity:
   - Simple CLI/utility: ~100-150 features
   - Medium web app: ~200-250 features
   - Complex full-stack: ~300-400 features

**Write the spec file** using the XML format from [references/app-spec-format.md](references/app-spec-format.md):

```bash
cat > prompts/app_spec.txt << 'EOF'
<project_specification>
  <project_name>{from package.json or directory}</project_name>

  <overview>
    {Synthesized from ARCHITECTURE.md overview}
  </overview>

  <technology_stack>
    <frontend>
      <framework>{from STACK.md}</framework>
      <styling>{from STACK.md}</styling>
      <port>{from STACK.md or default 3000}</port>
    </frontend>
    <backend>
      <runtime>{from STACK.md}</runtime>
      <database>{from STACK.md or INTEGRATIONS.md}</database>
      <port>{from STACK.md or default 3001}</port>
    </backend>
  </technology_stack>

  <prerequisites>
    <environment_setup>
      {from STACK.md Runtime + INTEGRATIONS.md requirements}
    </environment_setup>
  </prerequisites>

  <core_features>
    <!-- Group by ARCHITECTURE.md layers -->
    <{layer_name}>
      - {Feature derived from code analysis}
      - {Feature derived from code analysis}
    </{layer_name}>
  </core_features>

  <api_endpoints_summary>
    {from INTEGRATIONS.md or inferred from STRUCTURE.md routes/}
  </api_endpoints_summary>

  <key_interactions>
    {from ARCHITECTURE.md Data Flow}
  </key_interactions>

  <success_criteria>
    <functionality>
      - All existing features continue working
      - New features integrate seamlessly
      - No regression in core functionality
    </functionality>
  </success_criteria>
</project_specification>
EOF
```
</step>

<step name="verify_output">
### Step 5: Verify Generated Spec

```bash
head -100 prompts/app_spec.txt
echo "---"
grep -c "User can\|System\|API\|Feature" prompts/app_spec.txt || echo "0"
```

**Validation checklist:**
- [ ] `<project_specification>` root tag present
- [ ] `<project_name>` matches actual project
- [ ] `<technology_stack>` reflects STACK.md
- [ ] `<core_features>` has categorized features
- [ ] Features are specific and testable
</step>

<step name="completion">
### Step 6: Report Completion

Output:
```
app_spec.txt generated from GSD codebase mapping.

Source: .planning/codebase/*.md
Output: prompts/app_spec.txt

Next: Start Autocoder

  cd {project_dir}
  python ~/projects/autocoder/start.py

Or via UI:
  ~/projects/autocoder/start_ui.sh

The Initializer will create features.db from this spec.
```
</step>

## XML Format Reference

See [references/app-spec-format.md](references/app-spec-format.md) for complete XML structure with all sections.

## Error Handling

| Error | Resolution |
|-------|------------|
| No .planning/codebase/ | Run `/gsd:map-codebase` first |
| Missing required files | Re-run GSD mapping |
| Cannot infer features | Ask user for clarification |
