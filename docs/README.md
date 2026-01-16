# Autonomous Coder - Documentation

This directory contains detailed documentation for the autonomous coding system.

## 📚 Documentation Index

### Before you go digging

- Most day-to-day usage is covered in the root `README.md`.
- If you want a place for personal notes (paths, local setup quirks), copy `docs/LOCAL_DEV_TEMPLATE.md` to `LOCAL_DEV.md` (it’s git-ignored).

### Quick Start Guides

- **[PARALLEL_MODE_UI.md](PARALLEL_MODE_UI.md)** - How to use parallel mode from the web UI
  - Toggle parallel mode
  - Select agent count (1-5)
  - Choose model presets (Quality, Balanced, Economy, Cheap, Experimental)
  - 3x faster development with multiple agents

### Architecture Documentation

- **[SYSTEM_COMPLETE.md](SYSTEM_COMPLETE.md)** - Complete system overview
  - All components and features
  - Architecture diagrams
  - Quick start guide
  - Production checklist

- **[MCP_ARCHITECTURE.md](MCP_ARCHITECTURE.md)** - Hybrid MCP architecture
  - System code uses direct imports (fast)
  - Agents use MCP tools (capable)
  - Why both approaches are needed
  - Usage examples

### Workflow Guides

- **[TDD_WORKFLOW_WITH_MCP.md](TDD_WORKFLOW_WITH_MCP.md)** - Test-driven development workflow
  - Agents follow TDD (Red-Green-Refactor)
  - MCP tools for test detection and execution
  - Gatekeeper verification
  - Complete workflow examples

- **[RELIABILITY_PIPELINE.md](RELIABILITY_PIPELINE.md)** - Reliability mechanisms in parallel mode
  - Retry/backoff + loop breaker (`BLOCKED`)
  - Evidence-first Gatekeeper artifacts
  - Windows worktree cleanup queue
  - Log/artifact retention
  - Web UI diagnostics fixtures

### Component Documentation

- **[TEST_DETECTION_IMPROVEMENTS.md](TEST_DETECTION_IMPROVEMENTS.md)** - Test framework detection
  - Supports 12+ frameworks (pytest, Jest, Vitest, XCTest, Go test, etc.)
  - CI-safe test commands (prevents watch mode hangs)
  - iOS/Swift support with Fastlane
  - Test file generation in correct format

- **[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)** - Learning system
  - Stores implementation patterns from completed features
  - Jaccard similarity matching
  - Prompt enhancement with reference examples
  - Model performance tracking by category

- **[KNOWLEDGE_BASE_INTEGRATION.md](KNOWLEDGE_BASE_INTEGRATION.md)** - Integration guide
  - How to integrate knowledge base into your workflow
  - API reference
  - Usage examples

- **[KNOWLEDGE_BASE_SUMMARY.md](KNOWLEDGE_BASE_SUMMARY.md)** - Quick reference
  - Key features at a glance
  - Usage patterns

### Development Resources

- **[CRITICAL_FIXES.md](CRITICAL_FIXES.md)** - Recent critical fixes
  - Async/sync mismatch fix
  - Dirty state prevention in gatekeeper
  - JavaScript test file extensions
  - Production-ready checklist

- **[PROMPT_FOR_OTHER_AI.md](PROMPT_FOR_OTHER_AI.md)** - Prompt for other AI assistants
  - Context when asking other AI models for help
  - System architecture overview
  - Key design decisions

- **[LOCAL_DEV_TEMPLATE.md](LOCAL_DEV_TEMPLATE.md)** - Template for local-only notes (copy to `LOCAL_DEV.md`)

## 🎯 Documentation by Use Case

### For New Users

1. **Start here:** [PARALLEL_MODE_UI.md](PARALLEL_MODE_UI.md) - Learn to use the UI
2. **Understand the system:** [SYSTEM_COMPLETE.md](SYSTEM_COMPLETE.md) - Complete overview
3. **Learn TDD workflow:** [TDD_WORKFLOW_WITH_MCP.md](TDD_WORKFLOW_WITH_MCP.md) - How agents work

### For Developers

1. **Architecture:** [MCP_ARCHITECTURE.md](MCP_ARCHITECTURE.md) - System design
2. **Components:** [TEST_DETECTION_IMPROVEMENTS.md](TEST_DETECTION_IMPROVEMENTS.md) - Test detection
3. **Knowledge base:** [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) - Learning system
4. **Recent fixes:** [CRITICAL_FIXES.md](CRITICAL_FIXES.md) - Latest improvements

### For Troubleshooting

1. **Quick fixes:** [CRITICAL_FIXES.md](CRITICAL_FIXES.md) - Common issues and solutions
2. **Testing issues:** [TEST_DETECTION_IMPROVEMENTS.md](TEST_DETECTION_IMPROVEMENTS.md) - Framework detection

## 📊 System Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                   SYSTEM CODE (Python)                      │
│  Orchestrator, Gatekeeper, WorktreeManager                 │
│  ✅ Direct imports = FAST!                                  │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Coordinates
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     AGENTS (LLMs)                            │
│  Worker agents implementing features                       │
│  ✅ MCP tools = CAPABLE!                                   │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Key Features

- **⚡ 3x Faster** - Parallel agents with isolated worktrees
- **🧠 Continuous Learning** - Knowledge base improves over time
- **💰 Cost Optimized** - Smart model selection (Opus + Haiku)
- **🛡️ Quality Gates** - Gatekeeper ensures tests pass
- **🔄 Crash Recovery** - Heartbeat monitoring + auto-recovery
- **📋 TDD Workflow** - Agents write tests first
- **🔧 Framework Agnostic** - Works with any project

## 🔗 Related Files

- Root [README.md](../README.md) - Main project README
- [CLAUDE.md](../CLAUDE.md) - Instructions for Claude Code
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [research/](../research/) - Research notes and exploration
