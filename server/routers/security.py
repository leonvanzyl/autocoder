"""
Security Router
===============

REST API endpoints for security scanning.

Endpoints:
- POST /api/security/scan - Run security scan on a project
- GET /api/security/reports - List scan reports
- GET /api/security/reports/{filename} - Get a specific report
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security", tags=["security"])


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    from registry import get_project_path

    return get_project_path(project_name)


# ============================================================================
# Request/Response Models
# ============================================================================


class ScanRequest(BaseModel):
    """Request to run a security scan."""

    project_name: str = Field(..., description="Name of the registered project")
    scan_dependencies: bool = Field(True, description="Run npm audit / pip-audit")
    scan_secrets: bool = Field(True, description="Scan for hardcoded secrets")
    scan_code: bool = Field(True, description="Scan for code vulnerability patterns")


class VulnerabilityInfo(BaseModel):
    """Information about a detected vulnerability."""

    type: str
    severity: str
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    recommendation: Optional[str] = None
    cwe_id: Optional[str] = None
    package_name: Optional[str] = None
    package_version: Optional[str] = None


class ScanSummary(BaseModel):
    """Summary of scan results."""

    total_issues: int
    critical: int
    high: int
    medium: int
    low: int
    has_critical_or_high: bool


class ScanResponse(BaseModel):
    """Response from security scan."""

    project_dir: str
    scan_time: str
    vulnerabilities: list[VulnerabilityInfo]
    summary: ScanSummary
    scans_run: list[str]
    report_saved: bool


class ReportListResponse(BaseModel):
    """Response listing available reports."""

    reports: list[str]
    count: int


# ============================================================================
# REST Endpoints
# ============================================================================


@router.post("/scan", response_model=ScanResponse)
async def run_security_scan(request: ScanRequest):
    """
    Run a security scan on a project.

    Scans for:
    - Vulnerable dependencies (npm audit, pip-audit)
    - Hardcoded secrets (API keys, passwords, tokens)
    - Code vulnerability patterns (SQL injection, XSS, etc.)

    Results are saved to .autocoder/security-reports/
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    try:
        from security_scanner import scan_project

        result = scan_project(
            project_dir,
            scan_dependencies=request.scan_dependencies,
            scan_secrets=request.scan_secrets,
            scan_code=request.scan_code,
        )

        return ScanResponse(
            project_dir=result.project_dir,
            scan_time=result.scan_time,
            vulnerabilities=[
                VulnerabilityInfo(**v.to_dict()) for v in result.vulnerabilities
            ],
            summary=ScanSummary(**result.summary),
            scans_run=result.scans_run,
            report_saved=True,
        )

    except Exception as e:
        logger.exception(f"Error running security scan: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/reports/{project_name}", response_model=ReportListResponse)
async def list_reports(project_name: str):
    """
    List available security scan reports for a project.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    reports_dir = project_dir / ".autocoder" / "security-reports"
    if not reports_dir.exists():
        return ReportListResponse(reports=[], count=0)

    reports = sorted(
        [f.name for f in reports_dir.glob("security_scan_*.json")],
        reverse=True,
    )

    return ReportListResponse(reports=reports, count=len(reports))


@router.get("/reports/{project_name}/{filename}")
async def get_report(project_name: str, filename: str):
    """
    Get a specific security scan report.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    # Security: validate filename to prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filename.startswith("security_scan_") or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid report filename")

    report_path = project_dir / ".autocoder" / "security-reports" / filename
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        with open(report_path) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading report: {str(e)}")


@router.get("/latest/{project_name}")
async def get_latest_report(project_name: str):
    """
    Get the most recent security scan report for a project.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    reports_dir = project_dir / ".autocoder" / "security-reports"
    if not reports_dir.exists():
        raise HTTPException(status_code=404, detail="No reports found")

    reports = sorted(reports_dir.glob("security_scan_*.json"), reverse=True)
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found")

    try:
        with open(reports[0]) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading report: {str(e)}")
