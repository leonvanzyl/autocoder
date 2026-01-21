"""
Visual Regression Testing
=========================

Screenshot comparison testing for detecting unintended UI changes.

Features:
- Capture screenshots after feature completion via Playwright
- Store baselines in .visual-snapshots/
- Compare screenshots with configurable threshold
- Generate diff images highlighting changes
- Flag features for review when changes detected
- Support for multiple viewports and themes

Configuration:
- visual_regression.enabled: Enable/disable visual testing
- visual_regression.threshold: Pixel difference threshold (default: 0.1%)
- visual_regression.viewports: List of viewport sizes to test
- visual_regression.capture_on_pass: Capture on feature pass (default: true)

Requirements:
- Playwright must be installed: pip install playwright
- Browsers must be installed: playwright install chromium
"""

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Check for PIL availability
try:
    from PIL import Image, ImageChops, ImageDraw

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow not installed. Install with: pip install Pillow")

# Check for Playwright availability
try:
    from playwright.async_api import async_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("Playwright not installed. Install with: pip install playwright")


@dataclass
class Viewport:
    """Screen viewport configuration."""

    name: str
    width: int
    height: int

    @classmethod
    def desktop(cls) -> "Viewport":
        return cls("desktop", 1920, 1080)

    @classmethod
    def tablet(cls) -> "Viewport":
        return cls("tablet", 768, 1024)

    @classmethod
    def mobile(cls) -> "Viewport":
        return cls("mobile", 375, 667)


@dataclass
class SnapshotResult:
    """Result of a snapshot comparison."""

    name: str
    viewport: str
    baseline_path: Optional[str] = None
    current_path: Optional[str] = None
    diff_path: Optional[str] = None
    diff_percentage: float = 0.0
    passed: bool = True
    is_new: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "viewport": self.viewport,
            "baseline_path": self.baseline_path,
            "current_path": self.current_path,
            "diff_path": self.diff_path,
            "diff_percentage": self.diff_percentage,
            "passed": self.passed,
            "is_new": self.is_new,
            "error": self.error,
        }


@dataclass
class TestReport:
    """Visual regression test report."""

    project_dir: str
    test_time: str
    results: list[SnapshotResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    new: int = 0

    def __post_init__(self):
        if not self.test_time:
            self.test_time = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        return {
            "project_dir": self.project_dir,
            "test_time": self.test_time,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "new": self.new,
            },
        }


class VisualRegressionTester:
    """
    Visual regression testing using Playwright screenshots.

    Usage:
        tester = VisualRegressionTester(project_dir)
        report = await tester.test_page("http://localhost:3000", "homepage")
        tester.save_report(report)
    """

    def __init__(
        self,
        project_dir: Path,
        threshold: float = 0.1,
        viewports: Optional[list[Viewport]] = None,
    ):
        self.project_dir = Path(project_dir)
        self.threshold = threshold  # Percentage difference allowed
        self.viewports = viewports or [Viewport.desktop()]
        self.snapshots_dir = self.project_dir / ".visual-snapshots"
        self.baselines_dir = self.snapshots_dir / "baselines"
        self.current_dir = self.snapshots_dir / "current"
        self.diff_dir = self.snapshots_dir / "diffs"

        # Ensure directories exist
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        self.current_dir.mkdir(parents=True, exist_ok=True)
        self.diff_dir.mkdir(parents=True, exist_ok=True)

    async def capture_screenshot(
        self,
        url: str,
        name: str,
        viewport: Optional[Viewport] = None,
        wait_for: Optional[str] = None,
        full_page: bool = True,
    ) -> Path:
        """
        Capture a screenshot using Playwright.

        Args:
            url: URL to capture
            name: Screenshot name
            viewport: Viewport configuration
            wait_for: CSS selector to wait for before capture
            full_page: Capture full scrollable page

        Returns:
            Path to saved screenshot
        """
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        viewport = viewport or Viewport.desktop()
        filename = f"{name}_{viewport.name}.png"
        output_path = self.current_dir / filename

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                viewport={"width": viewport.width, "height": viewport.height}
            )

            try:
                await page.goto(url, wait_until="networkidle")

                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=10000)

                # Small delay for animations to settle
                await asyncio.sleep(0.5)

                await page.screenshot(path=str(output_path), full_page=full_page)

            finally:
                await browser.close()

        return output_path

    def compare_images(
        self,
        baseline_path: Path,
        current_path: Path,
        diff_path: Path,
    ) -> tuple[float, bool]:
        """
        Compare two images and generate diff.

        Args:
            baseline_path: Path to baseline image
            current_path: Path to current image
            diff_path: Path to save diff image

        Returns:
            Tuple of (diff_percentage, passed)
        """
        if not HAS_PIL:
            raise RuntimeError("Pillow not installed. Run: pip install Pillow")

        baseline = Image.open(baseline_path).convert("RGB")
        current = Image.open(current_path).convert("RGB")

        # Resize if dimensions differ
        if baseline.size != current.size:
            current = current.resize(baseline.size, Image.Resampling.LANCZOS)

        # Calculate difference
        diff = ImageChops.difference(baseline, current)

        # Count different pixels
        diff_data = diff.getdata()
        total_pixels = baseline.size[0] * baseline.size[1]
        diff_pixels = sum(1 for pixel in diff_data if sum(pixel) > 30)  # Threshold for "different"

        diff_percentage = (diff_pixels / total_pixels) * 100

        # Generate highlighted diff image
        if diff_percentage > 0:
            # Create diff overlay
            diff_highlight = Image.new("RGBA", baseline.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(diff_highlight)

            for y in range(baseline.size[1]):
                for x in range(baseline.size[0]):
                    pixel = diff.getpixel((x, y))
                    if sum(pixel) > 30:
                        draw.point((x, y), fill=(255, 0, 0, 128))  # Red highlight

            # Composite with original
            result = Image.alpha_composite(baseline.convert("RGBA"), diff_highlight)
            result.save(diff_path)

        passed = diff_percentage <= self.threshold

        return diff_percentage, passed

    async def test_page(
        self,
        url: str,
        name: str,
        wait_for: Optional[str] = None,
        update_baseline: bool = False,
    ) -> TestReport:
        """
        Test a page across all viewports.

        Args:
            url: URL to test
            name: Test name
            wait_for: CSS selector to wait for
            update_baseline: If True, update baselines instead of comparing

        Returns:
            TestReport with results
        """
        report = TestReport(
            project_dir=str(self.project_dir),
            test_time=datetime.utcnow().isoformat() + "Z",
        )

        for viewport in self.viewports:
            result = SnapshotResult(name=name, viewport=viewport.name)

            try:
                # Capture current screenshot
                current_path = await self.capture_screenshot(
                    url, name, viewport, wait_for
                )
                result.current_path = str(current_path.relative_to(self.project_dir))

                # Check for baseline
                baseline_filename = f"{name}_{viewport.name}.png"
                baseline_path = self.baselines_dir / baseline_filename
                result.baseline_path = str(baseline_path.relative_to(self.project_dir))

                if not baseline_path.exists() or update_baseline:
                    # New baseline - copy current to baseline
                    import shutil

                    shutil.copy(current_path, baseline_path)
                    result.is_new = True
                    result.passed = True
                    report.new += 1
                else:
                    # Compare with baseline
                    diff_filename = f"{name}_{viewport.name}_diff.png"
                    diff_path = self.diff_dir / diff_filename

                    diff_percentage, passed = self.compare_images(
                        baseline_path, current_path, diff_path
                    )

                    result.diff_percentage = diff_percentage
                    result.passed = passed

                    if not passed:
                        result.diff_path = str(diff_path.relative_to(self.project_dir))
                        report.failed += 1
                    else:
                        report.passed += 1

            except Exception as e:
                result.error = str(e)
                result.passed = False
                report.failed += 1
                logger.error(f"Visual test error for {name}/{viewport.name}: {e}")

            report.results.append(result)
            report.total += 1

        return report

    async def test_routes(
        self,
        base_url: str,
        routes: list[dict],
        update_baseline: bool = False,
    ) -> TestReport:
        """
        Test multiple routes.

        Args:
            base_url: Base URL (e.g., http://localhost:3000)
            routes: List of routes to test [{"path": "/", "name": "home", "wait_for": "#app"}]
            update_baseline: Update baselines instead of comparing

        Returns:
            Combined TestReport
        """
        combined_report = TestReport(
            project_dir=str(self.project_dir),
            test_time=datetime.utcnow().isoformat() + "Z",
        )

        for route in routes:
            url = base_url.rstrip("/") + route["path"]
            name = route.get("name", route["path"].replace("/", "_").strip("_") or "home")
            wait_for = route.get("wait_for")

            report = await self.test_page(url, name, wait_for, update_baseline)

            combined_report.results.extend(report.results)
            combined_report.total += report.total
            combined_report.passed += report.passed
            combined_report.failed += report.failed
            combined_report.new += report.new

        return combined_report

    def save_report(self, report: TestReport) -> Path:
        """Save test report to file."""
        reports_dir = self.snapshots_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"visual_test_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        return report_path

    def update_baseline(self, name: str, viewport: str) -> bool:
        """
        Accept current screenshot as new baseline.

        Args:
            name: Test name
            viewport: Viewport name

        Returns:
            True if successful
        """
        filename = f"{name}_{viewport}.png"
        current_path = self.current_dir / filename
        baseline_path = self.baselines_dir / filename

        if current_path.exists():
            import shutil

            shutil.copy(current_path, baseline_path)

            # Clean up diff if exists
            diff_path = self.diff_dir / f"{name}_{viewport}_diff.png"
            if diff_path.exists():
                diff_path.unlink()

            return True

        return False

    def list_baselines(self) -> list[dict]:
        """List all baseline snapshots."""
        baselines = []

        for file in self.baselines_dir.glob("*.png"):
            stat = file.stat()
            parts = file.stem.rsplit("_", 1)
            name = parts[0] if len(parts) > 1 else file.stem
            viewport = parts[1] if len(parts) > 1 else "desktop"

            baselines.append(
                {
                    "name": name,
                    "viewport": viewport,
                    "filename": file.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return baselines

    def delete_baseline(self, name: str, viewport: str) -> bool:
        """Delete a baseline snapshot."""
        filename = f"{name}_{viewport}.png"
        baseline_path = self.baselines_dir / filename

        if baseline_path.exists():
            baseline_path.unlink()
            return True

        return False


async def run_visual_tests(
    project_dir: Path,
    base_url: str,
    routes: Optional[list[dict]] = None,
    threshold: float = 0.1,
    update_baseline: bool = False,
) -> TestReport:
    """
    Run visual regression tests for a project.

    Args:
        project_dir: Project directory
        base_url: Base URL to test
        routes: Routes to test (default: [{"path": "/", "name": "home"}])
        threshold: Diff threshold percentage
        update_baseline: Update baselines instead of comparing

    Returns:
        TestReport with results
    """
    if routes is None:
        routes = [{"path": "/", "name": "home"}]

    tester = VisualRegressionTester(project_dir, threshold)
    report = await tester.test_routes(base_url, routes, update_baseline)
    tester.save_report(report)

    return report


def run_visual_tests_sync(
    project_dir: Path,
    base_url: str,
    routes: Optional[list[dict]] = None,
    threshold: float = 0.1,
    update_baseline: bool = False,
) -> TestReport:
    """Synchronous wrapper for run_visual_tests."""
    return asyncio.run(
        run_visual_tests(project_dir, base_url, routes, threshold, update_baseline)
    )
