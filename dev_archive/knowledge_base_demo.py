"""
Knowledge Base Integration Example
===================================

Demonstrates how to integrate the knowledge base into the agent workflow:
1. Enhance prompts with past examples
2. Track implementations
3. Store results for learning
"""

from pathlib import Path
from knowledge_base import get_knowledge_base, ImplementationTracker


def example_prompt_enhancement():
    """Example: Enhancing a prompt with knowledge base examples."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Prompt Enhancement")
    print("=" * 70)

    # Current feature to implement
    current_feature = {
        "category": "authentication",
        "name": "social login",
        "description": "Add OAuth login with Google and GitHub providers"
    }

    # Base prompt
    base_prompt = """
    Implement the following feature:
    - Add OAuth authentication with Google and GitHub
    - Use NextAuth.js for session management
    - Create login buttons in the auth modal
    - Handle callback routes properly
    """

    # Enhance with knowledge base
    from prompts import enhance_prompt_with_knowledge

    enhanced_prompt = enhance_prompt_with_knowledge(base_prompt, current_feature)

    print("\nENHANCED PROMPT:")
    print(enhanced_prompt)


def example_implementation_tracking():
    """Example: Tracking an implementation for learning."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Implementation Tracking")
    print("=" * 70)

    feature = {
        "category": "ui",
        "name": "data table",
        "description": "Create a sortable data table with pagination"
    }

    # Start tracking
    tracker = ImplementationTracker(feature)
    tracker.set_model("claude-opus-4-5")

    # Simulate implementation process
    print("\n[Agent] Starting implementation...")

    # Record approach
    tracker.record_approach(
        "Used TanStack Table with React for headless table functionality, "
        "custom pagination logic, and Tailwind for styling"
    )

    # Simulate file changes
    files = [
        "src/components/DataTable.tsx",
        "src/components/DataTable.types.ts",
        "src/components/Pagination.tsx",
        "src/hooks/useSort.ts"
    ]

    for file in files:
        tracker.record_file_change(file, "created")
        print(f"  Created: {file}")

    # Add notes during implementation
    tracker.add_note("TanStack Table has steep learning curve but very flexible")
    tracker.add_note("Server-side pagination better for large datasets")
    tracker.add_note("Column resizing requires react-resizable")

    # Get summary before saving
    summary = tracker.get_summary()
    print(f"\nImplementation Summary:")
    print(f"  Files changed: {summary['files_changed']}")
    print(f"  Duration: {summary['duration_seconds']:.1f}s")
    print(f"  Notes: {len(summary['notes'])} observations")

    # Save successful implementation
    pattern_id = tracker.save_to_knowledge_base(
        success=True,
        attempts=1,
        lessons_learned="TanStack Table is powerful but complex - consider simpler alternatives for basic tables"
    )

    print(f"\n[KnowledgeBase] Saved pattern ID: {pattern_id}")


def example_learning_from_failures():
    """Example: Learning from failed implementations."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Learning from Failures")
    print("=" * 70)

    feature = {
        "category": "api",
        "name": "rate limiting",
        "description": "Implement rate limiting for API endpoints"
    }

    # Track failed attempt
    kb = get_knowledge_base()

    # First attempt - wrong approach
    kb.store_pattern(
        feature=feature,
        implementation={
            "approach": "Tried in-memory rate limiting with simple counter",
            "files_changed": ["src/middleware/rateLimit.ts"],
            "model_used": "claude-sonnet-4-5"
        },
        success=False,
        attempts=1,
        lessons_learned="In-memory rate limiting doesn't work with multiple server instances - need Redis"
    )

    print("\n[KnowledgeBase] Recorded failed attempt with lesson learned")

    # Second attempt - correct approach
    kb.store_pattern(
        feature=feature,
        implementation={
            "approach": "Used Redis-backed rate limiting with Upstash",
            "files_changed": [
                "src/middleware/rateLimit.ts",
                "src/lib/redis.ts",
                "src/app/api/edges/rate.ts"
            ],
            "model_used": "claude-opus-4-5"
        },
        success=True,
        attempts=2,
        lessons_learned="Upstash Redis edge rate limiting is perfect for serverless - works at edge"
    )

    print("[KnowledgeBase] Recorded successful approach")

    # Query best approach for next time
    similar = kb.get_similar_features(feature, limit=1)
    if similar:
        print(f"\nNext time, use this approach:")
        print(f"  {similar[0]['approach']}")
        print(f"  Lesson: {similar[0]['lessons_learned']}")


def example_model_selection():
    """Example: Learning which model works best."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Model Selection")
    print("=" * 70)

    kb = get_knowledge_base()

    # Check which model works best for different categories
    categories = ["authentication", "ui", "api", "database"]

    print("\nModel recommendations by category:")
    for category in categories:
        best_model = kb.get_best_model(category)
        stats = kb.get_success_rate(category)

        print(f"\n  {category}:")
        print(f"    Recommended: {best_model}")
        print(f"    Success rate: {stats['success_rate']:.1f}%")
        print(f"    Total patterns: {stats['total_patterns']}")


def example_getting_insights():
    """Example: Getting insights from the knowledge base."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Knowledge Base Insights")
    print("=" * 70)

    kb = get_knowledge_base()

    # Overall summary
    summary = kb.get_summary()

    print("\nKNOWLEDGE BASE SUMMARY:")
    print(f"  Total patterns: {summary['total_patterns']}")
    print(f"  Success rate: {summary['overall_success_rate']}%")
    print(f"  Categories: {', '.join(summary['by_category'].keys())}")

    print("\nTOP MODELS:")
    for model, count in summary['top_models'].items():
        print(f"  {model}: {count} patterns")

    # Common successful approaches for a category
    print("\nCOMMON APPROACHES FOR 'authentication':")
    approaches = kb.get_common_approaches("authentication", limit=3)

    for i, approach in enumerate(approaches, 1):
        print(f"\n  {i}. {approach['approach'][:80]}...")
        print(f"     Success rate: {approach['success_rate']:.0f}%")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("KNOWLEDGE BASE INTEGRATION EXAMPLES")
    print("=" * 70)

    example_prompt_enhancement()
    example_implementation_tracking()
    example_learning_from_failures()
    example_model_selection()
    example_getting_insights()

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  1. Enhance prompts with past examples using enhance_prompt_with_knowledge()")
    print("  2. Track implementations with ImplementationTracker class")
    print("  3. Store both successes and failures with lessons learned")
    print("  4. Query best model per category with get_best_model()")
    print("  5. Get insights with get_summary() and get_common_approaches()")
    print()


if __name__ == "__main__":
    main()
