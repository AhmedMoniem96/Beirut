from collections import defaultdict
from types import MethodType
from typing import Callable, DefaultDict, List, Union
import weakref


class EventBus:
    """Minimal pub/sub helper that avoids retaining dead listeners."""

    __slots__ = ("_subs",)

    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[Union[Callable[..., None], weakref.WeakMethod]]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        listeners = self._subs[event_name]
        if isinstance(callback, MethodType):
            listeners.append(weakref.WeakMethod(callback))
        else:
            listeners.append(callback)

    def emit(self, event_name: str, *args, **kwargs) -> None:
        listeners = self._subs.get(event_name)
        if not listeners:
            return

        alive: List[Union[Callable[..., None], weakref.WeakMethod]] = []
        for cb in listeners:
            if isinstance(cb, weakref.WeakMethod):
                fn = cb()
                if fn is None:
                    continue
                fn(*args, **kwargs)
                alive.append(cb)
            else:
                cb(*args, **kwargs)
                alive.append(cb)
        self._subs[event_name] = alive


bus = EventBus()
