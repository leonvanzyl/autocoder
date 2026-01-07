---
description: Create commit with detailed comment
---

Please create a comprehensive checkpoint commit with the following steps:

1. **Initialize Git if needed**: Run `git init` if git has not been instantiated for the project yet.

2. **Analyze all changes**:

   - Run `git status` to see all tracked and untracked files
   - Run `git diff` to see detailed changes in tracked files
   - Run `git log -5 --oneline` to understand the commit message style of this repository

3. **Stage everything**:

   - Add ALL tracked changes (modified and deleted files)
   - Add ALL untracked files (new files)
   - Use `git add -A` or `git add .` to stage everything

4. **Create a detailed commit message**:

   - **First line**: Write a clear, concise summary (50-72 chars) describing the primary change
     - Use imperative mood (e.g., "Add feature" not "Added feature")
     - Examples: "feat: add user authentication", "fix: resolve database connection issue", "refactor: improve API route structure"
   - **Body**: Provide a detailed description including:
     - What changes were made (list of key modifications)
     - Why these changes were made (purpose/motivation)
     - Any important technical details or decisions
     - Breaking changes or migration notes if applicable
   - **Footer**: Include co-author attribution as shown in the Git Safety Protocol

5. **Execute the commit**: Create the commit with the properly formatted message following this repository's conventions.

IMPORTANT:

- Do NOT skip any files - include everything
- Make the commit message descriptive enough that someone reviewing the git log can understand what was accomplished
- Follow the project's existing commit message conventions (check git log first)
- Include the Claude Code co-author attribution in the commit message
