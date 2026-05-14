import ctypes
import ctypes.wintypes
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ANSI colour codes — applied per level, reset after the line
_RESET  = "\033[0m"
_GREY   = "\033[90m"
_WHITE  = "\033[97m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_BOLD_RED = "\033[1;31m"

def _enable_windows_ansi():
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.wintypes.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


_LEVEL_COLOURS = {
    logging.DEBUG:    _GREY,
    logging.INFO:     _WHITE,
    logging.WARNING:  _YELLOW,
    logging.ERROR:    _RED,
    logging.CRITICAL: _BOLD_RED,
}


class _ColourFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelno, "")
        line = super().format(record)
        return f"{colour}{line}{_RESET}" if colour else line


def _create_file_handler(filename: str, level=logging.INFO) -> TimedRotatingFileHandler:
    handler = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.suffix = "%Y-%m-%d"
    return handler


def _create_console_handler(level=logging.INFO) -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(_ColourFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    return handler


def setup_logging():
    """Configure structured logging for the application.

    Creates three loggers mirroring the Node.js Winston setup:
    - app: General application logs
    - agent: AI/tool activity logs
    - http: HTTP request/response logs
    """
    _enable_windows_ansi()
    # App logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(_create_file_handler("app.log"))
    app_logger.addHandler(_create_file_handler("error.log", logging.ERROR))
    app_logger.addHandler(_create_console_handler())

    # Agent logger
    agent_logger = logging.getLogger("agent")
    agent_logger.setLevel(logging.INFO)
    agent_logger.addHandler(_create_file_handler("agent.log"))
    agent_logger.addHandler(_create_console_handler())

    # HTTP logger
    http_logger = logging.getLogger("http")
    http_logger.setLevel(logging.INFO)
    http_logger.addHandler(_create_file_handler("http.log"))

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
