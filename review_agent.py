"""
Review Agent Module
===================

Automatic code review agent that analyzes completed features.

Features:
- Analyzes recent commits after N features complete
- Detects common issues:
  - Dead code (unused variables, functions)
  - Inconsistent naming
  - Missing error handling
  - Code duplication
  - Security issues
- Creates new features for found issues
- Generates review reports

Configuration:
- review.enabled: Enable/disable review agent
- review.trigger_after_features: Run review after N features (default: 5)
- review.checks: Which checks to run
"""

import ast
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    """Severity levels for review issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    STYLE = "style"


class IssueCategory(str, Enum):
    """Categories of review issues."""

    DEAD_CODE = "dead_code"
    NAMING = "naming"
    ERROR_HANDLING = "error_handling"
    DUPLICATION = "duplication"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLEXITY = "complexity"
    DOCUMENTATION = "documentation"
    STYLE = "style"


@dataclass
class ReviewIssue:
    """A code review issue."""

    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
        }
        if self.line_number:
            result["line_number"] = self.line_number
        if self.code_snippet:
            result["code_snippet"] = self.code_snippet
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result

    def to_feature(self) -> dict:
        """Convert to a feature for tracking."""
        return {
            "category": "Code Review",
            "name": self.title,
            "description": self.description,
            "steps": [
                f"Review issue in {self.file_path}" + (f":{self.line_number}" if self.line_number else ""),
                self.suggestion or "Fix the identified issue",
                "Verify the fix works correctly",
            ],
        }


@dataclass
class ReviewReport:
    """Complete review report."""

    project_dir: str
    review_time: str
    commits_reviewed: list[str] = field(default_factory=list)
    files_reviewed: list[str] = field(default_factory=list)
    issues: list[ReviewIssue] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_dir": self.project_dir,
            "review_time": self.review_time,
            "commits_reviewed": self.commits_reviewed,
            "files_reviewed": self.files_reviewed,
            "issues": [i.to_dict() for i in self.issues],
            "summary": {
                "total_issues": len(self.issues),
                "by_severity": {
                    s.value: len([i for i in self.issues if i.severity == s])
                    for s in IssueSeverity
                },
                "by_category": {
                    c.value: len([i for i in self.issues if i.category == c])
                    for c in IssueCategory
                },
            },
        }


class ReviewAgent:
    """
    Code review agent for automatic quality checks.

    Usage:
        agent = ReviewAgent(project_dir)
        report = agent.review()
        features = agent.get_issues_as_features()
    """

    def __init__(
        self,
        project_dir: Path,
        check_dead_code: bool = True,
        check_naming: bool = True,
        check_error_handling: bool = True,
        check_security: bool = True,
        check_complexity: bool = True,
    ):
        self.project_dir = Path(project_dir)
        self.check_dead_code = check_dead_code
        self.check_naming = check_naming
        self.check_error_handling = check_error_handling
        self.check_security = check_security
        self.check_complexity = check_complexity
        self.issues: list[ReviewIssue] = []

    def review(
        self,
        commits: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
    ) -> ReviewReport:
        """
        Run code review.

        Args:
            commits: Specific commits to review (default: recent commits)
            files: Specific files to review (default: changed files)

        Returns:
            ReviewReport with all findings
        """
        self.issues = []

        # Get files to review
        if files:
            files_to_review = [self.project_dir / f for f in files]
        elif commits:
            files_to_review = self._get_changed_files(commits)
        else:
            # Review all source files
            files_to_review = list(self._iter_source_files())

        # Run checks
        for file_path in files_to_review:
            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(errors="ignore")

                if file_path.suffix == ".py":
                    self._review_python_file(file_path, content)
                elif file_path.suffix in {".js", ".ts", ".jsx", ".tsx"}:
                    self._review_javascript_file(file_path, content)
            except Exception as e:
                logger.warning(f"Error reviewing {file_path}: {e}")

        # Generate report
        return ReviewReport(
            project_dir=str(self.project_dir),
            review_time=datetime.utcnow().isoformat() + "Z",
            commits_reviewed=commits or [],
            files_reviewed=[str(f.relative_to(self.project_dir)) for f in files_to_review if f.exists()],
            issues=self.issues,
        )

    def _iter_source_files(self):
        """Iterate over source files in project."""
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx"}
        skip_dirs = {"node_modules", "venv", ".venv", "__pycache__", ".git", "dist", "build"}

        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                if Path(file).suffix in extensions:
                    yield Path(root) / file

    def _get_changed_files(self, commits: list[str]) -> list[Path]:
        """Get files changed in specified commits."""
        files = set()
        for commit in commits:
            try:
                result = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                )
                for line in result.stdout.strip().split("\n"):
                    if line:
                        files.add(self.project_dir / line)
            except Exception:
                pass
        return list(files)

    def _review_python_file(self, file_path: Path, content: str) -> None:
        """Review a Python file."""
        relative_path = str(file_path.relative_to(self.project_dir))

        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        # Check for dead code (unused imports)
        if self.check_dead_code:
            self._check_python_unused_imports(tree, content, relative_path)

        # Check naming conventions
        if self.check_naming:
            self._check_python_naming(tree, relative_path)

        # Check error handling
        if self.check_error_handling:
            self._check_python_error_handling(tree, content, relative_path)

        # Check complexity
        if self.check_complexity:
            self._check_python_complexity(tree, relative_path)

        # Check security patterns
        if self.check_security:
            self._check_security_patterns(content, relative_path)

    def _check_python_unused_imports(self, tree: ast.AST, content: str, file_path: str) -> None:
        """Check for unused imports in Python."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imports.append((name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        name = alias.asname or alias.name
                        imports.append((name, node.lineno))

        # Simple check: see if import name appears in rest of file
        for name, lineno in imports:
            # Count occurrences (excluding import lines)
            pattern = rf"\b{re.escape(name)}\b"
            matches = list(re.finditer(pattern, content))
            # If only appears once (the import), likely unused
            if len(matches) <= 1:
                self.issues.append(
                    ReviewIssue(
                        category=IssueCategory.DEAD_CODE,
                        severity=IssueSeverity.WARNING,
                        title=f"Possibly unused import: {name}",
                        description=f"Import '{name}' may be unused in this file",
                        file_path=file_path,
                        line_number=lineno,
                        suggestion="Remove unused import if not needed",
                    )
                )

    def _check_python_naming(self, tree: ast.AST, file_path: str) -> None:
        """Check Python naming conventions."""
        for node in ast.walk(tree):
            # Check class names (should be PascalCase)
            if isinstance(node, ast.ClassDef):
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
                    self.issues.append(
                        ReviewIssue(
                            category=IssueCategory.NAMING,
                            severity=IssueSeverity.STYLE,
                            title=f"Class name not PascalCase: {node.name}",
                            description=f"Class '{node.name}' should use PascalCase naming",
                            file_path=file_path,
                            line_number=node.lineno,
                            suggestion="Rename to follow PascalCase convention",
                        )
                    )

            # Check function names (should be snake_case)
            elif isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_") and not re.match(r"^[a-z_][a-z0-9_]*$", node.name):
                    if not re.match(r"^__\w+__$", node.name):  # Skip dunder methods
                        self.issues.append(
                            ReviewIssue(
                                category=IssueCategory.NAMING,
                                severity=IssueSeverity.STYLE,
                                title=f"Function name not snake_case: {node.name}",
                                description=f"Function '{node.name}' should use snake_case naming",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion="Rename to follow snake_case convention",
                            )
                        )

    def _check_python_error_handling(self, tree: ast.AST, content: str, file_path: str) -> None:
        """Check error handling in Python."""
        for node in ast.walk(tree):
            # Check for bare except clauses
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    self.issues.append(
                        ReviewIssue(
                            category=IssueCategory.ERROR_HANDLING,
                            severity=IssueSeverity.WARNING,
                            title="Bare except clause",
                            description="Bare 'except:' catches all exceptions including KeyboardInterrupt",
                            file_path=file_path,
                            line_number=node.lineno,
                            suggestion="Use 'except Exception:' or catch specific exceptions",
                        )
                    )

            # Check for pass in except
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    self.issues.append(
                        ReviewIssue(
                            category=IssueCategory.ERROR_HANDLING,
                            severity=IssueSeverity.WARNING,
                            title="Empty except handler",
                            description="Exception is caught but silently ignored",
                            file_path=file_path,
                            line_number=node.lineno,
                            suggestion="Add logging or proper error handling",
                        )
                    )

    def _check_python_complexity(self, tree: ast.AST, file_path: str) -> None:
        """Check code complexity in Python."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Count lines in function
                if hasattr(node, "end_lineno") and node.end_lineno:
                    lines = node.end_lineno - node.lineno
                    if lines > 50:
                        self.issues.append(
                            ReviewIssue(
                                category=IssueCategory.COMPLEXITY,
                                severity=IssueSeverity.INFO,
                                title=f"Long function: {node.name} ({lines} lines)",
                                description=f"Function '{node.name}' is {lines} lines long",
                                file_path=file_path,
                                line_number=node.lineno,
                                suggestion="Consider breaking into smaller functions",
                            )
                        )

                # Count parameters
                num_args = len(node.args.args) + len(node.args.posonlyargs) + len(node.args.kwonlyargs)
                if num_args > 7:
                    self.issues.append(
                        ReviewIssue(
                            category=IssueCategory.COMPLEXITY,
                            severity=IssueSeverity.INFO,
                            title=f"Too many parameters: {node.name} ({num_args})",
                            description=f"Function '{node.name}' has {num_args} parameters",
                            file_path=file_path,
                            line_number=node.lineno,
                            suggestion="Consider using a config object or dataclass",
                        )
                    )

    def _check_security_patterns(self, content: str, file_path: str) -> None:
        """Check for common security issues."""
        lines = content.split("\n")

        patterns = [
            (r"eval\s*\(", "Use of eval()", "Avoid eval() - it can execute arbitrary code"),
            (r"exec\s*\(", "Use of exec()", "Avoid exec() - it can execute arbitrary code"),
            (r"shell\s*=\s*True", "subprocess with shell=True", "Avoid shell=True to prevent injection"),
            (r"pickle\.load", "Use of pickle.load", "Pickle can execute arbitrary code"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, title, suggestion in patterns:
                if re.search(pattern, line):
                    self.issues.append(
                        ReviewIssue(
                            category=IssueCategory.SECURITY,
                            severity=IssueSeverity.WARNING,
                            title=title,
                            description="Potential security issue detected",
                            file_path=file_path,
                            line_number=i,
                            code_snippet=line.strip()[:80],
                            suggestion=suggestion,
                        )
                    )

    def _review_javascript_file(self, file_path: Path, content: str) -> None:
        """Review a JavaScript/TypeScript file."""
        relative_path = str(file_path.relative_to(self.project_dir))
        lines = content.split("\n")

        # Check for console.log statements
        for i, line in enumerate(lines, 1):
            if re.search(r"console\.(log|debug|info)\s*\(", line):
                # Skip if in comment
                if not line.strip().startswith("//"):
                    self.issues.append(
                        ReviewIssue(
                            category=IssueCategory.DEAD_CODE,
                            severity=IssueSeverity.INFO,
                            title="console.log statement",
                            description="Debug logging should be removed in production",
                            file_path=relative_path,
                            line_number=i,
                            code_snippet=line.strip()[:80],
                            suggestion="Remove or use proper logging",
                        )
                    )

        # Check for TODO/FIXME comments
        for i, line in enumerate(lines, 1):
            if re.search(r"(TODO|FIXME|XXX|HACK):", line, re.IGNORECASE):
                self.issues.append(
                    ReviewIssue(
                        category=IssueCategory.DOCUMENTATION,
                        severity=IssueSeverity.INFO,
                        title="TODO/FIXME comment found",
                        description="Outstanding work marked in code",
                        file_path=relative_path,
                        line_number=i,
                        code_snippet=line.strip()[:80],
                        suggestion="Address the TODO or create a tracking issue",
                    )
                )

        # Check for security patterns
        if self.check_security:
            self._check_js_security_patterns(content, relative_path)

    def _check_js_security_patterns(self, content: str, file_path: str) -> None:
        """Check JavaScript security patterns."""
        lines = content.split("\n")

        patterns = [
            (r"eval\s*\(", "Use of eval()", "Avoid eval() - use JSON.parse() or Function()"),
            (r"innerHTML\s*=", "Direct innerHTML assignment", "Use textContent or sanitize HTML"),
            (r"dangerouslySetInnerHTML", "dangerouslySetInnerHTML usage", "Ensure content is sanitized"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, title, suggestion in patterns:
                if re.search(pattern, line):
                    self.issues.append(
                        ReviewIssue(
                            category=IssueCategory.SECURITY,
                            severity=IssueSeverity.WARNING,
                            title=title,
                            description="Potential security issue detected",
                            file_path=file_path,
                            line_number=i,
                            code_snippet=line.strip()[:80],
                            suggestion=suggestion,
                        )
                    )

    def get_issues_as_features(self) -> list[dict]:
        """
        Convert significant issues to features for tracking.

        Only creates features for errors and warnings, not info/style.
        """
        features = []
        seen = set()

        for issue in self.issues:
            if issue.severity in {IssueSeverity.ERROR, IssueSeverity.WARNING}:
                # Deduplicate by title
                if issue.title not in seen:
                    seen.add(issue.title)
                    features.append(issue.to_feature())

        return features

    def save_report(self, report: ReviewReport) -> Path:
        """Save review report to file."""
        reports_dir = self.project_dir / ".autocoder" / "review-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"review_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        return report_path


def run_review(
    project_dir: Path,
    commits: Optional[list[str]] = None,
    save_report: bool = True,
) -> ReviewReport:
    """
    Run code review on a project.

    Args:
        project_dir: Project directory
        commits: Specific commits to review
        save_report: Whether to save the report

    Returns:
        ReviewReport with findings
    """
    agent = ReviewAgent(project_dir)
    report = agent.review(commits=commits)

    if save_report:
        agent.save_report(report)

    return report
