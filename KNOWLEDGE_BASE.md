# Knowledge Base System

A learning system that stores implementation patterns from completed features to improve future implementations. Inspired by scagent research, simplified for feature-level learning.

## Overview

The knowledge base:
- **Learns from experience**: Stores patterns from both successful and failed feature implementations
- **Enhances prompts**: Provides relevant examples from similar past features
- **Tracks performance**: Records which models and approaches work best for different feature categories
- **Cross-project learning**: Uses global knowledge base (`~/.autocoder/knowledge.db`) to share insights across projects

## Architecture

```
~/.autocoder/knowledge.db (SQLite)
└── patterns table
    ├── id
    ├── category (e.g., "authentication", "ui", "api")
    ├── feature_name
    ├── description
    ├── approach (what was done)
    ├── files_changed (JSON array)
    ├── model_used (e.g., "claude-opus-4-5")
    ├── success (boolean)
    ├── created_at
    ├── attempts (how many tries)
    └── lessons_learned (key insights)
```

## API Usage

### 1. Enhancing Prompts with Past Examples

```python
from prompts import enhance_prompt_with_knowledge

feature = {
    "category": "authentication",
    "name": "social login",
    "description": "Add OAuth login with Google and GitHub"
}

base_prompt = "Implement the following feature..."

# Enhances prompt with similar past examples
enhanced_prompt = enhance_prompt_with_knowledge(base_prompt, feature)
```

### 2. Tracking Implementations

```python
from knowledge_base import ImplementationTracker

# Start tracking
tracker = ImplementationTracker(feature, project_dir)
tracker.set_model("claude-opus-4-5")

# During implementation
tracker.record_approach("Used NextAuth.js with OAuth providers")
tracker.record_file_change("src/app/api/auth/[...nextauth].ts", "created")
tracker.record_file_change("src/components/AuthButton.tsx", "created")
tracker.add_note("NextAuth.js handles session management automatically")

# After completion
tracker.save_to_knowledge_base(
    success=True,
    attempts=1,
    lessons_learned="NextAuth.js is production-ready with built-in OAuth"
)
```

### 3. Direct Storage

```python
from knowledge_base import get_knowledge_base

kb = get_knowledge_base()

kb.store_pattern(
    feature={
        "category": "ui",
        "name": "modal dialog",
        "description": "Create reusable modal component"
    },
    implementation={
        "approach": "Used Radix UI Dialog primitive with Tailwind",
        "files_changed": [
            "src/components/Modal.tsx",
            "src/components/Modal.stories.tsx"
        ],
        "model_used": "claude-opus-4-5"
    },
    success=True,
    attempts=1,
    lessons_learned="Radix UI primitives are better for accessibility than building from scratch"
)
```

### 4. Finding Similar Features

```python
kb = get_knowledge_base()

# Find top 3 similar features
similar = kb.get_similar_features(feature, limit=3)

for pattern in similar:
    print(f"Feature: {pattern['feature_name']}")
    print(f"Success: {pattern['success']}")
    print(f"Approach: {pattern['approach']}")
    print(f"Files: {pattern['files_changed']}")
    if pattern['lessons_learned']:
        print(f"Lesson: {pattern['lessons_learned']}")
```

### 5. Learning Best Models

```python
kb = get_knowledge_base()

# Get best model for a category
best_model = kb.get_best_model("authentication")
# Returns: "claude-opus-4-5" (model with highest success rate)

# Get success statistics
stats = kb.get_success_rate("authentication")
# Returns: {
#   "total_patterns": 5,
#   "success_count": 4,
#   "success_rate": 80.0,
#   "avg_attempts": 1.2
# }
```

### 6. Getting Insights

```python
kb = get_knowledge_base()

# Overall summary
summary = kb.get_summary()
# Returns: {
#   "total_patterns": 25,
#   "by_category": {"authentication": 5, "ui": 12, "api": 8},
#   "overall_success_rate": 82.5,
#   "top_models": {"claude-opus-4-5": 18, "claude-sonnet-4-5": 7}
# }

# Common successful approaches
approaches = kb.get_common_approaches("ui", limit=5)
# Returns: [
#   {
#     "approach": "Used Radix UI primitives...",
#     "total": 3,
#     "successes": 3,
#     "success_rate": 100.0
#   },
#   ...
# ]
```

## Integration with Agent

The knowledge base integrates with the agent in several ways:

### 1. Prompt Enhancement (prompts.py)

```python
from prompts import enhance_prompt_with_knowledge

# Automatically called before sending prompt to agent
enhanced_prompt = enhance_prompt_with_knowledge(base_prompt, current_feature)
```

### 2. MCP Integration (future)

The knowledge base could be exposed as MCP tools:
- `knowledge_get_similar` - Find similar features
- `knowledge_get_best_model` - Get recommended model
- `knowledge_store_pattern` - Store implementation result
- `knowledge_get_reference_prompt` - Get enhancement text

## Examples

See `knowledge_base_demo.py` for complete examples:
- Prompt enhancement
- Implementation tracking
- Learning from failures
- Model selection
- Getting insights

Run the demo:
```bash
python knowledge_base_demo.py
```

## Testing

Run the test suite:
```bash
python test_knowledge_base.py
```

## Database Location

- **Path**: `~/.autocoder/knowledge.db`
- **Format**: SQLite
- **Scope**: Global across all projects (enables cross-project learning)

## Design Decisions

1. **Global knowledge base**: Shared across projects to learn from all implementations
2. **Simple similarity matching**: Uses keyword matching (Jaccard similarity) - could be upgraded to embeddings
3. **Stores failures**: Failed attempts are valuable for learning what doesn't work
4. **Tracks attempts**: Records how many tries were needed for success
5. **Lessons learned**: Explicit field for key insights (not just implicit from patterns)

## Future Enhancements

- **Embedding-based similarity**: Use vector embeddings for better semantic matching
- **Automatic tracking**: Integrate with agent to automatically track file changes
- **Pattern recognition**: Detect common patterns across implementations
- **Conflict detection**: Warn when approach contradicts learned lessons
- **Performance metrics**: Track implementation time, code quality, test coverage
- **A/B testing**: Compare different approaches for same feature type
- **Project-specific overrides**: Allow project-specific exceptions to global patterns

## Inspiration

This system is inspired by [scagent](https://github.com/transform-group/scagent), particularly the knowledge base pattern for continuous learning from code audits. Adapted for feature implementation learning instead of security auditing.

Key differences from scagent:
- **Simpler**: Focuses on feature patterns, not code issue detection
- **Positive & negative**: Learns from both successes and failures
- **Agent-focused**: Designed for autonomous coding agents
- **Cross-project**: Global knowledge sharing across projects
