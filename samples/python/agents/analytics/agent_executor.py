from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    FilePart,
    FileWithBytes,
    InvalidParamsError,
    Part,
    Task,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    completed_task,
    new_artifact,
)
from a2a.utils.errors import ServerError
from agent import ChartGenerationAgent


class ChartGenerationAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = ChartGenerationAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        try:
            result = self.agent.invoke(query, context.context_id)
        except Exception as e:
            raise ServerError(
                error=ValueError(f'Error invoking agent: {e}')
            ) from e

        data = self.agent.get_image_data(
            session_id=context.context_id, image_key=result.raw
        )
        if data and not data.error:
            parts = [
                Part(
                    root=FilePart(
                        file=FileWithBytes(
                            bytes=data.bytes,
                            mime_type=data.mime_type,
                            name=data.name,
                        )
                    )
                )
            ]

        else:
            parts = [
                Part(
                    root=TextPart(
                        text=data.error
                        if data
                        else 'Failed to generate chart image.'
                    ),
                )
            ]

        await event_queue.enqueue_event(
            completed_task(
                context.task_id,
                context.context_id,
                [new_artifact(parts, f'chart_{context.task_id}')],
                [context.message],
            )
        )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())

    def _validate_request(self, context: RequestContext) -> bool:
        return False
