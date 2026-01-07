"""
Knowledge Base Inspection Tool
==============================

Command-line utility to inspect and manage the knowledge base.
"""

import argparse
import json
from pathlib import Path
from knowledge_base import get_knowledge_base


def inspect_summary(args):
    """Show knowledge base summary."""
    kb = get_knowledge_base()
    summary = kb.get_summary()

    print("\n" + "=" * 70)
    print("KNOWLEDGE BASE SUMMARY")
    print("=" * 70)
    print(f"\nLocation: {kb.db_path}")
    print(f"Total patterns: {summary['total_patterns']}")
    print(f"Overall success rate: {summary['overall_success_rate']}%")

    print("\nPatterns by category:")
    for category, count in summary['by_category'].items():
        print(f"  {category}: {count}")

    print("\nTop models:")
    for model, count in summary['top_models'].items():
        print(f"  {model}: {count} patterns")


def inspect_category(args):
    """Show details for a specific category."""
    kb = get_knowledge_base()

    print("\n" + "=" * 70)
    print(f"CATEGORY: {args.category}")
    print("=" * 70)

    # Get best model
    best_model = kb.get_best_model(args.category)
    print(f"\nBest model: {best_model}")

    # Get success rate
    stats = kb.get_success_rate(args.category)
    print(f"Success rate: {stats['success_rate']:.1f}%")
    print(f"Total patterns: {stats['total_patterns']}")
    print(f"Avg attempts: {stats['avg_attempts']}")

    # Get common approaches
    approaches = kb.get_common_approaches(args.category, limit=args.limit)
    print(f"\nCommon successful approaches (top {len(approaches)}):")
    for i, approach in enumerate(approaches, 1):
        print(f"\n  {i}. {approach['approach'][:80]}...")
        print(f"     Success rate: {approach['success_rate']:.0f}% ({approach['successes']}/{approach['total']})")


def inspect_similar(args):
    """Find similar features to a query."""
    kb = get_knowledge_base()

    feature = {
        "category": args.category or "",
        "name": args.name or "",
        "description": args.description or ""
    }

    similar = kb.get_similar_features(feature, limit=args.limit)

    print("\n" + "=" * 70)
    print(f"SIMILAR FEATURES TO: {args.name or args.description}")
    print("=" * 70)

    if not similar:
        print("\nNo similar features found.")
        return

    for i, pattern in enumerate(similar, 1):
        print(f"\n{i}. {pattern['feature_name']} ({pattern['category']})")
        print(f"   Success: {'Yes' if pattern['success'] else 'No'}")
        print(f"   Approach: {pattern['approach'][:80]}...")

        if pattern['files_changed']:
            files = json.loads(pattern['files_changed'])
            print(f"   Files: {len(files)} changed")

        if pattern['lessons_learned']:
            print(f"   Lesson: {pattern['lessons_learned'][:80]}...")

        if pattern['attempts'] > 1:
            print(f"   Attempts: {pattern['attempts']}")


def inspect_recent(args):
    """Show recent patterns."""
    import sqlite3

    kb = get_knowledge_base()
    conn = sqlite3.connect(kb.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, feature_name, success, created_at
        FROM patterns
        ORDER BY created_at DESC
        LIMIT ?
    """, (args.limit,))

    results = cursor.fetchall()
    conn.close()

    print("\n" + "=" * 70)
    print(f"RECENT PATTERNS (last {len(results)})")
    print("=" * 70)

    for row in results:
        category, name, success, created_at = row
        status = "OK" if success else "FAIL"
        print(f"\n[{status}] {name} ({category})")
        print(f"      {created_at}")


def inspect_export(args):
    """Export knowledge base to JSON."""
    import sqlite3

    kb = get_knowledge_base()
    conn = sqlite3.connect(kb.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, category, feature_name, description, approach,
               files_changed, model_used, success, created_at,
               attempts, lessons_learned
        FROM patterns
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    patterns = []
    for row in rows:
        pattern = {
            "id": row[0],
            "category": row[1],
            "feature_name": row[2],
            "description": row[3],
            "approach": row[4],
            "files_changed": json.loads(row[5]),
            "model_used": row[6],
            "success": bool(row[7]),
            "created_at": row[8],
            "attempts": row[9],
            "lessons_learned": row[10]
        }
        patterns.append(pattern)

    output = {
        "total_patterns": len(patterns),
        "patterns": patterns
    }

    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2))
        print(f"\nExported {len(patterns)} patterns to {args.output}")
    else:
        print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Inspect and manage the knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show summary
  python inspect_knowledge.py summary

  # Show category details
  python inspect_knowledge.py category authentication

  # Find similar features
  python inspect_knowledge.py similar --category authentication --name "login"

  # Show recent patterns
  python inspect_knowledge.py recent --limit 10

  # Export to JSON
  python inspect_knowledge.py export --output knowledge.json
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Summary command
    parser_summary = subparsers.add_parser("summary", help="Show knowledge base summary")
    parser_summary.set_defaults(func=inspect_summary)

    # Category command
    parser_category = subparsers.add_parser("category", help="Show category details")
    parser_category.add_argument("category", help="Category name")
    parser_category.add_argument("--limit", type=int, default=5, help="Max approaches to show")
    parser_category.set_defaults(func=inspect_category)

    # Similar command
    parser_similar = subparsers.add_parser("similar", help="Find similar features")
    parser_similar.add_argument("--category", help="Filter by category")
    parser_similar.add_argument("--name", help="Feature name")
    parser_similar.add_argument("--description", help="Feature description")
    parser_similar.add_argument("--limit", type=int, default=3, help="Max results")
    parser_similar.set_defaults(func=inspect_similar)

    # Recent command
    parser_recent = subparsers.add_parser("recent", help="Show recent patterns")
    parser_recent.add_argument("--limit", type=int, default=10, help="Max patterns to show")
    parser_recent.set_defaults(func=inspect_recent)

    # Export command
    parser_export = subparsers.add_parser("export", help="Export to JSON")
    parser_export.add_argument("--output", "-o", help="Output file path")
    parser_export.set_defaults(func=inspect_export)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
