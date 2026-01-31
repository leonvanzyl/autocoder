# Future Enhancements

A running list of ideas and improvements to implement when time permits.

---

## Settings & Configuration

### Provider Selection in Settings UI
- Add "Provider" section to settings with options: `Anthropic API` / `Vertex AI` / `Ollama`
- Show relevant config fields based on selection
- Add "Test Connection" button to verify credentials
- Currently Vertex AI and Ollama are configured via `.env` file only

---

## UI/UX Improvements

*(Add ideas here)*

---

## Agent & Orchestrator

### [DONE] Documentation Admin Agent (Haiku)
- Background agent using Claude Haiku (cheap/fast) for admin tasks
- Integrated into main agent infrastructure (same pattern as initializer/coding/testing)
- Responsibilities:
  - Keep CLAUDE.md and README.md up to date with code changes
  - Maintain CHANGELOG.md with feature additions/fixes
  - Sync documentation with actual behavior
  - Flag outdated documentation for review
- Each project gets its own agent (not shared)
- Uses Claude Code authentication (no separate API key needed)
- Usage: `python autonomous_agent_demo.py --project-dir /path/to/project --agent-type doc-admin --max-iterations 1`

---

## Testing & Quality

*(Add ideas here)*

---

## Documentation

*(Add ideas here)*

---

## Notes

- Priority: 🔴 High | 🟡 Medium | 🟢 Low
- Add `[DONE]` prefix when completed
- Move completed items to a "Completed" section at the bottom if desired
