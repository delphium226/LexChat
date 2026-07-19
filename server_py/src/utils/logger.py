import ctypes
import ctypes.wintypes
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

from .log_context import RequestIdFilter

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _resolve_level(env_var: str, default: int = logging.INFO) -> int:
    """Resolve a logging level from an env var name (e.g. "INFO", "DEBUG").

    Read straight from the environment rather than importing `settings` — this
    module is initialised before most of the app, so importing config here risks
    an import cycle. An unrecognised value falls back to `default`.
    """
    name = os.getenv(env_var, "").strip().upper()
    if not name:
        return default
    return getattr(logging, name, default) if isinstance(getattr(logging, name, None), int) else default

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


class _WindowsSafeRotatingFileHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler that tolerates Windows file-lock errors on rollover.

    When uvicorn runs with --reload, the reloader and worker processes both hold
    the log file open. os.rename() fails with PermissionError (WinError 32) if
    either process tries to rotate while the other has the handle. Swallowing the
    error here keeps logging working; rotation resumes once only one process holds
    the file (i.e. in production, or after the reloader's child is replaced).
    """

    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            pass


def _create_file_handler(filename: str, level=logging.INFO) -> _WindowsSafeRotatingFileHandler:
    handler = _WindowsSafeRotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(RequestIdFilter())
    handler.suffix = "%Y-%m-%d"
    return handler


def _create_console_handler(level=logging.INFO) -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(_ColourFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(RequestIdFilter())
    return handler


def setup_logging(bot_id: str = ""):
    """Configure structured logging for the application.

    Creates three loggers mirroring the Node.js Winston setup:
    - app: General application logs
    - agent: AI/tool activity logs
    - http: HTTP request/response logs

    When bot_id is supplied, log files are prefixed with "<bot_id>_" so that
    multiple bot processes sharing the same logs/ directory write to separate
    files and avoid Windows file-lock conflicts on TimedRotatingFileHandler.
    """
    _enable_windows_ansi()
    prefix = f"{bot_id}_" if bot_id else ""

    # Base level for all app loggers — overridable at runtime via LOG_LEVEL
    # (e.g. LOG_LEVEL=DEBUG) without a code change. Console can be tuned
    # independently via CONSOLE_LOG_LEVEL; blank = same as LOG_LEVEL.
    base_level = _resolve_level("LOG_LEVEL", logging.INFO)
    console_level = _resolve_level("CONSOLE_LOG_LEVEL", base_level)

    # App logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(base_level)
    app_logger.addHandler(_create_file_handler(f"{prefix}app.log", base_level))
    app_logger.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))
    app_logger.addHandler(_create_console_handler(console_level))

    # Agent logger
    agent_logger = logging.getLogger("agent")
    agent_logger.setLevel(base_level)
    agent_logger.addHandler(_create_file_handler(f"{prefix}agent.log", base_level))
    agent_logger.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))
    agent_logger.addHandler(_create_console_handler(console_level))

    # HTTP logger — access log. Also fans 5xx into the shared error.log so server
    # errors are recoverable from one place (the middleware logs 5xx at ERROR).
    http_logger = logging.getLogger("http")
    http_logger.setLevel(base_level)
    http_logger.addHandler(_create_file_handler(f"{prefix}http.log", base_level))
    http_logger.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))

    # Crawler logger — the SP Official Report / SP TV background crawler. Long-running
    # and chatty (backfills, daily deltas, caption capture), so it gets its own file
    # to keep app.log readable; errors also go to the shared error.log. Only the
    # parliament bot writes here (delay=True → no file until first crawl log line).
    crawler_logger = logging.getLogger("crawler")
    crawler_logger.setLevel(base_level)
    crawler_logger.addHandler(_create_file_handler(f"{prefix}crawler.log", base_level))
    crawler_logger.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))
    crawler_logger.addHandler(_create_console_handler(console_level))

    # SP TV video deep-link resolver (sptv_client, caption_match). Parliament-bot
    # only and fail-soft — previously logged to an unconfigured "sptv" logger that
    # propagated to the handler-less root, so INFO was dropped and WARNING+ went to
    # bare stderr. Give it its own file (+ shared error.log) so caption diagnostics
    # are recoverable. delay=True → no file until the first line is written.
    sptv_logger = logging.getLogger("sptv")
    sptv_logger.setLevel(base_level)
    sptv_logger.addHandler(_create_file_handler(f"{prefix}sptv.log", base_level))
    sptv_logger.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))
    sptv_logger.addHandler(_create_console_handler(console_level))

    # Adopt uvicorn's own error logger (startup/shutdown/lifecycle errors) into our
    # handler set so they land in app.log + the shared error.log rather than only on
    # uvicorn's default console handler. uvicorn.access is silenced at the process
    # level via --no-access-log in the launch scripts (our http middleware covers it),
    # so it is left untouched here.
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers.clear()          # drop uvicorn's default handler
    uvicorn_error.setLevel(base_level)
    uvicorn_error.addHandler(_create_file_handler(f"{prefix}app.log", base_level))
    uvicorn_error.addHandler(_create_file_handler(f"{prefix}error.log", logging.ERROR))
    uvicorn_error.addHandler(_create_console_handler(console_level))
    uvicorn_error.propagate = False         # avoid double emit if root ever gets handlers

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
