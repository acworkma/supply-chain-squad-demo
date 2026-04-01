"""Agent message endpoints — list and stream agent conversation transcript."""

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from app.messages import message_store

router = APIRouter(tags=["messages"])


@router.get("/agent-messages")
async def get_agent_messages(since: int = Query(0, description="Return messages starting from this index")):
    """Return all agent chat messages."""
    messages = message_store.get_messages(since_index=since)
    return [m.model_dump(mode="json") for m in messages]


@router.get("/agent-messages/stream")
async def stream_agent_messages():
    """SSE stream of agent messages as they are produced."""
    queue = await message_store.subscribe()

    async def message_generator():
        try:
            while True:
                msg = await queue.get()
                yield {"data": msg.model_dump_json()}
        finally:
            message_store.unsubscribe(queue)

    return EventSourceResponse(message_generator())
