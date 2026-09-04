import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

# A filter to allow logs only up to a certain level (e.g., INFO)
class MaxLevelFilter(logging.Filter):
    """
    Filters (lets through) all messages with level <= max_level.
    """
    def __init__(self, max_level):
        super().__init__()
        self.max_level = max_level

    def filter(self, record):
        return record.levelno <= self.max_level


def setup_logging(
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    console: bool = True,
    retention_days: int = 30
):
    """
    Configures logging for the entire application.

    This function should be called once at the beginning of the application's lifecycle.
    After this is called, any part of the app can get a logger instance by calling:
    `logger = logging.getLogger(__name__)`

    :param log_dir: The directory to store log files.
    :param log_level: The minimum logging level to be processed.
    :param console: If True, logs will also be output to the console.
    :param retention_days: The number of days to keep log files.
    """
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Use the root logger to catch all logs from any module
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Prevent adding duplicate handlers if this function is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # --- File Handlers ---
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # 1. Info Handler: for general logs (INFO + WARNING; ERROR/CRITICAL go to error.log)
    info_log_file = log_path / "app.log"
    info_handler = TimedRotatingFileHandler(
        info_log_file, when="midnight", interval=1, backupCount=retention_days, encoding="utf-8"
    )
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.INFO)
    # This filter ensures that ERROR and CRITICAL messages don't go to the info log
    info_handler.addFilter(MaxLevelFilter(logging.WARNING))
    root_logger.addHandler(info_handler)


    # 2. Error Handler: for error logs only (ERROR and CRITICAL)
    error_log_file = log_path / "error.log"
    error_handler = TimedRotatingFileHandler(
        error_log_file, when="midnight", interval=1, backupCount=retention_days, encoding="utf-8"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)


    # --- Console Handler ---
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    # Attach the rotating file handlers directly to uvicorn's loggers so that
    # HTTP access logs and server lifecycle messages also land in app.log /
    # error.log. propagate=False avoids duplication through the "uvicorn"
    # parent logger (uvicorn.error still reaches "uvicorn" via its own
    # propagate=True and reuses these handlers).
    _configure_uvicorn_loggers(info_handler, error_handler, console=console)


def _configure_uvicorn_loggers(
    info_handler: logging.Handler,
    error_handler: logging.Handler,
    console: bool = True,
) -> None:
    """
    Wire uvicorn loggers to the application's rotating file handlers and
    preserve uvicorn's native colored console output.

    uvicorn and uvicorn.access receive the file handlers directly and set
    propagate=False so their records do not bubble up and get duplicated by
    the "uvicorn" parent's console handler. uvicorn.error keeps
    propagate=True so it reuses the handlers attached to "uvicorn".
    """
    for name in ("uvicorn", "uvicorn.access"):
        lg = logging.getLogger(name)
        # Remove file handlers attached by a previous setup_logging() call
        # (e.g. under uvicorn --reload where this runs in both processes).
        # Console handlers are left untouched so uvicorn's colored output stays.
        lg.handlers = [
            h for h in lg.handlers if not isinstance(h, TimedRotatingFileHandler)
        ]
        lg.addHandler(info_handler)
        lg.addHandler(error_handler)
        lg.propagate = False

    # uvicorn.error has no own handlers in the default config; let it bubble
    # up to "uvicorn" so it inherits both the file handlers and the colored
    # console handler attached there.
    logging.getLogger("uvicorn.error").propagate = True

    if not console:
        return

    try:
        from uvicorn.logging import AccessFormatter, DefaultFormatter
    except ImportError:  # pragma: no cover - uvicorn is a hard dependency
        return

    uvicorn_logger = logging.getLogger("uvicorn")
    if not any(isinstance(h, logging.StreamHandler) for h in uvicorn_logger.handlers):
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(DefaultFormatter("%(levelprefix)s %(message)s", use_colors=None))
        uvicorn_logger.addHandler(h)

    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(h, logging.StreamHandler) for h in access_logger.handlers):
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(
            AccessFormatter('%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s')
        )
        access_logger.addHandler(h)
