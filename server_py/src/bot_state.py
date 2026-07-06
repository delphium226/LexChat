"""Bot identity loaded from bot_config.json at startup.

Lives in a leaf module so routers can import it directly instead of doing
deferred imports from main (which routers should never depend on). Set once
during the lifespan startup; read-only afterwards.
"""

_bot_identity: dict = {}


def set_bot_identity(identity: dict) -> None:
    global _bot_identity
    _bot_identity = identity or {}


def get_bot_identity() -> dict:
    return _bot_identity
