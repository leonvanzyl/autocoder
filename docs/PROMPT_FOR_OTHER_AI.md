# Prompt for Another AI - Architecture Review

I'm building an autonomous coding agent system that runs multiple Claude agents in parallel to build features faster. I need advice on preventing file conflicts when agents work simultaneously.

## Context

**System Setup:**
- 3-5 Claude agents run in parallel
- Each agent claims features from a SQLite database
- Agents can read/write files using standard file operations
- Agents can go "sideways" (make mistakes, create bad code, get stuck)
- System needs crash recovery and resume capability

**The Problem:**
```
Agent 1 working on "Add user authentication"
  → Creates auth.py
  → Modifies main.py (imports auth)

Agent 2 working on "Add admin login" (simultaneously)
  → Modifies auth.py (adds admin functions)
  → Modifies main.py (imports admin)

CONFLICT: Both agents editing same files!
```

## Two Approaches I'm Considering

### Approach 1: Git Worktrees (From Another Developer)
```python
# Each agent gets isolated working directory
project/
  ├── agent-1/     # Git worktree
  ├── agent-2/     # Git worktree
  └── agent-3/     # Git worktree

# Agent works in isolation, then merges back
def run_agent_in_worktree(agent_id, feature):
    worktree_path = create_worktree(f"agent-{agent_id}")
    # Agent does work here...
    # Then merge back to main directory
    merge_worktree(worktree_path, main_dir)
```

**Pros:**
- True isolation, no conflicts during work
- Can review changes before merging
- Can discard bad work easily

**Cons:**
- Need to handle merge conflicts at the end
- Uses 3x disk space
- More complex (git worktree management)
- Agent could create garbage that you have to merge anyway

### Approach 2: Database File Locking (My Current Idea)
```python
# Lock files when agent starts feature
# Use knowledge base of past features to predict which files will be touched

file_locks:
  - auth.py (locked by agent-1 for feature #5)
  - main.py (locked by agent-1 for feature #5)

Agent 2 tries to claim feature that needs auth.py → BLOCKED
Must wait or work on different feature
```

**Pros:**
- Simpler architecture (shared directory)
- Can use knowledge base to predict conflicts
- No merge step needed

**Cons:**
- Relying on database to prevent conflicts
- If AI goes sideways, could mess up shared files
- Predictions might be wrong
- Single point of failure

## My Concerns

1. **AI Can Go Sideways**: What if Agent 1 creates garbage in auth.py, locks it, then crashes? Agent 2 is blocked from using a critical file.

2. **Database Reliability**: Is it safe to rely on database locks for something this important? What if locks don't get released?

3. **Knowledge Base Accuracy**: Using past patterns to predict file usage seems smart but what if it's wrong?

4. **Recovery**: How do I recover when an agent messes up a file? With git worktrees I could just discard the worktree.

## Questions for You

1. **Which approach would you choose** and why?

2. **What am I missing?** Are there other approaches I haven't considered?

3. **How would YOU handle** the "AI goes sideways" problem in each approach?

4. **Production readiness**: Which is safer for real-world use?

5. **Hybrid approaches**: Is there a way to combine the best of both?

## Technical Context (If Needed)

- Language: Python
- Database: SQLite
- VCS: Git
- Agents: Claude via Anthropic API
- File operations: Standard Python file I/O
- Crash recovery: Need to handle agent crashes gracefully

---

Please be critical and honest. I'd rather hear harsh truths now than build something that will break in production.
