import asyncio

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from typing_extensions import override
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import Event, EventQueue
from a2a.utils import new_agent_text_message
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task,
    TextPart,
)

class HelloWorldAgent:
    """Hello World Agent."""

    async def invoke(self) -> str:
      return 'Hello World'


class HelloWorldAgentExecutor(AgentExecutor):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.agent = HelloWorldAgent()

    @override
    async def execute(
        self,
        request: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        result = await self.agent.invoke()
        event_queue.enqueue_event(new_agent_text_message(result))

    @override
    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> Task | None:
        raise Exception("cancel not supported")
