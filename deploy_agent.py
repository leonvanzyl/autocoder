"""
Deploy Agent
============

Agent for managing deployment workflows across different environments.
Supports various deployment strategies and provides deployment status tracking.
"""

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import JSON

logger = logging.getLogger(__name__)

Base = declarative_base()


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class DeploymentStatus(str, Enum):
    """Deployment status states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class DeploymentEnvironment(str, Enum):
    """Deployment target environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    PREVIEW = "preview"


class DeploymentStrategy(str, Enum):
    """Deployment strategies."""

    DIRECT = "direct"  # Direct deployment
    BLUE_GREEN = "blue_green"  # Blue-green deployment
    CANARY = "canary"  # Canary deployment
    ROLLING = "rolling"  # Rolling update


@dataclass
class DeploymentConfig:
    """Configuration for a deployment."""

    environment: DeploymentEnvironment
    strategy: DeploymentStrategy = DeploymentStrategy.DIRECT
    branch: str = "main"
    commit_sha: str | None = None
    deploy_command: str | None = None
    pre_deploy_checks: list[str] = field(default_factory=list)
    post_deploy_checks: list[str] = field(default_factory=list)
    rollback_command: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""

    success: bool
    deployment_id: int | None = None
    message: str = ""
    duration_ms: int = 0
    logs: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)


# =============================================================================
# Database Models
# =============================================================================


class Deployment(Base):
    """
    Tracks deployment history and status.
    """

    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, index=True)
    environment = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default=DeploymentStatus.PENDING.value)
    strategy = Column(String(50), nullable=False, default=DeploymentStrategy.DIRECT.value)

    # Git information
    branch = Column(String(255), nullable=True)
    commit_sha = Column(String(64), nullable=True)
    commit_message = Column(Text, nullable=True)

    # Deployment details
    deploy_url = Column(String(500), nullable=True)
    logs = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Metrics
    duration_ms = Column(Integer, nullable=True)
    artifact_count = Column(Integer, nullable=True, default=0)

    # Deployment metadata
    deployment_metadata = Column(JSON, nullable=True)

    # Timestamps
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "projectName": self.project_name,
            "environment": self.environment,
            "status": self.status,
            "strategy": self.strategy,
            "branch": self.branch,
            "commitSha": self.commit_sha,
            "commitMessage": self.commit_message,
            "deployUrl": self.deploy_url,
            "logs": self.logs,
            "errorMessage": self.error_message,
            "durationMs": self.duration_ms,
            "artifactCount": self.artifact_count,
            "metadata": self.deployment_metadata,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class DeploymentCheck(Base):
    """
    Tracks pre/post deployment checks.
    """

    __tablename__ = "deployment_checks"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, nullable=False, index=True)
    check_type = Column(String(50), nullable=False)  # 'pre' or 'post'
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    output = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "deploymentId": self.deployment_id,
            "checkType": self.check_type,
            "name": self.name,
            "status": self.status,
            "output": self.output,
            "durationMs": self.duration_ms,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# Deploy Agent
# =============================================================================


class DeployAgent:
    """
    Agent for managing deployment workflows.

    Provides:
    - Multi-environment deployment support
    - Pre/post deployment checks
    - Deployment history tracking
    - Rollback capabilities
    - Integration with CI/CD systems
    """

    def __init__(self, project_path: Path):
        """
        Initialize the deploy agent.

        Args:
            project_path: Path to the project directory
        """
        self.project_path = project_path
        self.db_path = project_path / "deployments.db"

        # Create engine and tables
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _get_git_info(self) -> tuple[str | None, str | None, str | None]:
        """Get current git branch, commit SHA, and message."""
        try:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

            # Get commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            sha = sha_result.stdout.strip()[:12] if sha_result.returncode == 0 else None

            # Get commit message
            msg_result = subprocess.run(
                ["git", "log", "-1", "--format=%s"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            message = msg_result.stdout.strip() if msg_result.returncode == 0 else None

            return branch, sha, message
        except Exception as e:
            logger.warning(f"Failed to get git info: {e}")
            return None, None, None

    def _run_command(self, command: str, timeout: int = 300) -> tuple[bool, str, int]:
        """
        Run a shell command and return result.

        Args:
            command: Command to run
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, output, duration_ms)
        """
        start_time = datetime.now(timezone.utc)
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            output = result.stdout + result.stderr
            return result.returncode == 0, output, duration_ms
        except subprocess.TimeoutExpired:
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return False, f"Command timed out after {timeout} seconds", duration_ms
        except Exception as e:
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return False, str(e), duration_ms

    def start_deployment(
        self,
        config: DeploymentConfig,
    ) -> DeploymentResult:
        """
        Start a new deployment.

        Args:
            config: Deployment configuration

        Returns:
            DeploymentResult with deployment status
        """
        start_time = datetime.now(timezone.utc)
        logs: list[str] = []

        with self.SessionLocal() as session:
            # Get git info
            branch, sha, message = self._get_git_info()
            if config.commit_sha:
                sha = config.commit_sha

            # Create deployment record
            deployment = Deployment(
                project_name=self.project_path.name,
                environment=config.environment.value,
                status=DeploymentStatus.IN_PROGRESS.value,
                strategy=config.strategy.value,
                branch=branch or config.branch,
                commit_sha=sha,
                commit_message=message,
                deployment_metadata=config.metadata,
            )
            session.add(deployment)
            session.commit()

            deployment_id = deployment.id
            logs.append(f"[{_utc_now().isoformat()}] Deployment #{deployment_id} started")
            logs.append(f"[{_utc_now().isoformat()}] Environment: {config.environment.value}")
            logs.append(f"[{_utc_now().isoformat()}] Strategy: {config.strategy.value}")
            logs.append(f"[{_utc_now().isoformat()}] Branch: {branch}, Commit: {sha}")

            # Run pre-deployment checks
            for check_cmd in config.pre_deploy_checks:
                logs.append(f"[{_utc_now().isoformat()}] Running pre-check: {check_cmd}")

                check_record = DeploymentCheck(
                    deployment_id=deployment_id,
                    check_type="pre",
                    name=check_cmd,
                    status="running",
                )
                session.add(check_record)
                session.commit()

                success, output, duration = self._run_command(check_cmd)
                check_record.status = "passed" if success else "failed"
                check_record.output = output
                check_record.duration_ms = duration
                session.commit()

                if not success:
                    logs.append(f"[{_utc_now().isoformat()}] Pre-check failed: {check_cmd}")
                    deployment.status = DeploymentStatus.FAILED.value
                    deployment.error_message = f"Pre-deployment check failed: {check_cmd}"
                    deployment.logs = "\n".join(logs)
                    deployment.completed_at = _utc_now()
                    session.commit()

                    return DeploymentResult(
                        success=False,
                        deployment_id=deployment_id,
                        message=f"Pre-deployment check failed: {check_cmd}",
                        logs=logs,
                    )

            # Run deployment command
            if config.deploy_command:
                logs.append(f"[{_utc_now().isoformat()}] Running deployment: {config.deploy_command}")
                success, output, duration = self._run_command(config.deploy_command)
                logs.append(output)

                if not success:
                    logs.append(f"[{_utc_now().isoformat()}] Deployment command failed")
                    deployment.status = DeploymentStatus.FAILED.value
                    deployment.error_message = output
                    deployment.logs = "\n".join(logs)
                    deployment.completed_at = _utc_now()
                    deployment.duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    session.commit()

                    return DeploymentResult(
                        success=False,
                        deployment_id=deployment_id,
                        message="Deployment command failed",
                        duration_ms=duration,
                        logs=logs,
                    )

            # Run post-deployment checks
            for check_cmd in config.post_deploy_checks:
                logs.append(f"[{_utc_now().isoformat()}] Running post-check: {check_cmd}")

                check_record = DeploymentCheck(
                    deployment_id=deployment_id,
                    check_type="post",
                    name=check_cmd,
                    status="running",
                )
                session.add(check_record)
                session.commit()

                success, output, duration = self._run_command(check_cmd)
                check_record.status = "passed" if success else "failed"
                check_record.output = output
                check_record.duration_ms = duration
                session.commit()

                if not success:
                    logs.append(f"[{_utc_now().isoformat()}] Post-check failed: {check_cmd}")
                    # Post-check failures don't fail deployment but are logged

            # Update deployment status
            total_duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            deployment.status = DeploymentStatus.SUCCESS.value
            deployment.logs = "\n".join(logs)
            deployment.completed_at = _utc_now()
            deployment.duration_ms = total_duration
            session.commit()

            logs.append(f"[{_utc_now().isoformat()}] Deployment #{deployment_id} completed successfully")

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message=f"Deployment #{deployment_id} completed successfully",
                duration_ms=total_duration,
                logs=logs,
            )

    def rollback(self, deployment_id: int) -> DeploymentResult:
        """
        Rollback a deployment.

        Args:
            deployment_id: ID of the deployment to rollback

        Returns:
            DeploymentResult with rollback status
        """
        with self.SessionLocal() as session:
            deployment = session.query(Deployment).filter_by(id=deployment_id).first()

            if not deployment:
                return DeploymentResult(
                    success=False,
                    message=f"Deployment #{deployment_id} not found",
                )

            if deployment.status == DeploymentStatus.ROLLED_BACK.value:
                return DeploymentResult(
                    success=False,
                    deployment_id=deployment_id,
                    message="Deployment already rolled back",
                )

            # Check for rollback command in metadata
            rollback_cmd = deployment.deployment_metadata.get("rollback_command") if deployment.deployment_metadata else None

            if rollback_cmd:
                success, output, duration = self._run_command(rollback_cmd)
                if not success:
                    return DeploymentResult(
                        success=False,
                        deployment_id=deployment_id,
                        message=f"Rollback failed: {output}",
                        duration_ms=duration,
                    )

            deployment.status = DeploymentStatus.ROLLED_BACK.value
            session.commit()

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message=f"Deployment #{deployment_id} rolled back successfully",
            )

    def get_deployment(self, deployment_id: int) -> dict[str, Any] | None:
        """Get deployment by ID."""
        with self.SessionLocal() as session:
            deployment = session.query(Deployment).filter_by(id=deployment_id).first()
            return deployment.to_dict() if deployment else None

    def list_deployments(
        self,
        environment: DeploymentEnvironment | None = None,
        status: DeploymentStatus | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        List deployments with optional filters.

        Args:
            environment: Filter by environment
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of deployment dictionaries
        """
        with self.SessionLocal() as session:
            query = session.query(Deployment).filter_by(project_name=self.project_path.name)

            if environment:
                query = query.filter_by(environment=environment.value)
            if status:
                query = query.filter_by(status=status.value)

            query = query.order_by(Deployment.created_at.desc()).limit(limit)
            return [d.to_dict() for d in query.all()]

    def get_deployment_checks(self, deployment_id: int) -> list[dict[str, Any]]:
        """Get checks for a deployment."""
        with self.SessionLocal() as session:
            checks = session.query(DeploymentCheck).filter_by(deployment_id=deployment_id).all()
            return [c.to_dict() for c in checks]

    def cancel_deployment(self, deployment_id: int) -> DeploymentResult:
        """
        Cancel a pending or in-progress deployment.

        Args:
            deployment_id: ID of the deployment to cancel

        Returns:
            DeploymentResult with cancellation status
        """
        with self.SessionLocal() as session:
            deployment = session.query(Deployment).filter_by(id=deployment_id).first()

            if not deployment:
                return DeploymentResult(
                    success=False,
                    message=f"Deployment #{deployment_id} not found",
                )

            if deployment.status not in [DeploymentStatus.PENDING.value, DeploymentStatus.IN_PROGRESS.value]:
                return DeploymentResult(
                    success=False,
                    deployment_id=deployment_id,
                    message=f"Cannot cancel deployment in '{deployment.status}' status",
                )

            deployment.status = DeploymentStatus.CANCELLED.value
            deployment.completed_at = _utc_now()
            session.commit()

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message=f"Deployment #{deployment_id} cancelled",
            )

    def get_environment_status(self) -> dict[str, Any]:
        """
        Get current status of all environments.

        Returns:
            Dictionary with environment statuses
        """
        with self.SessionLocal() as session:
            result = {}
            for env in DeploymentEnvironment:
                # Get latest deployment for each environment
                latest = (
                    session.query(Deployment)
                    .filter_by(project_name=self.project_path.name, environment=env.value)
                    .order_by(Deployment.created_at.desc())
                    .first()
                )

                result[env.value] = {
                    "environment": env.value,
                    "latestDeployment": latest.to_dict() if latest else None,
                    "status": latest.status if latest else "never_deployed",
                }

            return result
