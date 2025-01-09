"""Logging configuration for the application."""

import logging
import logging.handlers
import signal
import atexit
from datetime import datetime

from ..config import LOGGING_CONFIG, LOGS_DIR


class BatchingRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """A rotating file handler that batches writes to reduce I/O."""

    def __init__(self, filename, mode="a", maxBytes=0, backupCount=0, encoding=None, delay=False, batch_size=10):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.batch_size = batch_size
        self.buffer = []
        # Register cleanup handlers
        atexit.register(self.flush)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle termination signals by flushing logs before exit."""
        self.flush()
        # Re-raise the signal after handling
        signal.default_int_handler(signum, frame)

    def __del__(self):
        """Ensure logs are flushed when handler is destroyed."""
        self.flush()

    def emit(self, record):
        """Buffer the log record and write when batch is full."""
        try:
            msg = self.format(record)
            self.buffer.append(msg)

            if len(self.buffer) >= self.batch_size:
                self.flush()
        except Exception:
            self.handleError(record)

    def flush(self):
        """Write all buffered records to file."""
        if self.buffer:
            try:
                if self.stream is None:
                    self.stream = self._open()

                # Write all buffered records with a single write call
                self.stream.write("\n".join(self.buffer) + "\n")
                self.buffer = []

                # Check if rotation is needed
                if self.maxBytes > 0:
                    current_size = self.stream.tell()
                    if current_size >= self.maxBytes:
                        self.doRollover()

                self.stream.flush()
            except Exception as e:
                self.handleError(
                    logging.LogRecord(
                        name="BatchingRotatingFileHandler",
                        level=logging.ERROR,
                        pathname="",
                        lineno=0,
                        msg=str(e),
                        args=(),
                        exc_info=None,
                    )
                )


def setup_logging():
    """Configure application-wide logging."""
    # Create logs directory if it doesn't exist
    LOGS_DIR.mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(LOGGING_CONFIG["format"])

    # Console handler - INFO level
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # File handler with batching and rotation - DEBUG level
    log_file = LOGS_DIR / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
    file_handler = BatchingRotatingFileHandler(
        filename=log_file,
        maxBytes=LOGGING_CONFIG["file_max_bytes"],
        backupCount=LOGGING_CONFIG["backup_count"],
        encoding="utf-8",
        batch_size=LOGGING_CONFIG["batch_size"],
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Clean up old log files if more than backup_count exist
    log_files = sorted(LOGS_DIR.glob("scraper_*.log"), reverse=True)
    for old_file in log_files[LOGGING_CONFIG["backup_count"] + 1 :]:
        try:
            old_file.unlink()
        except OSError:
            pass  # Ignore errors in cleanup

    # Configure root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all logs
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Configure noisy loggers
    for logger_name, level in LOGGING_CONFIG["noisy_loggers"].items():
        logging.getLogger(logger_name).setLevel(getattr(logging, level))

    return root_logger
