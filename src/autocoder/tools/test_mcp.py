"""
MCP Test Server
===============

Exposes test framework detection and execution as Model Context Protocol tools.

This allows Claude agents to:
1. Detect the project's testing framework automatically
2. Generate test files in the correct format
3. Run tests with CI-safe commands
4. Get structured output back

Architecture:
- FastMCP server wraps TestFrameworkDetector
- Tools are automatically discovered by agents
- No complex prompt engineering needed
- Timeout protection prevents hangs
"""

import os
import subprocess
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

# Try to import FastMCP
try:
    from mcp.server.fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    logging.warning("FastMCP not available. Install with: pip install fastmcp")

# Import our detector
from autocoder.core.test_framework_detector import TestFrameworkDetector

logger = logging.getLogger(__name__)

# Initialize the MCP Server
if FASTMCP_AVAILABLE:
    mcp = FastMCP("Test Orchestrator")
else:
    logger.error("FastMCP not available. MCP server will not function.")
    mcp = None


def detect_framework_sync(project_path: str = ".") -> Dict[str, Any]:
    """
    Synchronous wrapper for framework detection.

    Args:
        project_path: Path to the project directory

    Returns:
        Framework information dictionary
    """
    try:
        detector = TestFrameworkDetector(project_path)
        info = detector.get_framework_info()

        # Add CI-safe test command
        info["ci_safe_test_command"] = detector.get_test_command(ci_mode=True)
        info["dev_test_command"] = detector.get_test_command(ci_mode=False)

        return {
            "success": True,
            "data": info
        }
    except Exception as e:
        logger.error(f"Framework detection failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def generate_test_file_sync(
    project_path: str,
    feature_name: str,
    feature_description: str,
    test_cases: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for test file generation.

    Args:
        project_path: Path to the project
        feature_name: Name of the feature
        feature_description: What the feature does
        test_cases: List of test case descriptions (optional)

    Returns:
        Dictionary with success status and file path
    """
    try:
        detector = TestFrameworkDetector(project_path)

        # Generate default test cases if not provided
        if not test_cases:
            test_cases = [
                f"{feature_name} should succeed with valid input",
                f"{feature_name} should fail with invalid input",
                f"{feature_name} should handle edge cases"
            ]

        test_file_path = detector.generate_test_file(
            feature_name=feature_name,
            feature_description=feature_description,
            test_cases=test_cases
        )

        return {
            "success": True,
            "test_file_path": test_file_path,
            "test_cases_count": len(test_cases)
        }

    except Exception as e:
        logger.error(f"Test file generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def run_tests_sync(
    project_path: str = ".",
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Synchronous wrapper for running tests.

    Args:
        project_path: Path to the project
        timeout: Maximum time to wait for tests (seconds)

    Returns:
        Dictionary with test results
    """
    try:
        detector = TestFrameworkDetector(project_path)
        cmd = detector.get_test_command(ci_mode=True)

        if not cmd:
            return {
                "success": False,
                "error": "No test framework detected"
            }

        logger.info(f"Running tests: {cmd}")

        # Execute with timeout
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Parse output
        output = result.stdout if result.stdout else ""
        errors = result.stderr if result.stderr else ""

        # Determine success
        passed = result.returncode == 0

        return {
            "success": True,
            "passed": passed,
            "exit_code": result.returncode,
            "command": cmd,
            "output": output,
            "errors": errors,
            "summary": _extract_test_summary(output, errors)
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Tests timed out after {timeout} seconds")
        return {
            "success": False,
            "error": f"Tests timed out after {timeout} seconds",
            "timeout": True
        }
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _extract_test_summary(stdout: str, stderr: str) -> Dict[str, Any]:
    """
    Extract test summary from output.

    Parses output to find:
    - Total tests run
    - Passed/failed counts
    - Duration

    Args:
        stdout: Standard output from tests
        stderr: Standard error from tests

    Returns:
        Summary dictionary
    """
    combined = stdout + stderr

    # Try to parse common patterns
    summary = {
        "total": None,
        "passed": None,
        "failed": None,
        "duration": None,
        "raw_output": combined[:500]  # First 500 chars
    }

    # Jest/Vitest pattern: "X passed, Y failed"
    import re
    jest_pattern = r"(\d+)\s+passed,\s*(\d+)\s+failed"
    match = re.search(jest_pattern, combined)
    if match:
        summary["passed"] = int(match.group(1))
        summary["failed"] = int(match.group(2))
        summary["total"] = summary["passed"] + summary["failed"]

    # Pytest pattern
    pytest_pattern = r"(\d+)\s+passed,\s*(\d+)\s+failed"
    match = re.search(pytest_pattern, combined)
    if match:
        summary["passed"] = int(match.group(1))
        summary["failed"] = int(match.group(2))
        summary["total"] = summary["passed"] + summary["failed"]

    return summary


# ============================================================================
# MCP Tool Definitions (FastMCP)
# ============================================================================

if FASTMCP_AVAILABLE:

    @mcp.tool()
    def detect_project_framework(project_path: str = ".") -> str:
        """
        Analyzes the project to detect the testing framework.

        Automatically detects which testing framework the project uses:
        - Python: pytest, unittest
        - JavaScript/TypeScript: Jest, Vitest, Mocha, Jasmine
        - Swift: XCTest, Fastlane
        - Go: go test
        - Ruby: RSpec, Minitest

        Args:
            project_path: Path to the project directory (default: current directory)

        Returns:
            JSON string with framework info including:
            - language: Programming language detected
            - framework: Test framework name
            - test_command: Command to run tests
            - test_dir: Directory for test files
            - ci_safe_test_command: CI-safe command with non-interactive flags
        """
        result = detect_framework_sync(project_path)
        import json
        return json.dumps(result, indent=2)

    @mcp.tool()
    def generate_test_file(
        feature_name: str,
        feature_description: str,
        project_path: str = ".",
        test_cases: Optional[str] = None
    ) -> str:
        """
        Generates a test file for a feature using the detected framework.

        Creates a test file in the proper format for the detected framework
        with placeholder test cases that you should implement.

        Args:
            feature_name: Name of the feature (e.g., "User Login")
            feature_description: What the feature does
            project_path: Path to the project (default: current directory)
            test_cases: Optional JSON array of test case descriptions.
                       If not provided, generates default happy/sad path cases.

        Returns:
            JSON string with:
            - success: Whether file was created
            - test_file_path: Path to created test file
            - test_cases_count: Number of test cases
        """
        # Parse test cases if provided as JSON
        cases_list = None
        if test_cases:
            try:
                import json
                cases_list = json.loads(test_cases)
            except json.JSONDecodeError:
                # If not valid JSON, treat as comma-separated list
                cases_list = [tc.strip() for tc in test_cases.split(",")]

        result = generate_test_file_sync(
            project_path=project_path,
            feature_name=feature_name,
            feature_description=feature_description,
            test_cases=cases_list
        )

        import json
        return json.dumps(result, indent=2)

    @mcp.tool()
    def run_tests(
        project_path: str = ".",
        timeout: int = 300
    ) -> str:
        """
        Runs the project's test suite using the detected framework.

        Executes tests with CI-safe flags (no watch mode, structured output).
        Automatically detects the correct command based on the project.

        Args:
            project_path: Path to the project (default: current directory)
            timeout: Maximum time to wait for tests in seconds (default: 300 = 5 minutes)

        Returns:
            JSON string with:
            - success: Whether tests executed
            - passed: True if all tests passed
            - exit_code: Test runner exit code
            - command: Command that was run
            - output: Standard output
            - errors: Standard error
            - summary: Parsed test counts (total/passed/failed)
        """
        result = run_tests_sync(
            project_path=project_path,
            timeout=timeout
        )

        import json
        return json.dumps(result, indent=2)

    @mcp.tool()
    def get_framework_info(project_path: str = ".") -> str:
        """
        Get detailed information about the detected testing framework.

        Returns comprehensive framework information including setup commands,
        file patterns, and template details.

        Args:
            project_path: Path to the project (default: current directory)

        Returns:
            JSON string with detailed framework information
        """
        result = detect_framework_sync(project_path)

        if result["success"]:
            # Add additional helpful info
            info = result["data"]
            framework_details = {
                "language": info.get("language"),
                "framework": info.get("framework"),
                "test_command": info.get("test_command"),
                "ci_safe_test_command": info.get("ci_safe_test_command"),
                "test_directory": info.get("test_dir"),
                "file_pattern": info.get("file_pattern"),
                "setup_command": info.get("setup_command"),
                "ci_safe": info.get("ci_safe", False),
                "capabilities": {
                    "auto_detect": True,
                    "test_generation": True,
                    "ci_safe_execution": True,
                    "timeout_protection": True
                },
                "recommended_workflow": [
                    "1. Use detect_project_framework to understand setup",
                    "2. Use generate_test_file to create test scaffolding",
                    "3. Implement the actual test logic in the generated file",
                    "4. Use run_tests to verify implementation",
                    "5. Iterate until tests pass"
                ]
            }

            return json.dumps({
                "success": True,
                "data": framework_details
            }, indent=2)
        else:
            return json.dumps(result, indent=2)


# ============================================================================
# Standalone Server (for non-FastMCP usage)
# ============================================================================

class TestMCPServer:
    """
    Test MCP Server class for integration without FastMCP.

    This provides the same interface but can be used directly
    in Python code without running an MCP server.
    """

    def __init__(self, project_path: str = "."):
        """
        Initialize the test server.

        Args:
            project_path: Default project path
        """
        self.project_path = project_path
        self.detector = TestFrameworkDetector(project_path)

    def detect_framework(self) -> Dict[str, Any]:
        """Detect the testing framework."""
        return detect_framework_sync(self.project_path)

    def generate_test(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate a test file."""
        return generate_test_file_sync(
            self.project_path,
            feature_name,
            feature_description,
            test_cases
        )

    def run_tests(self, timeout: int = 300) -> Dict[str, Any]:
        """Run the test suite."""
        return run_tests_sync(self.project_path, timeout)

    def get_framework_info(self) -> Dict[str, Any]:
        """Get detailed framework information."""
        return self.detector.get_framework_info()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the MCP server."""
    if not FASTMCP_AVAILABLE:
        print("ERROR: FastMCP is not installed!")
        print("Install it with: pip install fastmcp")
        return 1

    if mcp:
        mcp.run()
    else:
        print("ERROR: MCP server not initialized")
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
