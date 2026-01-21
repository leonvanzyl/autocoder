"""
Review Agent API Router
=======================

REST API endpoints for automatic code review.

Endpoints:
- POST /api/review/run - Run code review on a project
- GET /api/review/reports/{project_name} - List review reports
- GET /api/review/reports/{project_name}/{filename} - Get specific report
- POST /api/review/create-features - Create features from review issues
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from registry import get_project_path
from review_agent import ReviewAgent, run_review

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["review"])


# ============================================================================
# Request/Response Models
# ============================================================================


class RunReviewRequest(BaseModel):
    """Request to run a code review."""

    project_name: str = Field(..., description="Project name or path")
    commits: Optional[list[str]] = Field(None, description="Specific commits to review")
    files: Optional[list[str]] = Field(None, description="Specific files to review")
    save_report: bool = Field(True, description="Whether to save the report")
    checks: Optional[dict] = Field(
        None,
        description="Which checks to run (dead_code, naming, error_handling, security, complexity)",
    )


class ReviewIssueResponse(BaseModel):
    """A review issue."""

    category: str
    severity: str
    title: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None


class ReviewSummary(BaseModel):
    """Summary of review results."""

    total_issues: int
    by_severity: dict
    by_category: dict


class RunReviewResponse(BaseModel):
    """Response from running a review."""

    project_dir: str
    review_time: str
    commits_reviewed: list[str]
    files_reviewed: list[str]
    issues: list[ReviewIssueResponse]
    summary: ReviewSummary
    report_path: Optional[str] = None


class ReportListItem(BaseModel):
    """A review report in the list."""

    filename: str
    review_time: str
    total_issues: int
    errors: int
    warnings: int


class ReportListResponse(BaseModel):
    """List of review reports."""

    reports: list[ReportListItem]
    count: int


class CreateFeaturesRequest(BaseModel):
    """Request to create features from review issues."""

    project_name: str = Field(..., description="Project name")
    issues: list[dict] = Field(..., description="Issues to convert to features")


class CreateFeaturesResponse(BaseModel):
    """Response from creating features."""

    created: int
    features: list[dict]


# ============================================================================
# Helper Functions
# ============================================================================


def get_project_dir(project_name: str) -> Path:
    """Get project directory from name or path."""
    # Try to get from registry
    project_path = get_project_path(project_name)
    if project_path:
        return Path(project_path)

    # Check if it's a direct path
    path = Path(project_name)
    if path.exists() and path.is_dir():
        return path

    raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/run", response_model=RunReviewResponse)
async def run_code_review(request: RunReviewRequest):
    """
    Run code review on a project.

    Analyzes code for common issues:
    - Dead code (unused imports, variables)
    - Naming convention violations
    - Missing error handling
    - Security vulnerabilities
    - Code complexity
    """
    project_dir = get_project_dir(request.project_name)

    # Configure checks
    check_config = request.checks or {}

    try:
        agent = ReviewAgent(
            project_dir=project_dir,
            check_dead_code=check_config.get("dead_code", True),
            check_naming=check_config.get("naming", True),
            check_error_handling=check_config.get("error_handling", True),
            check_security=check_config.get("security", True),
            check_complexity=check_config.get("complexity", True),
        )

        report = agent.review(
            commits=request.commits,
            files=request.files,
        )

        report_path = None
        if request.save_report:
            saved_path = agent.save_report(report)
            report_path = str(saved_path.relative_to(project_dir))

        report_dict = report.to_dict()

        return RunReviewResponse(
            project_dir=report_dict["project_dir"],
            review_time=report_dict["review_time"],
            commits_reviewed=report_dict["commits_reviewed"],
            files_reviewed=report_dict["files_reviewed"],
            issues=[ReviewIssueResponse(**i) for i in report_dict["issues"]],
            summary=ReviewSummary(**report_dict["summary"]),
            report_path=report_path,
        )

    except Exception as e:
        logger.error(f"Review failed for {project_dir}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{project_name}", response_model=ReportListResponse)
async def list_reports(project_name: str):
    """
    List all review reports for a project.
    """
    project_dir = get_project_dir(project_name)
    reports_dir = project_dir / ".autocoder" / "review-reports"

    if not reports_dir.exists():
        return ReportListResponse(reports=[], count=0)

    reports = []
    for report_file in sorted(reports_dir.glob("review_*.json"), reverse=True):
        try:
            with open(report_file) as f:
                data = json.load(f)

            summary = data.get("summary", {})
            by_severity = summary.get("by_severity", {})

            reports.append(
                ReportListItem(
                    filename=report_file.name,
                    review_time=data.get("review_time", ""),
                    total_issues=summary.get("total_issues", 0),
                    errors=by_severity.get("error", 0),
                    warnings=by_severity.get("warning", 0),
                )
            )
        except Exception as e:
            logger.warning(f"Error reading report {report_file}: {e}")
            continue

    return ReportListResponse(reports=reports, count=len(reports))


@router.get("/reports/{project_name}/{filename}")
async def get_report(project_name: str, filename: str):
    """
    Get a specific review report.
    """
    project_dir = get_project_dir(project_name)
    report_path = project_dir / ".autocoder" / "review-reports" / filename

    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    # Validate filename to prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        with open(report_path) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading report: {e}")


@router.post("/create-features", response_model=CreateFeaturesResponse)
async def create_features_from_issues(request: CreateFeaturesRequest):
    """
    Create features from review issues.

    Converts review issues into trackable features that can be assigned
    to coding agents for resolution.
    """
    from api.database import Feature, get_session

    project_dir = get_project_dir(request.project_name)
    db_path = project_dir / "features.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Project database not found")

    created_features = []

    try:
        session = get_session(db_path)

        # Get max priority for ordering
        max_priority = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
        current_priority = (max_priority[0] if max_priority else 0) + 1

        for issue in request.issues:
            # Create feature from issue
            feature = Feature(
                priority=current_priority,
                category=issue.get("category", "Code Review"),
                name=issue.get("name", issue.get("title", "Review Issue")),
                description=issue.get("description", ""),
                steps=json.dumps(issue.get("steps", ["Fix the identified issue"])),
                passes=False,
                in_progress=False,
            )

            session.add(feature)
            current_priority += 1

            created_features.append(
                {
                    "priority": feature.priority,
                    "category": feature.category,
                    "name": feature.name,
                    "description": feature.description,
                }
            )

        session.commit()
        session.close()

        return CreateFeaturesResponse(
            created=len(created_features),
            features=created_features,
        )

    except Exception as e:
        logger.error(f"Failed to create features: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reports/{project_name}/{filename}")
async def delete_report(project_name: str, filename: str):
    """
    Delete a specific review report.
    """
    project_dir = get_project_dir(project_name)
    report_path = project_dir / ".autocoder" / "review-reports" / filename

    # Validate filename to prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    try:
        report_path.unlink()
        return {"deleted": True, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting report: {e}")
