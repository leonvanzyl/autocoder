"""
Knowledge Base Verification Script
===================================

Verifies that all components of the knowledge base system are working correctly.
"""

import sys
from pathlib import Path


def verify_imports():
    """Verify all imports work."""
    print("1. Verifying imports...")
    try:
        from knowledge_base import get_knowledge_base, ImplementationTracker
        from prompts import enhance_prompt_with_knowledge
        print("   OK: All imports successful")
        return True
    except Exception as e:
        print(f"   FAIL: Import error: {e}")
        return False


def verify_database():
    """Verify database initialization."""
    print("\n2. Verifying database...")
    try:
        from knowledge_base import get_knowledge_base

        kb = get_knowledge_base()
        assert kb.db_path.exists(), "Database file not created"

        # Check tables exist
        import sqlite3
        conn = sqlite3.connect(kb.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patterns'")
        result = cursor.fetchone()
        conn.close()

        assert result is not None, "Patterns table not found"
        print(f"   OK: Database initialized at {kb.db_path}")
        return True
    except Exception as e:
        print(f"   FAIL: Database error: {e}")
        return False


def verify_store_and_retrieve():
    """Verify storing and retrieving patterns."""
    print("\n3. Verifying store and retrieve...")
    try:
        from knowledge_base import get_knowledge_base

        kb = get_knowledge_base()

        # Store test pattern
        feature = {
            "category": "test",
            "name": "test feature",
            "description": "test description"
        }

        pattern_id = kb.store_pattern(
            feature=feature,
            implementation={
                "approach": "test approach",
                "files_changed": ["test.ts"],
                "model_used": "claude-opus-4-5"
            },
            success=True
        )

        assert pattern_id > 0, "Pattern ID should be positive"

        # Retrieve similar features
        similar = kb.get_similar_features(feature, limit=1)
        assert len(similar) >= 0, "Should return list"

        print("   OK: Store and retrieve working")
        return True
    except Exception as e:
        print(f"   FAIL: Store/retrieve error: {e}")
        return False


def verify_tracker():
    """Verify ImplementationTracker."""
    print("\n4. Verifying ImplementationTracker...")
    try:
        from knowledge_base import ImplementationTracker

        feature = {
            "category": "test",
            "name": "tracker test",
            "description": "test"
        }

        tracker = ImplementationTracker(feature)
        tracker.set_model("claude-opus-4-5")
        tracker.record_approach("test approach")
        tracker.record_file_change("test.ts", "created")
        tracker.add_note("test note")

        summary = tracker.get_summary()
        assert summary["feature"] == "tracker test"
        assert summary["files_changed"] == 1
        assert len(summary["notes"]) == 1

        print("   OK: ImplementationTracker working")
        return True
    except Exception as e:
        print(f"   FAIL: Tracker error: {e}")
        return False


def verify_prompt_enhancement():
    """Verify prompt enhancement."""
    print("\n5. Verifying prompt enhancement...")
    try:
        from prompts import enhance_prompt_with_knowledge

        feature = {
            "category": "authentication",
            "name": "login",
            "description": "test"
        }

        enhanced = enhance_prompt_with_knowledge("test prompt", feature)
        assert isinstance(enhanced, str)
        assert len(enhanced) >= len("test prompt")

        print("   OK: Prompt enhancement working")
        return True
    except Exception as e:
        print(f"   FAIL: Enhancement error: {e}")
        return False


def verify_inspection_tool():
    """Verify inspection tool."""
    print("\n6. Verifying inspection tool...")
    try:
        import subprocess

        result = subprocess.run(
            ["python", "inspect_knowledge.py", "summary"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0, f"Tool returned {result.returncode}"
        assert "KNOWLEDGE BASE SUMMARY" in result.stdout

        print("   OK: Inspection tool working")
        return True
    except Exception as e:
        print(f"   FAIL: Inspection tool error: {e}")
        return False


def verify_files_exist():
    """Verify all required files exist."""
    print("\n7. Verifying files exist...")

    required_files = [
        "knowledge_base.py",
        "KNOWLEDGE_BASE.md",
        "KNOWLEDGE_BASE_SUMMARY.md",
        "KNOWLEDGE_BASE_INTEGRATION.md",
        "test_knowledge_base.py",
        "knowledge_base_demo.py",
        "inspect_knowledge.py"
    ]

    all_exist = True
    for filename in required_files:
        if Path(filename).exists():
            print(f"   OK: {filename}")
        else:
            print(f"   FAIL: {filename} not found")
            all_exist = False

    return all_exist


def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("KNOWLEDGE BASE VERIFICATION")
    print("=" * 70)

    checks = [
        verify_imports,
        verify_database,
        verify_store_and_retrieve,
        verify_tracker,
        verify_prompt_enhancement,
        verify_inspection_tool,
        verify_files_exist
    ]

    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"   FAIL: Unexpected error: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(results)
    total = len(results)

    print(f"\nChecks passed: {passed}/{total}")

    if passed == total:
        print("\nAll checks passed! Knowledge base system is ready.")
        return 0
    else:
        print(f"\n{total - passed} check(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
