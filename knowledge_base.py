"""
Knowledge Base for Learning from Feature Implementations
========================================================

Stores patterns from completed features to improve future implementations.
Inspired by scagent research, but simplified for feature-level learning.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class ImplementationPattern:
    """Represents a learned pattern from a completed feature."""
    category: str
    feature_name: str
    description: str
    approach: str
    files_changed: list[str]
    model_used: str
    success: bool
    created_at: str
    attempts: int = 1
    lessons_learned: str = ""


class KnowledgeBase:
    """
    Knowledge base for storing and retrieving implementation patterns.

    Learns from:
    - Which approaches work for which feature categories
    - Which files typically change for certain features
    - Which model performs best for different tasks
    - Common patterns and pitfalls

    Database location: ~/.autocoder/knowledge.db (global across projects)
    """

    def __init__(self, project_dir: Optional[Path] = None):
        """
        Initialize knowledge base.

        Args:
            project_dir: Optional project directory. If None, uses global knowledge base.
        """
        self.project_dir = project_dir

        # Use global knowledge base for cross-project learning
        kb_dir = Path.home() / ".autocoder"
        kb_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = kb_dir / "knowledge.db"

        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                description TEXT NOT NULL,
                approach TEXT NOT NULL,
                files_changed TEXT NOT NULL,
                model_used TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                created_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 1,
                lessons_learned TEXT DEFAULT '',
                project_dir TEXT
            )
        """)

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category
            ON patterns(category)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_success
            ON patterns(success)
        """)

        conn.commit()
        conn.close()

    def store_pattern(
        self,
        feature: dict,
        implementation: dict,
        success: bool,
        attempts: int = 1,
        lessons_learned: str = ""
    ) -> int:
        """
        Store an implementation pattern after feature completion.

        Args:
            feature: Feature dict with category, name, description
            implementation: Implementation dict with:
                - approach: Description of the approach used
                - files_changed: List of files that were modified
                - model_used: Model that implemented this (e.g., "claude-opus-4-5")
            success: Whether the implementation succeeded
            attempts: Number of attempts before success
            lessons_learned: Key insights from this implementation

        Returns:
            Pattern ID
        """
        pattern = ImplementationPattern(
            category=feature.get("category", "unknown"),
            feature_name=feature.get("name", "unknown"),
            description=feature.get("description", ""),
            approach=implementation.get("approach", ""),
            files_changed=implementation.get("files_changed", []),
            model_used=implementation.get("model_used", "unknown"),
            success=success,
            created_at=datetime.now().isoformat(),
            attempts=attempts,
            lessons_learned=lessons_learned
        )

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO patterns (
                category, feature_name, description, approach,
                files_changed, model_used, success, created_at,
                attempts, lessons_learned, project_dir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern.category,
            pattern.feature_name,
            pattern.description,
            pattern.approach,
            json.dumps(pattern.files_changed),
            pattern.model_used,
            pattern.success,
            pattern.created_at,
            pattern.attempts,
            pattern.lessons_learned,
            str(self.project_dir) if self.project_dir else None
        ))

        pattern_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"[KnowledgeBase] Stored pattern: {pattern.category}/{pattern.feature_name} (success={success})")
        return pattern_id

    def get_similar_features(self, feature: dict, limit: int = 3) -> list[dict]:
        """
        Find similar past features based on category and keywords.

        Args:
            feature: Feature dict with category, name, description
            limit: Maximum number of similar features to return

        Returns:
            List of similar feature patterns (most similar first)
        """
        category = feature.get("category", "")
        name = feature.get("name", "")
        description = feature.get("description", "")

        # Extract keywords from name and description
        keywords = self._extract_keywords(f"{name} {description}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Query patterns by category (if specified)
        if category:
            cursor.execute("""
                SELECT id, category, feature_name, description, approach,
                       files_changed, model_used, success, created_at,
                       attempts, lessons_learned
                FROM patterns
                WHERE category = ?
                ORDER BY created_at DESC
            """, (category,))
        else:
            # Search all patterns if no category specified
            cursor.execute("""
                SELECT id, category, feature_name, description, approach,
                       files_changed, model_used, success, created_at,
                       attempts, lessons_learned
                FROM patterns
                ORDER BY created_at DESC
            """)

        results = cursor.fetchall()
        conn.close()

        # Score by keyword similarity
        scored = []
        for row in results:
            pattern = self._row_to_dict(row)
            score = self._calculate_similarity(keywords, pattern)
            if score > 0:
                scored.append((score, pattern))

        # Sort by similarity and return top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p[1] for p in scored[:limit]]

    def get_reference_prompt(self, feature: dict) -> str:
        """
        Generate a prompt enhancement with examples from similar features.

        Args:
            feature: Feature dict with category, name, description

        Returns:
            Prompt enhancement text with examples and lessons learned
        """
        similar = self.get_similar_features(feature, limit=3)

        if not similar:
            return ""

        enhancement = "\n" + "=" * 70 + "\n"
        enhancement += "REFERENCE EXAMPLES FROM SIMILAR FEATURES\n"
        enhancement += "=" * 70 + "\n\n"

        for i, pattern in enumerate(similar, 1):
            enhancement += f"Example {i}: {pattern['feature_name']}\n"
            enhancement += f"Category: {pattern['category']}\n"
            enhancement += f"Success: {'Yes' if pattern['success'] else 'No'}\n"
            enhancement += f"Approach: {pattern['approach']}\n"

            if pattern['files_changed']:
                files = json.loads(pattern['files_changed'])
                enhancement += f"Files Changed: {', '.join(files)}\n"

            if pattern['lessons_learned']:
                enhancement += f"Key Insights: {pattern['lessons_learned']}\n"

            if pattern['attempts'] > 1:
                enhancement += f"(Took {pattern['attempts']} attempts to succeed)\n"

            enhancement += "-" * 70 + "\n\n"

        enhancement += "=" * 70 + "\n"

        return enhancement

    def get_best_model(self, category: str) -> str:
        """
        Learn which model works best for a given category.

        Args:
            category: Feature category

        Returns:
            Model name with highest success rate for this category
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT model_used,
                   COUNT(*) as total,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes
            FROM patterns
            WHERE category = ?
            GROUP BY model_used
            HAVING total > 0
            ORDER BY (successes * 1.0 / total) DESC, total DESC
            LIMIT 1
        """, (category,))

        result = cursor.fetchone()
        conn.close()

        if result:
            model, total, successes = result
            success_rate = (successes / total) * 100
            print(f"[KnowledgeBase] Best model for {category}: {model} ({success_rate:.1f}% success rate)")
            return model

        # No data for this category - return default
        return "claude-opus-4-5"

    def get_success_rate(self, category: Optional[str] = None) -> dict:
        """
        Get overall success rate statistics.

        Args:
            category: Optional category filter

        Returns:
            Dict with success rate statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    AVG(attempts) as avg_attempts
                FROM patterns
                WHERE category = ?
            """, (category,))
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 0 ELSE 1 END) as successes,
                    AVG(attempts) as avg_attempts
                FROM patterns
            """)

        result = cursor.fetchone()
        conn.close()

        total, successes, avg_attempts = result

        return {
            "total_patterns": total or 0,
            "success_count": successes or 0,
            "success_rate": (successes / total * 100) if total > 0 else 0,
            "avg_attempts": round(avg_attempts, 1) if avg_attempts else 0
        }

    def get_common_approaches(self, category: str, limit: int = 5) -> list[dict]:
        """
        Get most common successful approaches for a category.

        Args:
            category: Feature category
            limit: Maximum approaches to return

        Returns:
            List of approaches with success counts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT approach,
                   COUNT(*) as total,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes
            FROM patterns
            WHERE category = ? AND success = 1
            GROUP BY approach
            ORDER BY successes DESC, total DESC
            LIMIT ?
        """, (category, limit))

        results = cursor.fetchall()
        conn.close()

        return [
            {
                "approach": row[0],
                "total": row[1],
                "successes": row[2],
                "success_rate": (row[2] / row[1] * 100) if row[1] > 0 else 0
            }
            for row in results
        ]

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from text."""
        # Simple keyword extraction - remove common words
        common_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "will", "should", "can", "could", "add", "create", "implement",
            "user", "feature", "test", "ensure", "when", "then"
        }

        words = set(text.lower().split())
        return words - common_words

    def _calculate_similarity(self, keywords: set[str], pattern: dict) -> float:
        """Calculate similarity score between keywords and pattern."""
        # Combine feature name and description
        pattern_text = f"{pattern['feature_name']} {pattern['description']}"
        pattern_keywords = self._extract_keywords(pattern_text)

        if not keywords or not pattern_keywords:
            return 0.0

        # Jaccard similarity
        intersection = len(keywords & pattern_keywords)
        union = len(keywords | pattern_keywords)

        return intersection / union if union > 0 else 0.0

    def _row_to_dict(self, row: tuple) -> dict:
        """Convert database row to dictionary."""
        return {
            "id": row[0],
            "category": row[1],
            "feature_name": row[2],
            "description": row[3],
            "approach": row[4],
            "files_changed": row[5],
            "model_used": row[6],
            "success": bool(row[7]),
            "created_at": row[8],
            "attempts": row[9],
            "lessons_learned": row[10]
        }

    def get_summary(self) -> dict:
        """Get overall knowledge base summary."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total patterns
        cursor.execute("SELECT COUNT(*) FROM patterns")
        total = cursor.fetchone()[0]

        # By category
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM patterns
            GROUP BY category
            ORDER BY count DESC
        """)
        by_category = dict(cursor.fetchall())

        # Success rate
        cursor.execute("""
            SELECT
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
            FROM patterns
        """)
        success_rate = cursor.fetchone()[0] or 0

        # Top models
        cursor.execute("""
            SELECT model_used, COUNT(*) as count
            FROM patterns
            GROUP BY model_used
            ORDER BY count DESC
            LIMIT 5
        """)
        top_models = dict(cursor.fetchall())

        conn.close()

        return {
            "total_patterns": total,
            "by_category": by_category,
            "overall_success_rate": round(success_rate, 1),
            "top_models": top_models
        }


def get_knowledge_base(project_dir: Optional[Path] = None) -> KnowledgeBase:
    """
    Get a knowledge base instance.

    Args:
        project_dir: Optional project directory

    Returns:
        KnowledgeBase instance
    """
    return KnowledgeBase(project_dir)


class ImplementationTracker:
    """
    Helper class to track implementation details for knowledge base storage.

    Usage:
        tracker = ImplementationTracker(feature)
        # ... during implementation ...
        tracker.record_file_change("src/components/Button.tsx", "created")
        tracker.record_approach("Used Radix UI primitive with custom styling")
        # ... after completion ...
        tracker.save_to_knowledge_base(success=True, attempts=1)
    """

    def __init__(self, feature: dict, project_dir: Optional[Path] = None):
        """
        Initialize tracker for a feature.

        Args:
            feature: Feature dict with category, name, description
            project_dir: Optional project directory
        """
        self.feature = feature
        self.project_dir = project_dir
        self.files_changed = []
        self.approach = ""
        self.model_used = "unknown"  # Will be set by agent
        self.start_time = datetime.now()
        self.notes = []

    def record_file_change(self, file_path: str, action: str = "modified") -> None:
        """
        Record a file change during implementation.

        Args:
            file_path: Path to the file
            action: Action taken (created, modified, deleted)
        """
        self.files_changed.append(file_path)

    def record_approach(self, approach: str) -> None:
        """
        Record the implementation approach used.

        Args:
            approach: Description of the approach
        """
        self.approach = approach

    def set_model(self, model_used: str) -> None:
        """
        Set which model performed the implementation.

        Args:
            model_used: Model name (e.g., "claude-opus-4-5")
        """
        self.model_used = model_used

    def add_note(self, note: str) -> None:
        """
        Add a note during implementation for learning.

        Args:
            note: Observation or note
        """
        self.notes.append(note)

    def save_to_knowledge_base(
        self,
        success: bool,
        attempts: int = 1,
        lessons_learned: str = ""
    ) -> int:
        """
        Save the tracked implementation to the knowledge base.

        Args:
            success: Whether the implementation succeeded
            attempts: Number of attempts before success
            lessons_learned: Key insights from this implementation

        Returns:
            Pattern ID
        """
        # Combine notes into lessons learned if not provided
        if not lessons_learned and self.notes:
            lessons_learned = "; ".join(self.notes)

        implementation = {
            "approach": self.approach or "No approach recorded",
            "files_changed": self.files_changed,
            "model_used": self.model_used
        }

        kb = get_knowledge_base(self.project_dir)
        return kb.store_pattern(
            feature=self.feature,
            implementation=implementation,
            success=success,
            attempts=attempts,
            lessons_learned=lessons_learned
        )

    def get_summary(self) -> dict:
        """
        Get a summary of the tracked implementation.

        Returns:
            Dict with implementation summary
        """
        duration = datetime.now() - self.start_time

        return {
            "feature": self.feature.get("name", "unknown"),
            "category": self.feature.get("category", "unknown"),
            "files_changed": len(self.files_changed),
            "files": self.files_changed,
            "approach": self.approach,
            "model_used": self.model_used,
            "duration_seconds": duration.total_seconds(),
            "notes": self.notes
        }
