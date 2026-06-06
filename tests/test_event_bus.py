import asyncio

import pytest

from openai_auth_proxy.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_history_and_retention():
    bus = EventBus(retention=2)
    first = await bus.publish("s", "one", {"n": 1})
    second = await bus.publish("s", "two", {"n": 2})
    third = await bus.publish("s", "three", {"n": 3})

    assert [event.id for event in bus.history("s")] == [second.id, third.id]
    assert [event.id for event in bus.history("s", after=second.id)] == [third.id]
    assert first.id < second.id < third.id


@pytest.mark.asyncio
async def test_event_bus_subscribe_receives_publish():
    bus = EventBus()
    received = []

    async def collect():
        async for event in bus.subscribe("s"):
            received.append(event)
            break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    await bus.publish("s", "message.delta", {"text": "hello"})
    await asyncio.wait_for(task, timeout=1)

    assert received[0].type == "message.delta"
    assert received[0].data == {"text": "hello"}
