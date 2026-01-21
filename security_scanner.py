"""
Security Scanner Module
=======================

Detect vulnerabilities in generated code and dependencies.

Features:
- Dependency scanning (npm audit, pip-audit/safety)
- Secret detection (API keys, passwords, tokens)
- Code vulnerability patterns (SQL injection, XSS, command injection)
- OWASP Top 10 pattern matching

Integration:
- Can be run standalone or as part of quality gates
- Results stored in project's .autocoder/security-reports/
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(str, Enum):
    """Vulnerability severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(str, Enum):
    """Types of vulnerabilities detected."""

    DEPENDENCY = "dependency"
    SECRET = "secret"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    INSECURE_CRYPTO = "insecure_crypto"
    HARDCODED_CREDENTIAL = "hardcoded_credential"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    OTHER = "other"


@dataclass
class Vulnerability:
    """A detected vulnerability."""

    type: VulnerabilityType
    severity: Severity
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    recommendation: Optional[str] = None
    cwe_id: Optional[str] = None
    package_name: Optional[str] = None
    package_version: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "type": self.type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
        }
        if self.file_path:
            result["file_path"] = self.file_path
        if self.line_number:
            result["line_number"] = self.line_number
        if self.code_snippet:
            result["code_snippet"] = self.code_snippet
        if self.recommendation:
            result["recommendation"] = self.recommendation
        if self.cwe_id:
            result["cwe_id"] = self.cwe_id
        if self.package_name:
            result["package_name"] = self.package_name
        if self.package_version:
            result["package_version"] = self.package_version
        return result


@dataclass
class ScanResult:
    """Result of a security scan."""

    project_dir: str
    scan_time: str
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    scans_run: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_dir": self.project_dir,
            "scan_time": self.scan_time,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "summary": self.summary,
            "scans_run": self.scans_run,
            "total_issues": len(self.vulnerabilities),
            "by_severity": {
                "critical": len([v for v in self.vulnerabilities if v.severity == Severity.CRITICAL]),
                "high": len([v for v in self.vulnerabilities if v.severity == Severity.HIGH]),
                "medium": len([v for v in self.vulnerabilities if v.severity == Severity.MEDIUM]),
                "low": len([v for v in self.vulnerabilities if v.severity == Severity.LOW]),
                "info": len([v for v in self.vulnerabilities if v.severity == Severity.INFO]),
            },
        }


# ============================================================================
# Secret Patterns
# ============================================================================

SECRET_PATTERNS = [
    # API Keys
    (
        r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
        "API Key Detected",
        Severity.HIGH,
        "CWE-798",
    ),
    # AWS Keys
    (
        r'(?i)(AKIA[0-9A-Z]{16})',
        "AWS Access Key ID",
        Severity.CRITICAL,
        "CWE-798",
    ),
    (
        r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?',
        "AWS Secret Access Key",
        Severity.CRITICAL,
        "CWE-798",
    ),
    # Private Keys
    (
        r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----',
        "Private Key Detected",
        Severity.CRITICAL,
        "CWE-321",
    ),
    # Passwords
    (
        r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']',
        "Hardcoded Password",
        Severity.HIGH,
        "CWE-798",
    ),
    # Generic Secrets
    (
        r'(?i)(secret|token|auth)[_-]?(key|token)?\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
        "Secret/Token Detected",
        Severity.HIGH,
        "CWE-798",
    ),
    # Database Connection Strings
    (
        r'(?i)(mongodb|postgres|mysql|redis)://[^"\'\s]+:[^"\'\s]+@',
        "Database Connection String with Credentials",
        Severity.HIGH,
        "CWE-798",
    ),
    # JWT Tokens
    (
        r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
        "JWT Token Detected",
        Severity.MEDIUM,
        "CWE-200",
    ),
    # GitHub Tokens
    (
        r'gh[pousr]_[A-Za-z0-9_]{36,}',
        "GitHub Token Detected",
        Severity.CRITICAL,
        "CWE-798",
    ),
    # Slack Tokens
    (
        r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*',
        "Slack Token Detected",
        Severity.HIGH,
        "CWE-798",
    ),
]

# ============================================================================
# Code Vulnerability Patterns
# ============================================================================

CODE_PATTERNS = [
    # SQL Injection
    (
        r'(?i)execute\s*\(\s*["\'].*\%.*["\'].*%',
        "Potential SQL Injection (string formatting)",
        VulnerabilityType.SQL_INJECTION,
        Severity.HIGH,
        "CWE-89",
        "Use parameterized queries instead of string formatting",
    ),
    (
        r'(?i)(cursor\.execute|db\.execute|connection\.execute)\s*\(\s*f["\']',
        "Potential SQL Injection (f-string)",
        VulnerabilityType.SQL_INJECTION,
        Severity.HIGH,
        "CWE-89",
        "Use parameterized queries instead of f-strings",
    ),
    (
        r'(?i)query\s*=\s*["\']SELECT.*\+',
        "Potential SQL Injection (string concatenation)",
        VulnerabilityType.SQL_INJECTION,
        Severity.HIGH,
        "CWE-89",
        "Use parameterized queries instead of string concatenation",
    ),
    # XSS
    (
        r'(?i)innerHTML\s*=\s*[^"\']*\+',
        "Potential XSS (innerHTML with concatenation)",
        VulnerabilityType.XSS,
        Severity.HIGH,
        "CWE-79",
        "Use textContent or sanitize HTML before setting innerHTML",
    ),
    (
        r'(?i)document\.write\s*\(',
        "Potential XSS (document.write)",
        VulnerabilityType.XSS,
        Severity.MEDIUM,
        "CWE-79",
        "Avoid document.write, use DOM manipulation instead",
    ),
    (
        r'(?i)dangerouslySetInnerHTML',
        "React dangerouslySetInnerHTML usage",
        VulnerabilityType.XSS,
        Severity.MEDIUM,
        "CWE-79",
        "Ensure content is properly sanitized before using dangerouslySetInnerHTML",
    ),
    # Command Injection
    (
        r'(?i)(subprocess\.call|subprocess\.run|os\.system|os\.popen)\s*\([^)]*\+',
        "Potential Command Injection (string concatenation)",
        VulnerabilityType.COMMAND_INJECTION,
        Severity.CRITICAL,
        "CWE-78",
        "Use subprocess with list arguments and avoid shell=True",
    ),
    (
        r'(?i)shell\s*=\s*True',
        "Subprocess with shell=True",
        VulnerabilityType.COMMAND_INJECTION,
        Severity.MEDIUM,
        "CWE-78",
        "Avoid shell=True, use list arguments instead",
    ),
    (
        r'(?i)exec\s*\(\s*[^"\']*\+',
        "Potential Code Injection (exec with concatenation)",
        VulnerabilityType.COMMAND_INJECTION,
        Severity.CRITICAL,
        "CWE-94",
        "Avoid using exec with user-controlled input",
    ),
    (
        r'(?i)eval\s*\(\s*[^"\']*\+',
        "Potential Code Injection (eval with concatenation)",
        VulnerabilityType.COMMAND_INJECTION,
        Severity.CRITICAL,
        "CWE-94",
        "Avoid using eval with user-controlled input",
    ),
    # Path Traversal
    (
        r'(?i)(open|read|write)\s*\([^)]*\+[^)]*\)',
        "Potential Path Traversal (file operation with concatenation)",
        VulnerabilityType.PATH_TRAVERSAL,
        Severity.MEDIUM,
        "CWE-22",
        "Validate and sanitize file paths before use",
    ),
    # Insecure Crypto
    (
        r'(?i)(md5|sha1)\s*\(',
        "Weak Cryptographic Hash (MD5/SHA1)",
        VulnerabilityType.INSECURE_CRYPTO,
        Severity.LOW,
        "CWE-328",
        "Use SHA-256 or stronger for security-sensitive operations",
    ),
    (
        r'(?i)random\.random\s*\(',
        "Insecure Random Number Generator",
        VulnerabilityType.INSECURE_CRYPTO,
        Severity.LOW,
        "CWE-330",
        "Use secrets module for security-sensitive random values",
    ),
    # Sensitive Data
    (
        r'(?i)console\.(log|info|debug)\s*\([^)]*password',
        "Password logged to console",
        VulnerabilityType.SENSITIVE_DATA_EXPOSURE,
        Severity.MEDIUM,
        "CWE-532",
        "Remove sensitive data from log statements",
    ),
    (
        r'(?i)print\s*\([^)]*password',
        "Password printed to output",
        VulnerabilityType.SENSITIVE_DATA_EXPOSURE,
        Severity.MEDIUM,
        "CWE-532",
        "Remove sensitive data from print statements",
    ),
]


class SecurityScanner:
    """
    Security scanner for detecting vulnerabilities in code and dependencies.

    Usage:
        scanner = SecurityScanner(project_dir)
        result = scanner.scan()
        print(f"Found {len(result.vulnerabilities)} issues")
    """

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)

    def scan(
        self,
        scan_dependencies: bool = True,
        scan_secrets: bool = True,
        scan_code: bool = True,
        save_report: bool = True,
    ) -> ScanResult:
        """
        Run security scan on the project.

        Args:
            scan_dependencies: Run npm audit / pip-audit
            scan_secrets: Scan for hardcoded secrets
            scan_code: Scan for code vulnerabilities
            save_report: Save report to .autocoder/security-reports/

        Returns:
            ScanResult with all findings
        """
        result = ScanResult(
            project_dir=str(self.project_dir),
            scan_time=datetime.utcnow().isoformat() + "Z",
        )

        if scan_dependencies:
            self._scan_dependencies(result)

        if scan_secrets:
            self._scan_secrets(result)

        if scan_code:
            self._scan_code_patterns(result)

        # Generate summary
        result.summary = {
            "total_issues": len(result.vulnerabilities),
            "critical": len([v for v in result.vulnerabilities if v.severity == Severity.CRITICAL]),
            "high": len([v for v in result.vulnerabilities if v.severity == Severity.HIGH]),
            "medium": len([v for v in result.vulnerabilities if v.severity == Severity.MEDIUM]),
            "low": len([v for v in result.vulnerabilities if v.severity == Severity.LOW]),
            "has_critical_or_high": any(
                v.severity in (Severity.CRITICAL, Severity.HIGH)
                for v in result.vulnerabilities
            ),
        }

        if save_report:
            self._save_report(result)

        return result

    def _scan_dependencies(self, result: ScanResult) -> None:
        """Scan dependencies for known vulnerabilities."""
        # Check for npm
        if (self.project_dir / "package.json").exists():
            self._run_npm_audit(result)

        # Check for Python
        if (self.project_dir / "requirements.txt").exists() or (
            self.project_dir / "pyproject.toml"
        ).exists():
            self._run_pip_audit(result)

    def _run_npm_audit(self, result: ScanResult) -> None:
        """Run npm audit and parse results."""
        result.scans_run.append("npm_audit")

        try:
            proc = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if proc.stdout:
                try:
                    audit_data = json.loads(proc.stdout)

                    # Parse vulnerabilities from npm audit output
                    vulns = audit_data.get("vulnerabilities", {})
                    for pkg_name, pkg_info in vulns.items():
                        severity_str = pkg_info.get("severity", "medium")
                        severity_map = {
                            "critical": Severity.CRITICAL,
                            "high": Severity.HIGH,
                            "moderate": Severity.MEDIUM,
                            "low": Severity.LOW,
                            "info": Severity.INFO,
                        }
                        severity = severity_map.get(severity_str, Severity.MEDIUM)

                        via = pkg_info.get("via", [])
                        description = ""
                        if via and isinstance(via[0], dict):
                            description = via[0].get("title", "")
                        elif via and isinstance(via[0], str):
                            description = f"Vulnerable through {via[0]}"

                        result.vulnerabilities.append(
                            Vulnerability(
                                type=VulnerabilityType.DEPENDENCY,
                                severity=severity,
                                title=f"Vulnerable dependency: {pkg_name}",
                                description=description or "Known vulnerability in package",
                                package_name=pkg_name,
                                package_version=pkg_info.get("range"),
                                recommendation=f"Run: npm update {pkg_name}",
                            )
                        )
                except json.JSONDecodeError:
                    pass

        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            pass

    def _run_pip_audit(self, result: ScanResult) -> None:
        """Run pip-audit and parse results."""
        result.scans_run.append("pip_audit")

        # Try pip-audit first
        pip_audit_path = shutil.which("pip-audit")
        if pip_audit_path:
            try:
                proc = subprocess.run(
                    ["pip-audit", "--format", "json", "-r", "requirements.txt"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if proc.stdout:
                    try:
                        vulns = json.loads(proc.stdout)
                        for vuln in vulns:
                            severity_map = {
                                "CRITICAL": Severity.CRITICAL,
                                "HIGH": Severity.HIGH,
                                "MEDIUM": Severity.MEDIUM,
                                "LOW": Severity.LOW,
                            }
                            result.vulnerabilities.append(
                                Vulnerability(
                                    type=VulnerabilityType.DEPENDENCY,
                                    severity=severity_map.get(
                                        vuln.get("severity", "MEDIUM"), Severity.MEDIUM
                                    ),
                                    title=f"Vulnerable dependency: {vuln.get('name')}",
                                    description=vuln.get("description", ""),
                                    package_name=vuln.get("name"),
                                    package_version=vuln.get("version"),
                                    cwe_id=vuln.get("id"),
                                    recommendation=f"Upgrade to {vuln.get('fix_versions', ['latest'])[0] if vuln.get('fix_versions') else 'latest'}",
                                )
                            )
                    except json.JSONDecodeError:
                        pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Try safety as fallback
        safety_path = shutil.which("safety")
        if safety_path and not any(
            v.type == VulnerabilityType.DEPENDENCY
            for v in result.vulnerabilities
            if v.package_name
        ):
            try:
                proc = subprocess.run(
                    ["safety", "check", "--json", "-r", "requirements.txt"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if proc.stdout:
                    try:
                        # Safety JSON format is different
                        safety_data = json.loads(proc.stdout)
                        # Parse safety output (format varies by version)
                        if isinstance(safety_data, list):
                            for item in safety_data:
                                if isinstance(item, list) and len(item) >= 4:
                                    result.vulnerabilities.append(
                                        Vulnerability(
                                            type=VulnerabilityType.DEPENDENCY,
                                            severity=Severity.MEDIUM,
                                            title=f"Vulnerable dependency: {item[0]}",
                                            description=item[3] if len(item) > 3 else "",
                                            package_name=item[0],
                                            package_version=item[1] if len(item) > 1 else None,
                                        )
                                    )
                    except json.JSONDecodeError:
                        pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

    def _scan_secrets(self, result: ScanResult) -> None:
        """Scan files for hardcoded secrets."""
        result.scans_run.append("secret_detection")

        # File extensions to scan
        extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx",
            ".json", ".yaml", ".yml", ".toml",
            ".env", ".env.local", ".env.example",
            ".sh", ".bash", ".zsh",
            ".md", ".txt",
        }

        # Directories to skip
        skip_dirs = {
            "node_modules", "venv", ".venv", "__pycache__",
            ".git", "dist", "build", ".next",
            "vendor", "packages",
        }

        for file_path in self._iter_files(extensions, skip_dirs):
            try:
                content = file_path.read_text(errors="ignore")
                lines = content.split("\n")

                for pattern, title, severity, cwe_id in SECRET_PATTERNS:
                    for i, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            # Skip if it looks like an example or placeholder
                            if any(
                                placeholder in line.lower()
                                for placeholder in [
                                    "example",
                                    "your_",
                                    "<your",
                                    "${",
                                    "{{",
                                    "xxx",
                                    "placeholder",
                                    "changeme",
                                ]
                            ):
                                continue

                            result.vulnerabilities.append(
                                Vulnerability(
                                    type=VulnerabilityType.SECRET,
                                    severity=severity,
                                    title=title,
                                    description=f"Possible hardcoded secret detected",
                                    file_path=str(file_path.relative_to(self.project_dir)),
                                    line_number=i,
                                    code_snippet=line[:100] + "..." if len(line) > 100 else line,
                                    cwe_id=cwe_id,
                                    recommendation="Move sensitive values to environment variables",
                                )
                            )
            except Exception:
                continue

    def _scan_code_patterns(self, result: ScanResult) -> None:
        """Scan code for vulnerability patterns."""
        result.scans_run.append("code_patterns")

        # File extensions to scan
        extensions = {".py", ".js", ".ts", ".tsx", ".jsx"}

        # Directories to skip
        skip_dirs = {
            "node_modules", "venv", ".venv", "__pycache__",
            ".git", "dist", "build", ".next",
        }

        for file_path in self._iter_files(extensions, skip_dirs):
            try:
                content = file_path.read_text(errors="ignore")
                lines = content.split("\n")

                for pattern, title, vuln_type, severity, cwe_id, recommendation in CODE_PATTERNS:
                    for i, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            result.vulnerabilities.append(
                                Vulnerability(
                                    type=vuln_type,
                                    severity=severity,
                                    title=title,
                                    description=f"Potential vulnerability pattern detected",
                                    file_path=str(file_path.relative_to(self.project_dir)),
                                    line_number=i,
                                    code_snippet=line.strip()[:100],
                                    cwe_id=cwe_id,
                                    recommendation=recommendation,
                                )
                            )
            except Exception:
                continue

    def _iter_files(
        self, extensions: set[str], skip_dirs: set[str]
    ):
        """Iterate over files with given extensions, skipping certain directories."""
        for root, dirs, files in os.walk(self.project_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in extensions or file in {".env", ".env.local", ".env.example"}:
                    yield file_path

    def _save_report(self, result: ScanResult) -> None:
        """Save scan report to file."""
        reports_dir = self.project_dir / ".autocoder" / "security-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"security_scan_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)


def scan_project(
    project_dir: Path,
    scan_dependencies: bool = True,
    scan_secrets: bool = True,
    scan_code: bool = True,
) -> ScanResult:
    """
    Convenience function to scan a project.

    Args:
        project_dir: Project directory
        scan_dependencies: Run dependency audit
        scan_secrets: Scan for secrets
        scan_code: Scan for code patterns

    Returns:
        ScanResult with findings
    """
    scanner = SecurityScanner(project_dir)
    return scanner.scan(
        scan_dependencies=scan_dependencies,
        scan_secrets=scan_secrets,
        scan_code=scan_code,
    )
