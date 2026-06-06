from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator

from .types import StreamEvent


class EventBus:
    def __init__(self, *, retention: int = 500) -> None:
        self.retention = retention
        self._next_id = 1
        self._history: dict[str, deque[StreamEvent]] = defaultdict(lambda: deque(maxlen=retention))
        self._subscribers: dict[str, set[asyncio.Queue[StreamEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, session_id: str, event_type: str, data: dict) -> StreamEvent:
        async with self._lock:
            event = StreamEvent(id=self._next_id, type=event_type, data=data)
            self._next_id += 1
            self._history[session_id].append(event)
            subscribers = list(self._subscribers[session_id])
        for queue in subscribers:
            queue.put_nowait(event)
        return event

    def history(self, session_id: str, *, after: int = 0) -> list[StreamEvent]:
        return [event for event in self._history[session_id] if event.id > after]

    async def subscribe(self, session_id: str, *, after: int = 0) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        for event in self.history(session_id, after=after):
            queue.put_nowait(event)
        async with self._lock:
            self._subscribers[session_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[session_id].discard(queue)
