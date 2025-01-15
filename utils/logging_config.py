"""Logging configuration for the application."""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from ..config import settings, LOGS_DIR


def _cleanup_old_logs(log_dir: Path, base_name: str, max_files: int, logger: logging.Logger):
    """Clean up old log files when max number is reached.

    Args:
        log_dir: Directory containing log files
        base_name: Base name of the log file (e.g., 'app.log')
        max_files: Maximum number of log files to keep (including base file)
        logger: Logger instance for logging cleanup operations
    """
    try:
        # Get all log files (base + rotated)
        log_files = []
        base_file = log_dir / base_name
        if base_file.exists():
            log_files.append(base_file)

        # Add rotated files
        rotated_files = sorted(
            [f for f in log_dir.glob(f"{base_name}.*") if f.is_file()],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        log_files.extend(rotated_files)

        # If we exceed max files, delete oldest
        if len(log_files) > max_files:
            logger.info(f"Found {len(log_files)} log files, max is {max_files}")
            files_to_delete = log_files[max_files:]
            for old_file in files_to_delete:
                try:
                    logger.debug(f"Deleting old log file: {old_file}")
                    old_file.unlink()
                except OSError as e:
                    logger.error(f"Failed to delete old log file {old_file}: {e}")
            logger.info(f"Deleted {len(files_to_delete)} old log files")
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")


def setup_logging():
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Set up root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all logs, handlers will filter

    # Create formatters and handlers
    formatter = logging.Formatter(settings.logging.format)

    # Console handler with configured console level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.logging.log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with configured file level (typically more verbose)
    log_file = LOGS_DIR / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=settings.logging.file_max_bytes,
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setLevel(settings.logging.file_log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Clean up old log files
    _cleanup_old_logs(
        LOGS_DIR,
        "app.log",
        settings.logging.backup_count + 1,  # +1 to account for the base log file
        root_logger,
    )

    # Set levels for noisy loggers
    for logger_name, level in settings.logging.noisy_loggers.items():
        logging.getLogger(logger_name).setLevel(level)
