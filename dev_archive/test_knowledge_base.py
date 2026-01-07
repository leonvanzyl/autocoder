"""
Test script for Knowledge Base functionality.

Demonstrates:
1. Storing patterns from completed features
2. Finding similar features
3. Generating reference prompts
4. Learning best models per category
"""

from pathlib import Path
from knowledge_base import get_knowledge_base


def test_knowledge_base():
    """Test knowledge base functionality."""
    kb = get_knowledge_base()

    print("=" * 70)
    print("KNOWLEDGE BASE TEST")
    print("=" * 70)

    # 1. Store some sample patterns
    print("\n1. Storing sample patterns...")

    # Pattern 1: Authentication feature
    feature1 = {
        "category": "authentication",
        "name": "login form",
        "description": "Create a login form with email and password validation"
    }

    implementation1 = {
        "approach": "Created React component with Formik for form handling, JWT tokens for auth",
        "files_changed": ["src/components/LoginForm.tsx", "src/api/auth.ts", "src/types/user.ts"],
        "model_used": "claude-opus-4-5"
    }

    kb.store_pattern(
        feature=feature1,
        implementation=implementation1,
        success=True,
        attempts=1,
        lessons_learned="Use Formik for complex forms - reduces validation code significantly"
    )

    # Pattern 2: Another auth feature (failed attempt)
    feature2 = {
        "category": "authentication",
        "name": "password reset",
        "description": "Implement password reset flow with email verification"
    }

    implementation2 = {
        "approach": "Tried custom email service - had reliability issues",
        "files_changed": ["src/api/auth.ts", "src/components/PasswordReset.tsx"],
        "model_used": "claude-sonnet-4-5"
    }

    kb.store_pattern(
        feature=feature2,
        implementation=implementation2,
        success=False,
        attempts=3,
        lessons_learned="Custom email services are unreliable - use Resend or SendGrid instead"
    )

    # Pattern 3: UI component feature
    feature3 = {
        "category": "ui",
        "name": "modal dialog",
        "description": "Create a reusable modal dialog component with animations"
    }

    implementation3 = {
        "approach": "Used Radix UI Dialog primitive with Tailwind animations",
        "files_changed": ["src/components/Modal.tsx", "src/components/Modal.stories.tsx"],
        "model_used": "claude-opus-4-5"
    }

    kb.store_pattern(
        feature=feature3,
        implementation=implementation3,
        success=True,
        attempts=1,
        lessons_learned="Radix UI primitives are better than building from scratch for accessibility"
    )

    # 2. Find similar features
    print("\n2. Finding similar features...")

    new_feature = {
        "category": "authentication",
        "name": "user registration",
        "description": "Create registration form with email verification"
    }

    similar = kb.get_similar_features(new_feature, limit=3)

    print(f"\nSimilar features to '{new_feature['name']}':")
    for i, pattern in enumerate(similar, 1):
        print(f"\n  {i}. {pattern['feature_name']} ({pattern['category']})")
        print(f"     Success: {pattern['success']}")
        print(f"     Approach: {pattern['approach'][:80]}...")
        if pattern['lessons_learned']:
            print(f"     Lesson: {pattern['lessons_learned']}")

    # 3. Generate reference prompt
    print("\n3. Generating reference prompt...")
    reference = kb.get_reference_prompt(new_feature)
    print(reference)

    # 4. Get best model
    print("\n4. Getting best model for category...")
    best_model = kb.get_best_model("authentication")
    print(f"Best model for 'authentication': {best_model}")

    # 5. Get success rate
    print("\n5. Getting success rate statistics...")
    stats = kb.get_success_rate("authentication")
    print(f"Authentication category stats:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")
    print(f"  Avg attempts: {stats['avg_attempts']}")

    # 6. Get common approaches
    print("\n6. Getting common successful approaches...")
    approaches = kb.get_common_approaches("authentication", limit=5)
    print(f"Common approaches for 'authentication':")
    for approach in approaches:
        print(f"  - {approach['approach'][:60]}...")
        print(f"    Success rate: {approach['success_rate']:.1f}% ({approach['successes']}/{approach['total']})")

    # 7. Get overall summary
    print("\n7. Getting knowledge base summary...")
    summary = kb.get_summary()
    print(f"Total patterns: {summary['total_patterns']}")
    print(f"Overall success rate: {summary['overall_success_rate']}%")
    print(f"Categories: {list(summary['by_category'].keys())}")
    print(f"Top models: {summary['top_models']}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_knowledge_base()
