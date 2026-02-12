#!/usr/bin/env python3
"""
Security Hook Tests
===================

Tests for the bash command security validation logic.
Run with: python test_security.py
"""

import asyncio
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from security import (
    bash_security_hook,
    extract_commands,
    get_effective_commands,
    get_effective_pkill_processes,
    load_org_config,
    load_project_commands,
    matches_pattern,
    validate_chmod_command,
    validate_init_script,
    validate_pkill_command,
    validate_playwright_command,
    validate_project_command,
)


@contextmanager
def temporary_home(home_path):
    """
    Context manager to temporarily set HOME (and Windows equivalents).

    Saves original environment variables and restores them on exit,
    even if an exception occurs.

    Args:
        home_path: Path to use as temporary home directory
    """
    # Save original values for Unix and Windows
    saved_env = {
        "HOME": os.environ.get("HOME"),
        "USERPROFILE": os.environ.get("USERPROFILE"),
        "HOMEDRIVE": os.environ.get("HOMEDRIVE"),
        "HOMEPATH": os.environ.get("HOMEPATH"),
    }

    try:
        # Set new home directory for both Unix and Windows
        os.environ["HOME"] = str(home_path)
        if sys.platform == "win32":
            os.environ["USERPROFILE"] = str(home_path)
            # Note: HOMEDRIVE and HOMEPATH are typically set by Windows
            # but we update them for consistency
            drive, path = os.path.splitdrive(str(home_path))
            if drive:
                os.environ["HOMEDRIVE"] = drive
                os.environ["HOMEPATH"] = path

        yield

    finally:
        # Restore original values
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def check_hook(command: str, should_block: bool) -> bool:
    """Check a single command against the security hook (helper function)."""
    input_data = {"tool_name": "Bash", "tool_input": {"command": command}}
    result = asyncio.run(bash_security_hook(input_data))
    was_blocked = result.get("decision") == "block"

    if was_blocked == should_block:
        status = "PASS"
    else:
        status = "FAIL"
        expected = "blocked" if should_block else "allowed"
        actual = "blocked" if was_blocked else "allowed"
        reason = result.get("reason", "")
        print(f"  {status}: {command!r}")
        print(f"         Expected: {expected}, Got: {actual}")
        if reason:
            print(f"         Reason: {reason}")
        return False

    print(f"  {status}: {command!r}")
    return True


def test_extract_commands():
    """Test the command extraction logic."""
    print("\nTesting command extraction:\n")
    passed = 0
    failed = 0

    test_cases = [
        ("ls -la", ["ls"]),
        ("npm install && npm run build", ["npm", "npm"]),
        ("cat file.txt | grep pattern", ["cat", "grep"]),
        ("/usr/bin/node script.js", ["node"]),
        ("VAR=value ls", ["ls"]),
        ("git status || git init", ["git", "git"]),
        # Fallback parser test: complex nested quotes that break shlex
        ('docker exec container php -r "echo \\"test\\";"', ["docker"]),
    ]

    for cmd, expected in test_cases:
        result = extract_commands(cmd)
        if result == expected:
            print(f"  PASS: {cmd!r} -> {result}")
            passed += 1
        else:
            print(f"  FAIL: {cmd!r}")
            print(f"         Expected: {expected}, Got: {result}")
            failed += 1

    return passed, failed


def test_validate_chmod():
    """Test chmod command validation."""
    print("\nTesting chmod validation:\n")
    passed = 0
    failed = 0

    # Test cases: (command, should_be_allowed, description)
    test_cases = [
        # Allowed cases
        ("chmod +x init.sh", True, "basic +x"),
        ("chmod +x script.sh", True, "+x on any script"),
        ("chmod u+x init.sh", True, "user +x"),
        ("chmod a+x init.sh", True, "all +x"),
        ("chmod ug+x init.sh", True, "user+group +x"),
        ("chmod +x file1.sh file2.sh", True, "multiple files"),
        # Blocked cases
        ("chmod 777 init.sh", False, "numeric mode"),
        ("chmod 755 init.sh", False, "numeric mode 755"),
        ("chmod +w init.sh", False, "write permission"),
        ("chmod +r init.sh", False, "read permission"),
        ("chmod -x init.sh", False, "remove execute"),
        ("chmod -R +x dir/", False, "recursive flag"),
        ("chmod --recursive +x dir/", False, "long recursive flag"),
        ("chmod +x", False, "missing file"),
    ]

    for cmd, should_allow, description in test_cases:
        allowed, reason = validate_chmod_command(cmd)
        if allowed == should_allow:
            print(f"  PASS: {cmd!r} ({description})")
            passed += 1
        else:
            expected = "allowed" if should_allow else "blocked"
            actual = "allowed" if allowed else "blocked"
            print(f"  FAIL: {cmd!r} ({description})")
            print(f"         Expected: {expected}, Got: {actual}")
            if reason:
                print(f"         Reason: {reason}")
            failed += 1

    return passed, failed


def test_validate_init_script():
    """Test init.sh script execution validation."""
    print("\nTesting init.sh validation:\n")
    passed = 0
    failed = 0

    # Test cases: (command, should_be_allowed, description)
    test_cases = [
        # Allowed cases
        ("./init.sh", True, "basic ./init.sh"),
        ("./init.sh arg1 arg2", True, "with arguments"),
        ("/path/to/init.sh", True, "absolute path"),
        ("../dir/init.sh", True, "relative path with init.sh"),
        # Blocked cases
        ("./setup.sh", False, "different script name"),
        ("./init.py", False, "python script"),
        ("bash init.sh", False, "bash invocation"),
        ("sh init.sh", False, "sh invocation"),
        ("./malicious.sh", False, "malicious script"),
        ("./init.sh; rm -rf /", False, "command injection attempt"),
    ]

    for cmd, should_allow, description in test_cases:
        allowed, reason = validate_init_script(cmd)
        if allowed == should_allow:
            print(f"  PASS: {cmd!r} ({description})")
            passed += 1
        else:
            expected = "allowed" if should_allow else "blocked"
            actual = "allowed" if allowed else "blocked"
            print(f"  FAIL: {cmd!r} ({description})")
            print(f"         Expected: {expected}, Got: {actual}")
            if reason:
                print(f"         Reason: {reason}")
            failed += 1

    return passed, failed


def test_pattern_matching():
    """Test command pattern matching."""
    print("\nTesting pattern matching:\n")
    passed = 0
    failed = 0

    # Test cases: (command, pattern, should_match, description)
    test_cases = [
        # Exact matches
        ("swift", "swift", True, "exact match"),
        ("npm", "npm", True, "exact npm"),
        ("xcodebuild", "xcodebuild", True, "exact xcodebuild"),

        # Prefix wildcards
        ("swiftc", "swift*", True, "swiftc matches swift*"),
        ("swiftlint", "swift*", True, "swiftlint matches swift*"),
        ("swiftformat", "swift*", True, "swiftformat matches swift*"),
        ("swift", "swift*", True, "swift matches swift*"),
        ("npm", "swift*", False, "npm doesn't match swift*"),

        # Bare wildcard (security: should NOT match anything)
        ("npm", "*", False, "bare wildcard doesn't match npm"),
        ("sudo", "*", False, "bare wildcard doesn't match sudo"),
        ("anything", "*", False, "bare wildcard doesn't match anything"),

        # Local script paths (with ./ prefix)
        ("build.sh", "./scripts/build.sh", True, "script name matches path"),
        ("./scripts/build.sh", "./scripts/build.sh", True, "exact script path"),
        ("scripts/build.sh", "./scripts/build.sh", True, "relative script path"),
        ("/abs/path/scripts/build.sh", "./scripts/build.sh", True, "absolute path matches"),
        ("test.sh", "./scripts/build.sh", False, "different script name"),

        # Path patterns (without ./ prefix - new behavior)
        ("test.sh", "scripts/test.sh", True, "script name matches path pattern"),
        ("scripts/test.sh", "scripts/test.sh", True, "exact path pattern match"),
        ("/abs/path/scripts/test.sh", "scripts/test.sh", True, "absolute path matches pattern"),
        ("build.sh", "scripts/test.sh", False, "different script name in pattern"),
        ("integration.test.js", "tests/integration.test.js", True, "script with dots matches"),

        # Non-matches
        ("go", "swift*", False, "go doesn't match swift*"),
        ("rustc", "swift*", False, "rustc doesn't match swift*"),
    ]

    for command, pattern, should_match, description in test_cases:
        result = matches_pattern(command, pattern)
        if result == should_match:
            print(f"  PASS: {command!r} vs {pattern!r} ({description})")
            passed += 1
        else:
            expected = "match" if should_match else "no match"
            actual = "match" if result else "no match"
            print(f"  FAIL: {command!r} vs {pattern!r} ({description})")
            print(f"         Expected: {expected}, Got: {actual}")
            failed += 1

    return passed, failed


def test_yaml_loading():
    """Test YAML config loading and validation."""
    print("\nTesting YAML loading:\n")
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        autoforge_dir = project_dir / ".autoforge"
        autoforge_dir.mkdir()

        # Test 1: Valid YAML
        config_path = autoforge_dir / "allowed_commands.yaml"
        config_path.write_text("""version: 1
commands:
  - name: swift
    description: Swift compiler
  - name: xcodebuild
    description: Xcode build
  - name: swift*
    description: All Swift tools
""")
        config = load_project_commands(project_dir)
        if config and config["version"] == 1 and len(config["commands"]) == 3:
            print("  PASS: Load valid YAML")
            passed += 1
        else:
            print("  FAIL: Load valid YAML")
            print(f"         Got: {config}")
            failed += 1

        # Test 2: Missing file returns None
        (project_dir / ".autoforge" / "allowed_commands.yaml").unlink()
        config = load_project_commands(project_dir)
        if config is None:
            print("  PASS: Missing file returns None")
            passed += 1
        else:
            print("  FAIL: Missing file returns None")
            print(f"         Got: {config}")
            failed += 1

        # Test 3: Invalid YAML returns None
        config_path.write_text("invalid: yaml: content:")
        config = load_project_commands(project_dir)
        if config is None:
            print("  PASS: Invalid YAML returns None")
            passed += 1
        else:
            print("  FAIL: Invalid YAML returns None")
            print(f"         Got: {config}")
            failed += 1

        # Test 4: Over limit (100 commands)
        commands = [f"  - name: cmd{i}\n    description: Command {i}" for i in range(101)]
        config_path.write_text("version: 1\ncommands:\n" + "\n".join(commands))
        config = load_project_commands(project_dir)
        if config is None:
            print("  PASS: Over limit rejected")
            passed += 1
        else:
            print("  FAIL: Over limit rejected")
            print(f"         Got: {config}")
            failed += 1

    return passed, failed


def test_command_validation():
    """Test project command validation."""
    print("\nTesting command validation:\n")
    passed = 0
    failed = 0

    # Test cases: (cmd_config, should_be_valid, description)
    test_cases = [
        # Valid commands
        ({"name": "swift", "description": "Swift compiler"}, True, "valid command"),
        ({"name": "swift"}, True, "command without description"),
        ({"name": "swift*", "description": "All Swift tools"}, True, "pattern command"),
        ({"name": "./scripts/build.sh", "description": "Build script"}, True, "local script"),

        # Invalid commands
        ({}, False, "missing name"),
        ({"description": "No name"}, False, "missing name field"),
        ({"name": ""}, False, "empty name"),
        ({"name": 123}, False, "non-string name"),

        # Security: Bare wildcard not allowed
        ({"name": "*"}, False, "bare wildcard rejected"),

        # Blocklisted commands
        ({"name": "sudo"}, False, "blocklisted sudo"),
        ({"name": "shutdown"}, False, "blocklisted shutdown"),
        ({"name": "dd"}, False, "blocklisted dd"),
    ]

    for cmd_config, should_be_valid, description in test_cases:
        valid, error = validate_project_command(cmd_config)
        if valid == should_be_valid:
            print(f"  PASS: {description}")
            passed += 1
        else:
            expected = "valid" if should_be_valid else "invalid"
            actual = "valid" if valid else "invalid"
            print(f"  FAIL: {description}")
            print(f"         Expected: {expected}, Got: {actual}")
            if error:
                print(f"         Error: {error}")
            failed += 1

    return passed, failed


def test_blocklist_enforcement():
    """Test blocklist enforcement in security hook."""
    print("\nTesting blocklist enforcement:\n")
    passed = 0
    failed = 0

    # All blocklisted commands should be rejected
    for cmd in ["sudo apt install", "shutdown now", "dd if=/dev/zero", "aws s3 ls"]:
        input_data = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        result = asyncio.run(bash_security_hook(input_data))
        if result.get("decision") == "block":
            print(f"  PASS: Blocked {cmd.split()[0]}")
            passed += 1
        else:
            print(f"  FAIL: Should block {cmd.split()[0]}")
            failed += 1

    return passed, failed


def test_project_commands():
    """Test project-specific commands in security hook."""
    print("\nTesting project-specific commands:\n")
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        autoforge_dir = project_dir / ".autoforge"
        autoforge_dir.mkdir()

        # Create a config with Swift commands
        config_path = autoforge_dir / "allowed_commands.yaml"
        config_path.write_text("""version: 1
commands:
  - name: swift
    description: Swift compiler
  - name: xcodebuild
    description: Xcode build
  - name: swift*
    description: All Swift tools
""")

        # Test 1: Project command should be allowed
        input_data = {"tool_name": "Bash", "tool_input": {"command": "swift --version"}}
        context = {"project_dir": str(project_dir)}
        result = asyncio.run(bash_security_hook(input_data, context=context))
        if result.get("decision") != "block":
            print("  PASS: Project command 'swift' allowed")
            passed += 1
        else:
            print("  FAIL: Project command 'swift' should be allowed")
            print(f"         Reason: {result.get('reason')}")
            failed += 1

        # Test 2: Pattern match should work
        input_data = {"tool_name": "Bash", "tool_input": {"command": "swiftlint"}}
        result = asyncio.run(bash_security_hook(input_data, context=context))
        if result.get("decision") != "block":
            print("  PASS: Pattern 'swift*' matches 'swiftlint'")
            passed += 1
        else:
            print("  FAIL: Pattern 'swift*' should match 'swiftlint'")
            print(f"         Reason: {result.get('reason')}")
            failed += 1

        # Test 3: Non-allowed command should be blocked
        input_data = {"tool_name": "Bash", "tool_input": {"command": "rustc"}}
        result = asyncio.run(bash_security_hook(input_data, context=context))
        if result.get("decision") == "block":
            print("  PASS: Non-allowed command 'rustc' blocked")
            passed += 1
        else:
            print("  FAIL: Non-allowed command 'rustc' should be blocked")
            failed += 1

        # Test 4: Empty command name is rejected
        config_path.write_text("""version: 1
commands:
  - name: ""
    description: Empty name should be rejected
""")
        result = load_project_commands(project_dir)
        if result is None:
            print("  PASS: Empty command name rejected in project config")
            passed += 1
        else:
            print("  FAIL: Empty command name should be rejected in project config")
            print(f"         Got: {result}")
            failed += 1

    return passed, failed


def test_org_config_loading():
    """Test organization-level config loading."""
    print("\nTesting org config loading:\n")
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        # Use temporary_home for cross-platform compatibility
        with temporary_home(tmpdir):
            org_dir = Path(tmpdir) / ".autoforge"
            org_dir.mkdir()
            org_config_path = org_dir / "config.yaml"

            # Test 1: Valid org config
            org_config_path.write_text("""version: 1
allowed_commands:
  - name: jq
    description: JSON processor
blocked_commands:
  - aws
  - kubectl
""")
            config = load_org_config()
            if config and config["version"] == 1:
                if len(config["allowed_commands"]) == 1 and len(config["blocked_commands"]) == 2:
                    print("  PASS: Load valid org config")
                    passed += 1
                else:
                    print("  FAIL: Load valid org config (wrong counts)")
                    failed += 1
            else:
                print("  FAIL: Load valid org config")
                print(f"         Got: {config}")
                failed += 1

            # Test 2: Missing file returns None
            org_config_path.unlink()
            config = load_org_config()
            if config is None:
                print("  PASS: Missing org config returns None")
                passed += 1
            else:
                print("  FAIL: Missing org config returns None")
                failed += 1

            # Test 3: Non-string command name is rejected
            org_config_path.write_text("""version: 1
allowed_commands:
  - name: 123
    description: Invalid numeric name
""")
            config = load_org_config()
            if config is None:
                print("  PASS: Non-string command name rejected")
                passed += 1
            else:
                print("  FAIL: Non-string command name rejected")
                print(f"         Got: {config}")
                failed += 1

            # Test 4: Empty command name is rejected
            org_config_path.write_text("""version: 1
allowed_commands:
  - name: ""
    description: Empty name
""")
            config = load_org_config()
            if config is None:
                print("  PASS: Empty command name rejected")
                passed += 1
            else:
                print("  FAIL: Empty command name rejected")
                print(f"         Got: {config}")
                failed += 1

            # Test 5: Whitespace-only command name is rejected
            org_config_path.write_text("""version: 1
allowed_commands:
  - name: "   "
    description: Whitespace name
""")
            config = load_org_config()
            if config is None:
                print("  PASS: Whitespace-only command name rejected")
                passed += 1
            else:
                print("  FAIL: Whitespace-only command name rejected")
                print(f"         Got: {config}")
                failed += 1

    return passed, failed


def test_hierarchy_resolution():
    """Test command hierarchy resolution."""
    print("\nTesting hierarchy resolution:\n")
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            # Use temporary_home for cross-platform compatibility
            with temporary_home(tmphome):
                org_dir = Path(tmphome) / ".autoforge"
                org_dir.mkdir()
                org_config_path = org_dir / "config.yaml"

                # Create org config with allowed and blocked commands
                org_config_path.write_text("""version: 1
allowed_commands:
  - name: jq
    description: JSON processor
  - name: python3
    description: Python interpreter
blocked_commands:
  - terraform
  - kubectl
""")

                project_dir = Path(tmpproject)
                project_autoforge = project_dir / ".autoforge"
                project_autoforge.mkdir()
                project_config = project_autoforge / "allowed_commands.yaml"

                # Create project config
                project_config.write_text("""version: 1
commands:
  - name: swift
    description: Swift compiler
""")

                # Test 1: Org allowed commands are included
                allowed, blocked = get_effective_commands(project_dir)
                if "jq" in allowed and "python3" in allowed:
                    print("  PASS: Org allowed commands included")
                    passed += 1
                else:
                    print("  FAIL: Org allowed commands included")
                    print(f"         jq in allowed: {'jq' in allowed}")
                    print(f"         python3 in allowed: {'python3' in allowed}")
                    failed += 1

                # Test 2: Org blocked commands are in blocklist
                if "terraform" in blocked and "kubectl" in blocked:
                    print("  PASS: Org blocked commands in blocklist")
                    passed += 1
                else:
                    print("  FAIL: Org blocked commands in blocklist")
                    failed += 1

                # Test 3: Project commands are included
                if "swift" in allowed:
                    print("  PASS: Project commands included")
                    passed += 1
                else:
                    print("  FAIL: Project commands included")
                    failed += 1

                # Test 4: Global commands are included
                if "npm" in allowed and "git" in allowed:
                    print("  PASS: Global commands included")
                    passed += 1
                else:
                    print("  FAIL: Global commands included")
                    failed += 1

                # Test 5: Hardcoded blocklist cannot be overridden
                if "sudo" in blocked and "shutdown" in blocked:
                    print("  PASS: Hardcoded blocklist enforced")
                    passed += 1
                else:
                    print("  FAIL: Hardcoded blocklist enforced")
                    failed += 1

    return passed, failed


def test_org_blocklist_enforcement():
    """Test that org-level blocked commands cannot be used."""
    print("\nTesting org blocklist enforcement:\n")
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            # Use temporary_home for cross-platform compatibility
            with temporary_home(tmphome):
                org_dir = Path(tmphome) / ".autoforge"
                org_dir.mkdir()
                org_config_path = org_dir / "config.yaml"

                # Create org config that blocks terraform
                org_config_path.write_text("""version: 1
blocked_commands:
  - terraform
""")

                project_dir = Path(tmpproject)
                project_autoforge = project_dir / ".autoforge"
                project_autoforge.mkdir()

                # Try to use terraform (should be blocked)
                input_data = {"tool_name": "Bash", "tool_input": {"command": "terraform apply"}}
                context = {"project_dir": str(project_dir)}
                result = asyncio.run(bash_security_hook(input_data, context=context))

                if result.get("decision") == "block":
                    print("  PASS: Org blocked command 'terraform' rejected")
                    passed += 1
                else:
                    print("  FAIL: Org blocked command 'terraform' should be rejected")
                    failed += 1

    return passed, failed


def test_pkill_extensibility():
    """Test that pkill processes can be extended via config."""
    print("\nTesting pkill process extensibility:\n")
    passed = 0
    failed = 0

    # Test 1: Default processes work without config
    allowed, reason = validate_pkill_command("pkill node")
    if allowed:
        print("  PASS: Default process 'node' allowed")
        passed += 1
    else:
        print(f"  FAIL: Default process 'node' should be allowed: {reason}")
        failed += 1

    # Test 2: Non-default process blocked without config
    allowed, reason = validate_pkill_command("pkill python")
    if not allowed:
        print("  PASS: Non-default process 'python' blocked without config")
        passed += 1
    else:
        print("  FAIL: Non-default process 'python' should be blocked without config")
        failed += 1

    # Test 3: Extra processes allowed when passed
    allowed, reason = validate_pkill_command("pkill python", extra_processes={"python"})
    if allowed:
        print("  PASS: Extra process 'python' allowed when configured")
        passed += 1
    else:
        print(f"  FAIL: Extra process 'python' should be allowed when configured: {reason}")
        failed += 1

    # Test 4: Default processes still work with extra processes
    allowed, reason = validate_pkill_command("pkill npm", extra_processes={"python"})
    if allowed:
        print("  PASS: Default process 'npm' still works with extra processes")
        passed += 1
    else:
        print(f"  FAIL: Default process should still work: {reason}")
        failed += 1

    # Test 5: Test get_effective_pkill_processes with org config
    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            with temporary_home(tmphome):
                org_dir = Path(tmphome) / ".autoforge"
                org_dir.mkdir()
                org_config_path = org_dir / "config.yaml"

                # Create org config with extra pkill processes
                org_config_path.write_text("""version: 1
pkill_processes:
  - python
  - uvicorn
""")

                project_dir = Path(tmpproject)
                processes = get_effective_pkill_processes(project_dir)

                # Should include defaults + org processes
                if "node" in processes and "python" in processes and "uvicorn" in processes:
                    print("  PASS: Org pkill_processes merged with defaults")
                    passed += 1
                else:
                    print(f"  FAIL: Expected node, python, uvicorn in {processes}")
                    failed += 1

    # Test 6: Test get_effective_pkill_processes with project config
    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            with temporary_home(tmphome):
                project_dir = Path(tmpproject)
                project_autoforge = project_dir / ".autoforge"
                project_autoforge.mkdir()
                project_config = project_autoforge / "allowed_commands.yaml"

                # Create project config with extra pkill processes
                project_config.write_text("""version: 1
commands: []
pkill_processes:
  - gunicorn
  - flask
""")

                processes = get_effective_pkill_processes(project_dir)

                # Should include defaults + project processes
                if "node" in processes and "gunicorn" in processes and "flask" in processes:
                    print("  PASS: Project pkill_processes merged with defaults")
                    passed += 1
                else:
                    print(f"  FAIL: Expected node, gunicorn, flask in {processes}")
                    failed += 1

    # Test 7: Integration test - pkill python blocked by default
    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            with temporary_home(tmphome):
                project_dir = Path(tmpproject)
                input_data = {"tool_name": "Bash", "tool_input": {"command": "pkill python"}}
                context = {"project_dir": str(project_dir)}
                result = asyncio.run(bash_security_hook(input_data, context=context))

                if result.get("decision") == "block":
                    print("  PASS: pkill python blocked without config")
                    passed += 1
                else:
                    print("  FAIL: pkill python should be blocked without config")
                    failed += 1

    # Test 8: Integration test - pkill python allowed with org config
    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            with temporary_home(tmphome):
                org_dir = Path(tmphome) / ".autoforge"
                org_dir.mkdir()
                org_config_path = org_dir / "config.yaml"

                org_config_path.write_text("""version: 1
pkill_processes:
  - python
""")

                project_dir = Path(tmpproject)
                input_data = {"tool_name": "Bash", "tool_input": {"command": "pkill python"}}
                context = {"project_dir": str(project_dir)}
                result = asyncio.run(bash_security_hook(input_data, context=context))

                if result.get("decision") != "block":
                    print("  PASS: pkill python allowed with org config")
                    passed += 1
                else:
                    print(f"  FAIL: pkill python should be allowed with org config: {result}")
                    failed += 1

    # Test 9: Regex metacharacters should be rejected in pkill_processes
    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            with temporary_home(tmphome):
                org_dir = Path(tmphome) / ".autoforge"
                org_dir.mkdir()
                org_config_path = org_dir / "config.yaml"

                # Try to register a regex pattern (should be rejected)
                org_config_path.write_text("""version: 1
pkill_processes:
  - ".*"
""")

                config = load_org_config()
                if config is None:
                    print("  PASS: Regex pattern '.*' rejected in pkill_processes")
                    passed += 1
                else:
                    print("  FAIL: Regex pattern '.*' should be rejected")
                    failed += 1

    # Test 10: Valid process names with dots/underscores/hyphens should be accepted
    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            with temporary_home(tmphome):
                org_dir = Path(tmphome) / ".autoforge"
                org_dir.mkdir()
                org_config_path = org_dir / "config.yaml"

                # Valid names with special chars
                org_config_path.write_text("""version: 1
pkill_processes:
  - my-app
  - app_server
  - node.js
""")

                config = load_org_config()
                if config is not None and config.get("pkill_processes") == ["my-app", "app_server", "node.js"]:
                    print("  PASS: Valid process names with dots/underscores/hyphens accepted")
                    passed += 1
                else:
                    print(f"  FAIL: Valid process names should be accepted: {config}")
                    failed += 1

    # Test 11: Names with spaces should be rejected
    with tempfile.TemporaryDirectory() as tmphome:
        with tempfile.TemporaryDirectory() as tmpproject:
            with temporary_home(tmphome):
                org_dir = Path(tmphome) / ".autoforge"
                org_dir.mkdir()
                org_config_path = org_dir / "config.yaml"

                org_config_path.write_text("""version: 1
pkill_processes:
  - "my app"
""")

                config = load_org_config()
                if config is None:
                    print("  PASS: Process name with space rejected")
                    passed += 1
                else:
                    print("  FAIL: Process name with space should be rejected")
                    failed += 1

    # Test 12: Multiple patterns - all must be allowed (BSD behavior)
    # On BSD, "pkill node sshd" would kill both, so we must validate all patterns
    allowed, reason = validate_pkill_command("pkill node npm")
    if allowed:
        print("  PASS: Multiple allowed patterns accepted")
        passed += 1
    else:
        print(f"  FAIL: Multiple allowed patterns should be accepted: {reason}")
        failed += 1

    # Test 13: Multiple patterns - block if any is disallowed
    allowed, reason = validate_pkill_command("pkill node sshd")
    if not allowed:
        print("  PASS: Multiple patterns blocked when one is disallowed")
        passed += 1
    else:
        print("  FAIL: Should block when any pattern is disallowed")
        failed += 1

    # Test 14: Multiple patterns - only first allowed, second disallowed
    allowed, reason = validate_pkill_command("pkill npm python")
    if not allowed:
        print("  PASS: Multiple patterns blocked (first allowed, second not)")
        passed += 1
    else:
        print("  FAIL: Should block when second pattern is disallowed")
        failed += 1

    return passed, failed


def test_playwright_cli_validation():
    """Test playwright-cli subcommand validation."""
    print("\nTesting playwright-cli validation:\n")
    passed = 0
    failed = 0

    # Test cases: (command, should_be_allowed, description)
    test_cases = [
        # Allowed cases
        ("playwright-cli screenshot", True, "screenshot allowed"),
        ("playwright-cli snapshot", True, "snapshot allowed"),
        ("playwright-cli click e5", True, "click with ref"),
        ("playwright-cli open http://localhost:3000", True, "open URL"),
        ("playwright-cli -s=agent-1 click e5", True, "session flag with click"),
        ("playwright-cli close", True, "close browser"),
        ("playwright-cli goto http://localhost:3000/page", True, "goto URL"),
        ("playwright-cli fill e3 'test value'", True, "fill form field"),
        ("playwright-cli console", True, "console messages"),
        # Blocked cases
        ("playwright-cli run-code 'await page.evaluate(() => {})'", False, "run-code blocked"),
        ("playwright-cli eval 'document.title'", False, "eval blocked"),
        ("playwright-cli -s=test eval 'document.title'", False, "eval with session flag blocked"),
    ]

    for cmd, should_allow, description in test_cases:
        allowed, reason = validate_playwright_command(cmd)
        if allowed == should_allow:
            print(f"  PASS: {cmd!r} ({description})")
            passed += 1
        else:
            expected = "allowed" if should_allow else "blocked"
            actual = "allowed" if allowed else "blocked"
            print(f"  FAIL: {cmd!r} ({description})")
            print(f"         Expected: {expected}, Got: {actual}")
            if reason:
                print(f"         Reason: {reason}")
            failed += 1

    # Integration test: verify through the security hook
    print("\n  Integration tests (via security hook):\n")

    # playwright-cli screenshot should be allowed
    input_data = {"tool_name": "Bash", "tool_input": {"command": "playwright-cli screenshot"}}
    result = asyncio.run(bash_security_hook(input_data))
    if result.get("decision") != "block":
        print("  PASS: playwright-cli screenshot allowed via hook")
        passed += 1
    else:
        print(f"  FAIL: playwright-cli screenshot should be allowed: {result.get('reason')}")
        failed += 1

    # playwright-cli run-code should be blocked
    input_data = {"tool_name": "Bash", "tool_input": {"command": "playwright-cli run-code 'code'"}}
    result = asyncio.run(bash_security_hook(input_data))
    if result.get("decision") == "block":
        print("  PASS: playwright-cli run-code blocked via hook")
        passed += 1
    else:
        print("  FAIL: playwright-cli run-code should be blocked via hook")
        failed += 1

    return passed, failed


def main():
    print("=" * 70)
    print("  SECURITY HOOK TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    # Test command extraction
    ext_passed, ext_failed = test_extract_commands()
    passed += ext_passed
    failed += ext_failed

    # Test chmod validation
    chmod_passed, chmod_failed = test_validate_chmod()
    passed += chmod_passed
    failed += chmod_failed

    # Test init.sh validation
    init_passed, init_failed = test_validate_init_script()
    passed += init_passed
    failed += init_failed

    # Test pattern matching (Phase 1)
    pattern_passed, pattern_failed = test_pattern_matching()
    passed += pattern_passed
    failed += pattern_failed

    # Test YAML loading (Phase 1)
    yaml_passed, yaml_failed = test_yaml_loading()
    passed += yaml_passed
    failed += yaml_failed

    # Test command validation (Phase 1)
    validation_passed, validation_failed = test_command_validation()
    passed += validation_passed
    failed += validation_failed

    # Test blocklist enforcement (Phase 1)
    blocklist_passed, blocklist_failed = test_blocklist_enforcement()
    passed += blocklist_passed
    failed += blocklist_failed

    # Test project commands (Phase 1)
    project_passed, project_failed = test_project_commands()
    passed += project_passed
    failed += project_failed

    # Test org config loading (Phase 2)
    org_loading_passed, org_loading_failed = test_org_config_loading()
    passed += org_loading_passed
    failed += org_loading_failed

    # Test hierarchy resolution (Phase 2)
    hierarchy_passed, hierarchy_failed = test_hierarchy_resolution()
    passed += hierarchy_passed
    failed += hierarchy_failed

    # Test org blocklist enforcement (Phase 2)
    org_block_passed, org_block_failed = test_org_blocklist_enforcement()
    passed += org_block_passed
    failed += org_block_failed

    # Test pkill process extensibility
    pkill_passed, pkill_failed = test_pkill_extensibility()
    passed += pkill_passed
    failed += pkill_failed

    # Test playwright-cli validation
    pw_passed, pw_failed = test_playwright_cli_validation()
    passed += pw_passed
    failed += pw_failed

    # Commands that SHOULD be blocked
    # Note: blocklisted commands (sudo, shutdown, dd, aws) are tested in
    # test_blocklist_enforcement(). chmod validation is tested in
    # test_validate_chmod(). init.sh validation is tested in
    # test_validate_init_script(). pkill validation is tested in
    # test_pkill_extensibility(). The entries below focus on scenarios
    # NOT covered by those dedicated tests.
    print("\nCommands that should be BLOCKED:\n")
    dangerous = [
        # Not in allowlist - dangerous system commands
        "reboot",
        # Not in allowlist - common commands excluded from minimal set
        "wget https://example.com",
        "python app.py",
        "killall node",
        # pkill with non-dev processes (pkill python tested in test_pkill_extensibility)
        "pkill bash",
        "pkill chrome",
        # Shell injection attempts
        "$(echo pkill) node",
        'eval "pkill node"',
        # playwright-cli dangerous subcommands
        "playwright-cli run-code 'await page.goto(\"http://evil.com\")'",
        "playwright-cli eval 'document.cookie'",
    ]

    for cmd in dangerous:
        if check_hook(cmd, should_block=True):
            passed += 1
        else:
            failed += 1

    # Commands that SHOULD be allowed
    # Note: chmod +x variants are tested in test_validate_chmod().
    # init.sh variants are tested in test_validate_init_script().
    # The combined "chmod +x init.sh && ./init.sh" below serves as the
    # integration test verifying the hook routes to both validators correctly.
    print("\nCommands that should be ALLOWED:\n")
    safe = [
        # File inspection
        "ls -la",
        "cat README.md",
        "head -100 file.txt",
        "tail -20 log.txt",
        "wc -l file.txt",
        "grep -r pattern src/",
        # File operations
        "cp file1.txt file2.txt",
        "mkdir newdir",
        "mkdir -p path/to/dir",
        "touch file.txt",
        "rm -rf temp/",
        "mv old.txt new.txt",
        # Directory
        "pwd",
        # Output
        "echo hello",
        # Node.js development
        "npm install",
        "npm run build",
        "node server.js",
        # Version control
        "git status",
        "git commit -m 'test'",
        "git add . && git commit -m 'msg'",
        # Process management
        "ps aux",
        "lsof -i :3000",
        "sleep 2",
        "kill 12345",
        # Allowed pkill patterns for dev servers
        "pkill node",
        "pkill npm",
        "pkill -f node",
        "pkill -f 'node server.js'",
        "pkill vite",
        # Network/API testing
        "curl https://example.com",
        # Shell scripts (bash/sh in allowlist)
        "bash script.sh",
        "sh script.sh",
        'bash -c "echo hello"',
        # Chained commands
        "npm install && npm run build",
        "ls | grep test",
        # Full paths
        "/usr/local/bin/node app.js",
        # Combined chmod and init.sh (integration test for both validators)
        "chmod +x init.sh && ./init.sh",
        # Playwright CLI allowed commands
        "playwright-cli open http://localhost:3000",
        "playwright-cli screenshot",
        "playwright-cli snapshot",
        "playwright-cli click e5",
        "playwright-cli -s=agent-1 close",
    ]

    for cmd in safe:
        if check_hook(cmd, should_block=False):
            passed += 1
        else:
            failed += 1

    # Summary
    print("\n" + "-" * 70)
    print(f"  Results: {passed} passed, {failed} failed")
    print("-" * 70)

    if failed == 0:
        print("\n  ALL TESTS PASSED")
        return 0
    else:
        print(f"\n  {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
