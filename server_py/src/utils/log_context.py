import contextvars
import logging

# Default "-" so lines emitted outside a request (startup, background crawler that
# runs its own tasks) render a stable placeholder rather than raising.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every LogRecord as `request_id`."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
