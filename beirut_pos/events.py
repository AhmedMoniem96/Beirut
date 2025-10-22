# beirut_pos/events.py
from collections import defaultdict
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

class EventBus:
    def __init__(self) -> None:
        # mapping: event_name -> list of callbacks
        self._subs: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    # two names so callers using `bus.on` or `bus.subscribe` both work
    def on(self, event: str, callback: Callable[..., Any]) -> None:
        """Subscribe callback(event_args...) to event."""
        self._subs[event].append(callback)

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Alias for `on`."""
        self.on(event, callback)

    def off(self, event: str, callback: Callable[..., Any] | None = None) -> None:
        """Unsubscribe a callback from an event. If callback is None remove all handlers."""
        if callback is None:
            self._subs.pop(event, None)
            return
        lst = self._subs.get(event)
        if not lst:
            return
        try:
            lst.remove(callback)
        except ValueError:
            # callback not found
            pass
        if not lst:
            self._subs.pop(event, None)

    def emit(self, event: str, *args, **kwargs) -> None:
        """Emit event; call subscribers. Exceptions are logged but do not stop other handlers."""
        handlers = list(self._subs.get(event, []))
        for cb in handlers:
            try:
                cb(*args, **kwargs)
            except Exception:
                logger.exception("Event handler for %s raised", event)

# Single shared instance
bus = EventBus()

# convenience top-level functions (optional)
on = bus.on
subscribe = bus.subscribe
off = bus.off
emit = bus.emit

__all__ = ["EventBus", "bus", "on", "subscribe", "off", "emit"]
