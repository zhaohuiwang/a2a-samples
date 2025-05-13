from typing_extensions import override

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Task,
)
from a2a.utils import new_agent_text_message


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
    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise Exception('cancel not supported')
