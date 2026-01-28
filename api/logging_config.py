"""
Logging Configuration
=====================

Centralized logging setup for the Autocoder system.

Usage:
    from api.logging_config import setup_logging, get_logger

    # At application startup
    setup_logging()

    # In modules
    logger = get_logger(__name__)
    logger.info("Message")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Default configuration
DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"
DEFAULT_LOG_FILE = "autocoder.log"
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_FILE_LOG_LEVEL = logging.DEBUG
DEFAULT_CONSOLE_LOG_LEVEL = logging.INFO
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

# Custom log format
FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONSOLE_FORMAT = "[%(levelname)s] %(message)s"
DEBUG_FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"

# Track if logging has been configured
_logging_configured = False


def setup_logging(
    log_dir: Optional[Path] = None,
    log_file: str = DEFAULT_LOG_FILE,
    console_level: int = DEFAULT_CONSOLE_LOG_LEVEL,
    file_level: int = DEFAULT_FILE_LOG_LEVEL,
    root_level: int = DEFAULT_LOG_LEVEL,
) -> None:
    """
    Configure logging for the Autocoder application.

    Sets up:
    - RotatingFileHandler for detailed logs (DEBUG level)
    - StreamHandler for console output (INFO level by default)

    Args:
        log_dir: Directory for log files (default: ./logs/)
        log_file: Name of the log file
        console_level: Log level for console output
        file_level: Log level for file output
        root_level: Root logger level
    """
    global _logging_configured

    if _logging_configured:
        return

    # Use default log directory if not specified
    if log_dir is None:
        log_dir = DEFAULT_LOG_DIR

    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_file

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(root_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(DEBUG_FILE_FORMAT))
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _logging_configured = True

    # Log startup
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging initialized. Log file: {log_path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    This is a convenience wrapper around logging.getLogger() that ensures
    consistent naming across the application.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def setup_orchestrator_logging(
    log_file: Path,
    session_id: Optional[str] = None,
) -> logging.Logger:
    """
    Set up a dedicated logger for the orchestrator with a specific log file.

    This creates a separate logger for orchestrator debug output that writes
    to a dedicated file (replacing the old DebugLogger class).

    Args:
        log_file: Path to the orchestrator log file
        session_id: Optional session identifier

    Returns:
        Configured logger for orchestrator use
    """
    logger = logging.getLogger("orchestrator")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    logger.handlers.clear()

    # Prevent propagation to root logger (orchestrator has its own file)
    logger.propagate = False

    # Create handler for orchestrator-specific log file
    handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_SIZE,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(handler)

    # Log session start
    import os
    logger.info("=" * 60)
    logger.info(f"Orchestrator Session Started (PID: {os.getpid()})")
    if session_id:
        logger.info(f"Session ID: {session_id}")
    logger.info("=" * 60)

    return logger


def log_section(logger: logging.Logger, title: str) -> None:
    """
    Log a section header for visual separation in log files.

    Args:
        logger: Logger instance
        title: Section title
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  {title}")
    logger.info("=" * 60)
    logger.info("")


def log_key_value(logger: logging.Logger, message: str, **kwargs) -> None:
    """
    Log a message with key-value pairs.

    Args:
        logger: Logger instance
        message: Main message
        **kwargs: Key-value pairs to log
    """
    logger.info(message)
    for key, value in kwargs.items():
        logger.info(f"    {key}: {value}")
