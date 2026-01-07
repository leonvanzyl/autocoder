"""
Test Framework Detector
========================

Automatically detects which test framework and commands a project uses.

Different projects use different testing setups:
- JavaScript: Jest, Vitest, Mocha, Jasmine
- Python: pytest, unittest, nose2
- Go: go test, testify
- Ruby: RSpec, Minitest

This detector analyzes the project to find:
1. Which language/framework is being used
2. What test command to run
3. Where test files should be created
4. How to structure tests for that framework
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class TestFrameworkDetector:
    """Detects the testing framework and commands for a project."""

    def __init__(self, project_dir: str):
        """
        Initialize the detector for a project.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = Path(project_dir).resolve()
        self.framework_info = None
        self._detect_framework()

    def _detect_framework(self) -> Dict:
        """
        Detect which testing framework the project uses.

        Returns framework info dictionary with:
        {
            "language": "python" | "javascript" | "typescript" | "go" | "ruby",
            "framework": "pytest" | "jest" | "vitest" | "go test" | ...,
            "test_command": "pytest" | "npm test" | "go test ./..." | ...,
            "test_dir": "tests/" | "__tests__/" | "test/" | ...,
            "file_pattern": "test_*.py" | "*.test.js" | "*_test.go" | ...,
            "setup_command": "pip install pytest" | "npm install" | ...,
            "template": template_function_for_creating_tests
        }
        """
        logger.info(f"Detecting test framework for: {self.project_dir}")

        # Check for Python
        if (self.project_dir / "pyproject.toml").exists() or \
           (self.project_dir / "setup.py").exists() or \
           (self.project_dir / "requirements.txt").exists():
            self.framework_info = self._detect_python_framework()
            return self.framework_info

        # Check for JavaScript/TypeScript (Node.js)
        if (self.project_dir / "package.json").exists():
            self.framework_info = self._detect_javascript_framework()
            return self.framework_info

        # Check for Go
        if (self.project_dir / "go.mod").exists():
            self.framework_info = self._detect_go_framework()
            return self.framework_info

        # Check for Ruby
        if (self.project_dir / "Gemfile").exists():
            self.framework_info = self._detect_ruby_framework()
            return self.framework_info

        # Check for iOS/Xcode projects
        xcode_proj = list(self.project_dir.glob("*.xcodeproj"))
        xcode_workspace = list(self.project_dir.glob("*.xcworkspace"))

        if xcode_proj or xcode_workspace:
            self.framework_info = self._detect_ios_framework(xcode_workspace, xcode_proj)
            return self.framework_info

        # Default: Couldn't detect
        logger.warning("Could not detect test framework, using defaults")
        self.framework_info = {
            "language": "unknown",
            "framework": "unknown",
            "test_command": None,
            "test_dir": "tests/",
            "file_pattern": None,
            "setup_command": None,
            "template": self._generic_test_template
        }

        return self.framework_info

    def _detect_python_framework(self) -> Dict:
        """Detect Python testing framework."""
        logger.info("Detected Python project")

        # Check for pytest (most common)
        try:
            result = subprocess.run(
                ["pytest", "--version"],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info("Found pytest")
                return {
                    "language": "python",
                    "framework": "pytest",
                    "test_command": "pytest",
                    "test_dir": "tests/",
                    "file_pattern": "test_*.py",
                    "setup_command": "pip install pytest pytest-cov",
                    "template": self._pytest_template
                }
        except FileNotFoundError:
            pass

        # Check for unittest (built-in)
        logger.info("Using unittest (Python built-in)")
        return {
            "language": "python",
            "framework": "unittest",
            "test_command": "python -m unittest discover",
            "test_dir": "tests/",
            "file_pattern": "test_*.py",
            "setup_command": None,  # Built-in, no setup needed
            "template": self._unittest_template
        }

    def _detect_javascript_framework(self) -> Dict:
        """Detect JavaScript/TypeScript testing framework."""
        logger.info("Detected JavaScript/TypeScript project")

        # Read package.json to find test scripts
        package_json_path = self.project_dir / "package.json"

        try:
            with open(package_json_path) as f:
                package_json = json.load(f)

            # Check dependencies for test frameworks
            dependencies = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {})
            }

            # Vitest (modern, fast)
            if "vitest" in dependencies:
                logger.info("Found Vitest")
                return {
                    "language": "typescript",
                    "framework": "vitest",
                    "test_command": "npm test",
                    "test_dir": "__tests__/",
                    "file_pattern": "*.test.ts",
                    "setup_command": "npm install",
                    "template": self._vitest_template
                }

            # Jest (most common)
            if "jest" in dependencies:
                logger.info("Found Jest")
                return {
                    "language": "typescript",
                    "framework": "jest",
                    "test_command": "npm test",
                    "test_dir": "__tests__/",
                    "file_pattern": "*.test.ts",
                    "setup_command": "npm install",
                    "template": self._jest_template
                }

            # Mocha
            if "mocha" in dependencies:
                logger.info("Found Mocha")
                return {
                    "language": "javascript",
                    "framework": "mocha",
                    "test_command": "npm test",
                    "test_dir": "test/",
                    "file_pattern": "*.test.js",
                    "setup_command": "npm install",
                    "template": self._mocha_template
                }

            # Jasmine
            if "jasmine" in dependencies:
                logger.info("Found Jasmine")
                return {
                    "language": "javascript",
                    "framework": "jasmine",
                    "test_command": "npm test",
                    "test_dir": "spec/",
                    "file_pattern": "*[sS]pec.js",
                    "setup_command": "npm install",
                    "template": self._jasmine_template
                }

            # Check scripts for test command
            scripts = package_json.get("scripts", {})
            if "test" in scripts:
                test_command = scripts["test"]
                logger.info(f"Found test script: {test_command}")
                return {
                    "language": "javascript",
                    "framework": "custom",
                    "test_command": "npm test",  # Use npm test which runs the script
                    "test_dir": "test/",
                    "file_pattern": "*.test.js",
                    "setup_command": "npm install",
                    "template": self._generic_test_template
                }

        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error reading package.json: {e}")

        # Default for Node.js projects
        logger.info("Using default Jest setup for Node.js")
        return {
            "language": "typescript",
            "framework": "jest",
            "test_command": "npm test",
            "test_dir": "__tests__/",
            "file_pattern": "*.test.ts",
            "setup_command": "npm install --save-dev jest",
            "template": self._jest_template
        }

    def _detect_go_framework(self) -> Dict:
        """Detect Go testing framework."""
        logger.info("Detected Go project")
        return {
            "language": "go",
            "framework": "go test",
            "test_command": "go test ./...",
            "test_dir": "",  # Go uses _test.go files alongside code
            "file_pattern": "*_test.go",
            "setup_command": None,
            "template": self._go_test_template
        }

    def _detect_ios_framework(self, workspaces: List, projects: List) -> Dict:
        """Detect iOS/Swift testing framework."""
        logger.info("Detected iOS/Xcode project")

        # Prefer workspaces over projects
        if workspaces:
            target = workspaces[0].stem  # filename without extension
            logger.info(f"Found workspace: {target}.xcworkspace")
        else:
            target = projects[0].stem
            logger.info(f"Found project: {target}.xcodeproj")

        # Check for Fastlane (preferred for CI/Agents)
        fastfile_paths = [
            self.project_dir / "Fastfile",
            self.project_dir / "fastlane" / "Fastfile"
        ]

        for fastfile in fastfile_paths:
            if fastfile.exists():
                logger.info("Found Fastlane - using fastlane scan")
                return {
                    "language": "swift",
                    "framework": "xctest-fastlane",
                    "test_command": f"fastlane scan --scheme {target}",
                    "test_dir": "Tests/",
                    "file_pattern": "*Tests.swift",
                    "setup_command": "bundle install",
                    "template": self._xctest_template,
                    "ci_safe": True  # Fastlane outputs structured logs
                }

        # Fallback to xcodebuild
        logger.info("Using xcodebuild directly")
        return {
            "language": "swift",
            "framework": "xctest",
            "test_command": f"xcodebuild test -scheme {target} -destination 'platform=iOS Simulator,name=iPhone 16'",
            "test_dir": "Tests/",
            "file_pattern": "*Tests.swift",
            "setup_command": None,
            "template": self._xctest_template,
            "ci_safe": False  # xcodebuild output is verbose/unstructured
        }

    def _detect_ruby_framework(self) -> Dict:
        """Detect Ruby testing framework."""
        logger.info("Detected Ruby project")

        # Check for RSpec
        if (self.project_dir / "spec" ).exists():
            logger.info("Found RSpec")
            return {
                "language": "ruby",
                "framework": "rspec",
                "test_command": "bundle exec rspec",
                "test_dir": "spec/",
                "file_pattern": "*_spec.rb",
                "setup_command": "bundle install",
                "template": self._rspec_template
            }

        # Default to Minitest
        logger.info("Using Minitest (Ruby default)")
        return {
            "language": "ruby",
            "framework": "minitest",
            "test_command": "ruby test/test_*.rb",
            "test_dir": "test/",
            "file_pattern": "test_*.rb",
            "setup_command": "bundle install",
            "template": self._minitest_template
        }

    def get_framework_info(self) -> Dict:
        """Get the detected framework information."""
        return self.framework_info

    def get_test_command(self, ci_mode: bool = True) -> Optional[str]:
        """
        Get the test command for this project.

        Args:
            ci_mode: If True, adds non-interactive flags for CI/Agent safety
                    (prevents watch mode, adds structured output, etc.)

        Returns:
            Test command string, or None if not detected
        """
        base_command = self.framework_info.get("test_command")
        if not base_command:
            return None

        if not ci_mode:
            return base_command

        # Add CI-safe flags to prevent hanging/confusion
        framework = self.framework_info.get("framework", "")

        # Jest/Vitest: Prevent watch mode, use CI mode
        if framework in ["jest", "vitest"]:
            return f"{base_command} -- --watchAll=false --ci"

        # Pytest: Remove ANSI codes (confuses LLMs), use strict mode
        if framework == "pytest":
            return f"{base_command} --color=no --tb=short -v"

        # Go: Verbose mode (better for error parsing)
        if framework == "go test":
            return f"{base_command} -v"

        # XCTest (xcodebuild): Already configured above
        # Mocha/Jasmine: Add reporter
        if framework in ["mocha", "jasmine"]:
            return f"{base_command} --reporter json"

        return base_command

    def get_test_dir(self) -> str:
        """Get the directory where tests should be created."""
        return self.framework_info.get("test_dir", "tests/")

    def generate_test_file(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """
        Generate a test file with appropriate framework.

        Args:
            feature_name: Name of the feature being tested
            feature_description: Description of what the feature does
            test_cases: List of test case descriptions

        Returns:
            Path to the generated test file
        """
        template = self.framework_info.get("template")
        test_dir = self.framework_info.get("test_dir", "tests/")

        if not template:
            logger.warning("No test template available for this framework")
            return None

        # Call the template function
        test_content = template(
            feature_name=feature_name,
            feature_description=feature_description,
            test_cases=test_cases
        )

        # Determine test file path
        test_file_pattern = self.framework_info.get("file_pattern", "test_*.py")
        safe_feature_name = feature_name.lower().replace(" ", "_").replace("-", "_")

        if self.framework_info["language"] == "python":
            test_filename = f"test_{safe_feature_name}.py"
        elif self.framework_info["language"] == "typescript":
            test_filename = f"{safe_feature_name}.test.ts"
        elif self.framework_info["language"] == "javascript":
            test_filename = f"{safe_feature_name}.test.js"
        elif self.framework_info["language"] == "go":
            test_filename = f"{safe_feature_name}_test.go"
        elif self.framework_info["language"] == "ruby":
            test_filename = f"{safe_feature_name}_spec.rb"
        else:
            test_filename = f"test_{safe_feature_name}.txt"

        test_file_path = self.project_dir / test_dir / test_filename

        # Create test directory if it doesn't exist
        test_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write test file
        with open(test_file_path, 'w') as f:
            f.write(test_content)

        logger.info(f"Created test file: {test_file_path}")
        return str(test_file_path)

    def _pytest_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate pytest test file."""
        test_name = feature_name.replace(" ", "_").lower()

        tests = []
        for i, test_case in enumerate(test_cases, 1):
            test_function = f"test_{test_name}_{i}"
            tests.append(f'''
def {test_function}():
    """
    Test: {test_case}

    Feature: {feature_description}
    """
    # TODO: Implement test for: {test_case}
    assert True  # Placeholder - implement actual test
''')

        return f'''"""
Tests for {feature_name}

Feature: {feature_description}
"""

import pytest


class Test{feature_name.replace(" ", "")}:
    """Test suite for {feature_name}."""

{''.join(tests)}
'''

    def _unittest_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate unittest test file."""
        class_name = feature_name.replace(" ", "").replace("-", "")

        tests = []
        for i, test_case in enumerate(test_cases, 1):
            test_function = f"test_{feature_name.lower().replace(' ', '_')}_{i}"
            tests.append(f'''
    def {test_function}(self):
        """Test: {test_case}"""
        # TODO: Implement test for: {test_case}
        self.assertTrue(True)  # Placeholder
''')

        return f'''"""
Unit tests for {feature_name}

Feature: {feature_description}
"""

import unittest


class Test{class_name}(unittest.TestCase):
    """Test suite for {feature_name}."""

{''.join(tests)}


if __name__ == '__main__':
    unittest.main()
'''

    def _jest_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate Jest test file."""
        describe_name = feature_name

        tests = []
        for test_case in test_cases:
            tests.append(f'''
  test('{test_case}', () => {{
    // TODO: Implement test for: {test_case}
    expect(true).toBe(true);  // Placeholder
  }});
''')

        return f'''/**
 * Tests for {feature_name}
 *
 * Feature: {feature_description}
 */

describe('{describe_name}', () => {{
{''.join(tests)}
}});
'''

    def _vitest_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate Vitest test file (same as Jest)."""
        return self._jest_template(feature_name, feature_description, test_cases)

    def _mocha_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate Mocha test file."""
        describe_name = feature_name

        tests = []
        for test_case in test_cases:
            tests.append(f'''
  it('{test_case}', function() {{
    // TODO: Implement test for: {test_case}
    assert.isTrue(true);  // Placeholder
  }});
''')

        return f'''/**
 * Tests for {feature_name}
 *
 * Feature: {feature_description}
 */

const assert = require('assert');

describe('{describe_name}', function() {{
{''.join(tests)}
}});
'''

    def _jasmine_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate Jasmine test file."""
        describe_name = feature_name

        tests = []
        for test_case in test_cases:
            tests.append(f'''
  it('{test_case}', function() {{
    // TODO: Implement test for: {test_case}
    expect(true).toBe(true);  // Placeholder
  }});
''')

        return f'''/**
 * Tests for {feature_name}
 *
 * Feature: {feature_description}
 */

describe('{describe_name}', function() {{
{''.join(testes)}
}});
'''

    def _go_test_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate Go test file."""
        func_name = feature_name.replace(" ", "").replace("-", "")

        tests = []
        for i, test_case in enumerate(test_cases, 1):
            test_function = f"Test{func_name}{i}"
            tests.append(f'''
func {test_function}(t *testing.T) {{
    // Test: {test_case}
    // TODO: Implement test for: {test_case}
}}
''')

        return f'''package tests

import "testing"

// {feature_name}
//
// Feature: {feature_description}

{''.join(tests)}
'''

    def _rspec_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate RSpec test file."""
        describe_name = feature_name

        tests = []
        for test_case in test_cases:
            tests.append(f'''
  it '{test_case}' do
    # TODO: Implement test for: {test_case}
    expect(true).to be_truthful  # Placeholder
  end
''')

        return f'''# Tests for {feature_name}
#
# Feature: {feature_description}

RSpec.describe '{describe_name}' do
{''.join(tests)}
end
'''

    def _minitest_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate Minitest test file."""
        class_name = feature_name.replace(" ", "").replace("-", "")

        tests = []
        for i, test_case in enumerate(test_cases, 1):
            test_function = f"test_{feature_name.lower().replace(' ', '_')}_{i}"
            tests.append(f'''
  def {test_function}
    # Test: {test_case}
    # TODO: Implement test for: {test_case}
    assert true  # Placeholder
  end
''')

        return f'''# Tests for {feature_name}
#
# Feature: {feature_description}

require 'minitest/autorun'

class Test{class_name} < Minitest::Test
{''.join(tests)}
end
'''

    def _xctest_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate XCTest (Swift) test file."""
        class_name = feature_name.replace(" ", "").replace("-", "")

        tests = []
        for test_case in test_cases:
            # Convert test case to function name
            test_name = test_case.lower().replace(" ", "_").replace("-", "_").strip(".,!?")
            test_function = f"test{test_name}"

            tests.append(f'''
    func {test_function}() throws {{
        // Test: {test_case}
        // TODO: Implement test for: {test_case}
        XCTFail("Not implemented yet")  // Placeholder
    }}
''')

        return f'''//
//  Tests for {feature_name}
//  Feature: {feature_description}
//

import XCTest
@testable import YourApp  // TODO: Replace with actual app name

final class {class_name}Tests: XCTestCase {{
{''.join(tests)}
}}
'''

    def _generic_test_template(
        self,
        feature_name: str,
        feature_description: str,
        test_cases: List[str]
    ) -> str:
        """Generate generic test file (fallback)."""
        lines = [
            f"# Tests for {feature_name}",
            f"# Feature: {feature_description}",
            "",
            "## Test Cases:",
        ]
        for test_case in test_cases:
            lines.append(f"- [ ] {test_case}")

        return "\n".join(lines)


def test_detector():
    """Test the framework detector."""
    import tempfile

    # Test Python project
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create Python project files
        (test_dir / "requirements.txt").write_text("pytest\n")

        detector = TestFrameworkDetector(str(test_dir))
        info = detector.get_framework_info()

        print(f"Language: {info['language']}")
        print(f"Framework: {info['framework']}")
        print(f"Test Command: {info['test_command']}")
        print(f"Test Dir: {info['test_dir']}")

        # Generate a test file
        test_file = detector.generate_test_file(
            feature_name="User Login",
            feature_description="Allow users to authenticate with email and password",
            test_cases=[
                "Valid email and password should login successfully",
                "Invalid password should show error",
                "Non-existent email should show error"
            ]
        )

        print(f"\nGenerated test file: {test_file}")
        print("\nTest file contents:")
        print((Path(test_file)).read_text())


if __name__ == "__main__":
    test_detector()
