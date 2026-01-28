"""
Visual Regression API Router
============================

REST API endpoints for visual regression testing.

Endpoints:
- POST /api/visual/test - Run visual tests
- GET /api/visual/baselines/{project_name} - List baselines
- GET /api/visual/reports/{project_name} - List test reports
- GET /api/visual/reports/{project_name}/{filename} - Get specific report
- POST /api/visual/update-baseline - Accept current as baseline
- DELETE /api/visual/baselines/{project_name}/{name}/{viewport} - Delete baseline
- GET /api/visual/snapshot/{project_name}/{type}/{filename} - Get snapshot image
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from registry import get_project_path
from visual_regression import (
    Viewport,
    VisualRegressionTester,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visual", tags=["visual-regression"])


# ============================================================================
# Request/Response Models
# ============================================================================


class RouteConfig(BaseModel):
    """Route configuration for testing."""

    path: str = Field(..., description="Route path (e.g., /dashboard)")
    name: Optional[str] = Field(None, description="Test name (auto-generated from path if not provided)")
    wait_for: Optional[str] = Field(None, description="CSS selector to wait for before capture")


class ViewportConfig(BaseModel):
    """Viewport configuration."""

    name: str
    width: int
    height: int


class RunTestsRequest(BaseModel):
    """Request to run visual tests."""

    project_name: str = Field(..., description="Project name")
    base_url: str = Field(..., description="Base URL (e.g., http://localhost:3000)")
    routes: Optional[list[RouteConfig]] = Field(None, description="Routes to test")
    threshold: float = Field(0.1, description="Diff threshold percentage")
    update_baseline: bool = Field(False, description="Update baselines instead of comparing")
    viewports: Optional[list[ViewportConfig]] = Field(None, description="Viewports to test")


class SnapshotResultResponse(BaseModel):
    """Single snapshot result."""

    name: str
    viewport: str
    baseline_path: Optional[str] = None
    current_path: Optional[str] = None
    diff_path: Optional[str] = None
    diff_percentage: float = 0.0
    passed: bool = True
    is_new: bool = False
    error: Optional[str] = None


class TestSummary(BaseModel):
    """Test summary statistics."""

    total: int
    passed: int
    failed: int
    new: int


class TestReportResponse(BaseModel):
    """Test report response."""

    project_dir: str
    test_time: str
    results: list[SnapshotResultResponse]
    summary: TestSummary


class BaselineItem(BaseModel):
    """Baseline snapshot item."""

    name: str
    viewport: str
    filename: str
    size: int
    modified: str


class BaselineListResponse(BaseModel):
    """List of baseline snapshots."""

    baselines: list[BaselineItem]
    count: int


class ReportListItem(BaseModel):
    """Report list item."""

    filename: str
    test_time: str
    total: int
    passed: int
    failed: int


class ReportListResponse(BaseModel):
    """List of test reports."""

    reports: list[ReportListItem]
    count: int


class UpdateBaselineRequest(BaseModel):
    """Request to update a baseline."""

    project_name: str
    name: str
    viewport: str


# ============================================================================
# Helper Functions
# ============================================================================


def get_project_dir(project_name: str) -> Path:
    """Get project directory from name or path."""
    project_path = get_project_path(project_name)
    if project_path:
        return Path(project_path)

    path = Path(project_name)
    if path.exists() and path.is_dir():
        return path

    raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/test", response_model=TestReportResponse)
async def run_tests(request: RunTestsRequest):
    """
    Run visual regression tests.

    Captures screenshots of specified routes and compares with baselines.
    """
    project_dir = get_project_dir(request.project_name)

    try:
        # Convert routes
        routes = None
        if request.routes:
            routes = [
                {
                    "path": r.path,
                    "name": r.name,
                    "wait_for": r.wait_for,
                }
                for r in request.routes
            ]

        # Configure viewports
        viewports = None
        if request.viewports:
            viewports = [
                Viewport(name=v.name, width=v.width, height=v.height)
                for v in request.viewports
            ]

        # Create tester with custom viewports
        tester = VisualRegressionTester(
            project_dir=project_dir,
            threshold=request.threshold,
            viewports=viewports or [Viewport.desktop()],
        )

        # Run tests
        if routes:
            report = await tester.test_routes(
                request.base_url, routes, request.update_baseline
            )
        else:
            # Default to home page
            report = await tester.test_page(
                request.base_url, "home", update_baseline=request.update_baseline
            )

        # Save report
        tester.save_report(report)

        # Convert to response
        return TestReportResponse(
            project_dir=report.project_dir,
            test_time=report.test_time,
            results=[
                SnapshotResultResponse(**r.to_dict()) for r in report.results
            ],
            summary=TestSummary(
                total=report.total,
                passed=report.passed,
                failed=report.failed,
                new=report.new,
            ),
        )

    except Exception as e:
        logger.error(f"Visual test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/baselines/{project_name}", response_model=BaselineListResponse)
async def list_baselines(project_name: str):
    """
    List all baseline snapshots for a project.
    """
    project_dir = get_project_dir(project_name)

    try:
        tester = VisualRegressionTester(project_dir)
        baselines = tester.list_baselines()

        return BaselineListResponse(
            baselines=[BaselineItem(**b) for b in baselines],
            count=len(baselines),
        )
    except Exception as e:
        logger.error(f"Error listing baselines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{project_name}", response_model=ReportListResponse)
async def list_reports(project_name: str):
    """
    List all visual test reports for a project.
    """
    project_dir = get_project_dir(project_name)
    reports_dir = project_dir / ".visual-snapshots" / "reports"

    if not reports_dir.exists():
        return ReportListResponse(reports=[], count=0)

    reports = []
    for report_file in sorted(reports_dir.glob("visual_test_*.json"), reverse=True):
        try:
            with open(report_file) as f:
                data = json.load(f)

            summary = data.get("summary", {})
            reports.append(
                ReportListItem(
                    filename=report_file.name,
                    test_time=data.get("test_time", ""),
                    total=summary.get("total", 0),
                    passed=summary.get("passed", 0),
                    failed=summary.get("failed", 0),
                )
            )
        except Exception as e:
            logger.warning(f"Error reading report {report_file}: {e}")

    return ReportListResponse(reports=reports, count=len(reports))


@router.get("/reports/{project_name}/{filename}")
async def get_report(project_name: str, filename: str):
    """
    Get a specific visual test report.
    """
    project_dir = get_project_dir(project_name)

    # Validate filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    report_path = project_dir / ".visual-snapshots" / "reports" / filename

    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    try:
        with open(report_path) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading report: {e}")


@router.post("/update-baseline")
async def update_baseline(request: UpdateBaselineRequest):
    """
    Accept current screenshot as new baseline.
    """
    project_dir = get_project_dir(request.project_name)

    try:
        tester = VisualRegressionTester(project_dir)
        success = tester.update_baseline(request.name, request.viewport)

        if success:
            return {"updated": True, "name": request.name, "viewport": request.viewport}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Current snapshot not found: {request.name}_{request.viewport}",
            )
    except Exception as e:
        logger.error(f"Error updating baseline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/baselines/{project_name}/{name}/{viewport}")
async def delete_baseline(project_name: str, name: str, viewport: str):
    """
    Delete a baseline snapshot.
    """
    project_dir = get_project_dir(project_name)

    # Validate inputs
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid name")
    if ".." in viewport or "/" in viewport or "\\" in viewport:
        raise HTTPException(status_code=400, detail="Invalid viewport")

    try:
        tester = VisualRegressionTester(project_dir)
        success = tester.delete_baseline(name, viewport)

        if success:
            return {"deleted": True, "name": name, "viewport": viewport}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Baseline not found: {name}_{viewport}",
            )
    except Exception as e:
        logger.error(f"Error deleting baseline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot/{project_name}/{snapshot_type}/{filename}")
async def get_snapshot(project_name: str, snapshot_type: str, filename: str):
    """
    Get a snapshot image.

    Args:
        project_name: Project name
        snapshot_type: Type of snapshot (baselines, current, diffs)
        filename: Image filename
    """
    project_dir = get_project_dir(project_name)

    # Validate inputs
    valid_types = ["baselines", "current", "diffs"]
    if snapshot_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid snapshot type. Valid types: {', '.join(valid_types)}",
        )

    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filename.endswith(".png"):
        raise HTTPException(status_code=400, detail="Only PNG files are supported")

    snapshot_path = project_dir / ".visual-snapshots" / snapshot_type / filename

    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {filename}")

    return FileResponse(snapshot_path, media_type="image/png")


@router.delete("/reports/{project_name}/{filename}")
async def delete_report(project_name: str, filename: str):
    """
    Delete a visual test report.
    """
    project_dir = get_project_dir(project_name)

    # Validate filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    report_path = project_dir / ".visual-snapshots" / "reports" / filename

    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    try:
        report_path.unlink()
        return {"deleted": True, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting report: {e}")
