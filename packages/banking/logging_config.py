"""
Logging configuration for finance tracker.

This module provides centralized logging setup with support for:
    - Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Console and file logging
    - Verbose mode for debugging
    - Consistent formatting across the application

Example:
    >>> from banking.logging_config import setup_logging
    >>> from pathlib import Path
    >>> 
    >>> # Setup with default settings
    >>> setup_logging()
    >>> 
    >>> # Setup with file logging
    >>> setup_logging(
    ...     level="DEBUG",
    ...     log_file=Path("app.log"),
    ...     verbose=True
    ... )
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO", log_file: Optional[Path] = None, verbose: bool = False
) -> None:
    """
    Set up logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, logs to console only.
        verbose: If True, use DEBUG level
    """
    log_level = logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

