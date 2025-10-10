from collections import defaultdict

class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)

    def subscribe(self, event_name, callback):
        self._subs[event_name].append(callback)

    def emit(self, event_name, *args, **kwargs):
        for cb in list(self._subs[event_name]):
            cb(*args, **kwargs)

bus = EventBus()
