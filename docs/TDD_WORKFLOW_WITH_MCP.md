"""
TDD Workflow with MCP Test Server
===================================

This example shows how Claude agents use the Test MCP Server
to follow Test-Driven Development (TDD) workflow.

The agent can:
1. Detect the project's testing framework
2. Generate test files automatically
3. Run tests with CI-safe commands
4. Get structured results back

No complex prompt engineering needed - the agent discovers
these tools naturally via MCP.
"""

import asyncio
from anthropic import Anthropic
from pathlib import Path

# In real usage, you'd import the MCP server
# For this example, we show the workflow conceptually


async def tdd_workflow_example():
    """
    Example of TDD workflow with MCP tools.

    This shows what the agent does internally when you give it
    a feature implementation task.
    """

    # ===== STEP 1: Agent discovers testing setup =====
    print("🔍 Step 1: Detecting framework...")
    # Agent calls: detect_project_framework()
    # Returns: { framework: "pytest", test_dir: "tests/", ... }

    # ===== STEP 2: Agent creates test file =====
    print("\n📝 Step 2: Generating test file...")
    # Agent calls: generate_test_file(
    #     feature_name="User Authentication",
    #     feature_description="JWT-based login system",
    #     test_cases=["Valid credentials return token", ...]
    # )
    # Returns: { test_file_path: "tests/test_user_auth.py" }

    # ===== STEP 3: Agent runs tests (RED phase) =====
    print("\n🔴 Step 3: Running tests (should FAIL)...")
    # Agent calls: run_tests()
    # Returns: { passed: false, exit_code: 1, errors: "...FAILED..." }

    # ===== STEP 4: Agent implements feature =====
    print("\n🔨 Step 4: Implementing feature...")
    # Agent writes code to make tests pass

    # ===== STEP 5: Agent runs tests again (GREEN phase) =====
    print("\n🟢 Step 5: Running tests (should PASS)...")
    # Agent calls: run_tests()
    # Returns: { passed: true, exit_code: 0, summary: {...} }

    # ===== STEP 6: Gatekeeper verifies =====
    print("\n🛡️ Step 6: Gatekeeper verification...")
    # Gatekeeper calls: run_tests() (fresh run)
    # If passed: Merge to main
    # If failed: Reject and retry

    print("\n✅ TDD workflow complete!")


# ============================================================================
# Real Integration Example
# ============================================================================

def example_agent_prompt_with_tdd():
    """
    Example prompt you give to an agent with TDD instructions.

    The agent will naturally use the MCP tools to accomplish this.
    """

    return """
You are implementing a new feature following Test-Driven Development.

Feature: User Authentication with JWT
Description: Allow users to login with email/password, receive JWT token

TDD Workflow:
1. Detect the project's testing framework
2. Generate a test file for "User Authentication"
3. Run the tests (they should FAIL - this is expected)
4. Implement the authentication feature
5. Run tests again until they PASS
6. Create a checkpoint commit after each passing test

Available Tools:
- detect_project_framework(): Learn which framework to use
- generate_test_file(): Create test scaffolding
- run_tests(): Execute tests with CI-safe flags

Important:
- Follow TDD strictly: tests FIRST, then implementation
- Run tests frequently (after each small change)
- Create git checkpoints after each success
- If tests fail, read the error output and fix issues
"""

# ============================================================================
# Gatekeeper Integration
# ============================================================================

class Gatekeeper:
    """
    Gatekeeper agent that verifies work before merging.

    The Gatekeeper is the ONLY agent allowed to merge to main branch.
    """

    def __init__(self, project_path: str):
        self.project_path = project_path
        # Import TestMCPServer
        from mcp_server.test_mcp import TestMCPServer
        self.test_server = TestMCPServer(project_path)

    def verify_feature(self, feature_branch: str) -> dict:
        """
        Verify a feature branch before merging.

        Args:
            feature_branch: Name of the feature branch to verify

        Returns:
            Verification result with approve/reject decision
        """
        print(f"🛡️ Gatekeeper: Verifying {feature_branch}...")

        # Step 1: Run tests
        test_result = self.test_server.run_tests(timeout=300)

        if not test_result.get("success"):
            return {
                "approved": False,
                "reason": "Test execution failed",
                "error": test_result.get("error")
            }

        # Step 2: Check if tests passed
        if not test_result.get("passed"):
            summary = test_result.get("summary", {})
            return {
                "approved": False,
                "reason": "Tests failed",
                "summary": summary,
                "output": test_result.get("output", "")[:1000],
                "errors": test_result.get("errors", "")[:1000]
            }

        # Step 3: Tests passed - approve merge
        print("✅ Gatekeeper: Tests passed. Approving merge.")
        return {
            "approved": True,
            "reason": "All tests passed",
            "summary": test_result.get("summary", {})
        }


# ============================================================================
# Example: Full Agent + MCP Integration
# ============================================================================

async def full_workflow_example():
    """
    Complete example showing agents + MCP server + Gatekeeper.
    """

    print("=" * 60)
    print("AUTONOMOUS CODING AGENT - TDD WORKFLOW")
    print("=" * 60)

    # Worker Agent receives task
    task = """
    Implement User Authentication feature:
    - Email/password login
    - JWT token generation
    - Password hashing with bcrypt
    """

    print(f"\n📋 Task: {task}")

    # Worker Agent uses MCP tools
    print("\n" + "=" * 60)
    print("WORKER AGENT")
    print("=" * 60)

    # 1. Detect framework
    print("\n1️⃣ Detecting framework...")
    # result = await agent.call_tool("test_mcp", "detect_project_framework")

    # 2. Generate test file
    print("\n2️⃣ Generating test file...")
    # result = await agent.call_tool(
    #     "test_mcp",
    #     "generate_test_file",
    #     feature_name="User Authentication",
    #     feature_description="JWT-based login with bcrypt"
    # )

    # 3. Run tests (RED)
    print("\n3️⃣ Running tests (RED - should fail)...")
    # result = await agent.call_tool("test_mcp", "run_tests")

    # 4. Implement feature
    print("\n4️⃣ Implementing feature...")
    # Agent writes code...

    # 5. Run tests (GREEN)
    print("\n5️⃣ Running tests (GREEN - should pass)...")
    # result = await agent.call_tool("test_mcp", "run_tests")

    # 6. Submit for review
    print("\n6️⃣ Submitting to Gatekeeper...")

    # Gatekeeper verifies
    print("\n" + "=" * 60)
    print("GATEKEEPER")
    print("=" * 60)

    gatekeeper = Gatekeeper(".")
    # verification = gatekeeper.verify_feature("feat/user-auth-001")

    print("\n7️⃣ Gatekeeper verification...")
    # if verification["approved"]:
    #     print("✅ Merging to main branch")
    #     # git merge --no-ff feat/user-auth-001
    # else:
    #     print("❌ Rejected - fixes needed")
    #     # Send back to worker agent

    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60)


# ============================================================================
# MCP Server Configuration
# ============================================================================

def setup_mcp_server_config():
    """
    Configuration for starting the MCP Test Server.

    Add this to your MCP server configuration file.
    """

    config = {
        "mcpServers": {
            "test-orchestrator": {
                "command": "python",
                "args": ["mcp_server/test_mcp.py"],
                "env": {
                    "PYTHONPATH": str(Path(__file__).parent)
                }
            }
        }
    }

    return config


# ============================================================================
# Usage Instructions
# ============================================================================

USAGE_INSTRUCTIONS = """
# Using the Test MCP Server

## Option 1: Standalone MCP Server

Start the server:
```bash
python mcp_server/test_mcp.py
```

Then configure your Claude Agent SDK to connect to it.

## Option 2: In-Process (Recommended)

Import directly in your agent code:
```python
from mcp_server.test_mcp import TestMCPServer

# Create server instance
test_server = TestMCPServer(project_path="./my-project")

# Use it
framework = test_server.detect_framework()
print(f"Framework: {framework['data']['framework']}")

# Generate tests
test_server.generate_test(
    feature_name="User Login",
    feature_description="JWT authentication"
)

# Run tests
results = test_server.run_tests()
if results["passed"]:
    print("✅ All tests passed!")
```

## Option 3: Agent with MCP Tools

When creating an agent, register the MCP server:
```python
from anthropic.agent import ClaudeAgent
from mcp_server.test_mcp import mcp

agent = ClaudeAgent(
    name="Developer",
    mcp_servers={"testing": mcp}
)

# Agent can now call tools:
# - detect_project_framework()
# - generate_test_file()
# - run_tests()
# - get_framework_info()
```

## Available Tools

### detect_project_framework(project_path=".")
Analyzes the project to detect testing framework.

Returns:
{
  "success": true,
  "data": {
    "language": "python",
    "framework": "pytest",
    "test_command": "pytest",
    "ci_safe_test_command": "pytest --color=no --tb=short -v",
    "test_dir": "tests/",
    "file_pattern": "test_*.py"
  }
}

### generate_test_file(feature_name, feature_description, project_path=".", test_cases=None)
Generates a test file in the correct format.

Args:
- feature_name: "User Authentication"
- feature_description: "JWT-based login system"
- test_cases: Optional JSON array of test cases

Returns:
{
  "success": true,
  "test_file_path": "tests/test_user_authentication.py",
  "test_cases_count": 3
}

### run_tests(project_path=".", timeout=300)
Runs the test suite with CI-safe flags.

Returns:
{
  "success": true,
  "passed": true,
  "exit_code": 0,
  "command": "pytest --color=no --tb=short -v",
  "output": "...",
  "summary": {
    "total": 15,
    "passed": 15,
    "failed": 0
  }
}

### get_framework_info(project_path=".")
Get detailed framework information.

Returns comprehensive info about the detected framework including
setup commands, file patterns, and recommended workflow.
"""


if __name__ == "__main__":
    print(USAGE_INSTRUCTIONS)

    # Run the example workflow
    # asyncio.run(full_workflow_example())
