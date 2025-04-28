import asyncio

from collections.abc import AsyncGenerator

from a2a.server import AgentProxy
from a2a.types import (
    Artifact,
    CancelTaskRequest,
    CancelTaskSuccessResponse,
    JSONRPCErrorResponse,
    SendTaskRequest,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    SendTaskStreamingSuccessResponse,
    SendTaskSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskNotCancelableError,
    TaskResubscriptionRequest,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    UnsupportedOperationError,
)
from a2a.utils import get_text_artifact


class FakeAgent:
    """Test Agent."""

    async def invoke(self):
        return 'Hello World'

    async def stream(self) -> AsyncGenerator[str, None]:
        yield 'Hello '
        await asyncio.sleep(2)
        yield 'World'


class TestAgentProxy(AgentProxy):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.agent = FakeAgent()

    async def on_send(
        self, task: Task, request: SendTaskRequest
    ) -> SendTaskSuccessResponse | JSONRPCErrorResponse:
        result = await self.agent.invoke()

        if not task.artifacts:
            task.artifacts = []

        artifact: Artifact = get_text_artifact(result, len(task.artifacts))
        task.artifacts.append(artifact)
        task.status.state = TaskState.completed

        return SendTaskSuccessResponse(id=request.id, result=task)

    async def on_send_subscribe(  # type: ignore
        self, task: Task, request: SendTaskStreamingRequest
    ) -> AsyncGenerator[SendTaskStreamingResponse, None]:
        if not task.artifacts:
            task.artifacts = []
        i = 0
        new_index = len(task.artifacts)
        async for chunk in self.agent.stream():
            artifact_update = TaskArtifactUpdateEvent(
                id=task.id,
                artifact=get_text_artifact(chunk, new_index),
                append=i > 0,
                lastChunk=False,  # TODO: set this value, but is this needed?
            )
            i += 1
            yield SendTaskStreamingResponse(
                root=SendTaskStreamingSuccessResponse(
                    id=request.id, result=artifact_update
                )
            )

        status_update = TaskStatusUpdateEvent(
            id=task.id,
            status=TaskStatus(state=TaskState.completed),
            final=True,
        )
        yield SendTaskStreamingResponse(
            root=SendTaskStreamingSuccessResponse(
                id=request.id, result=status_update
            )
        )

    async def on_cancel(
        self, task: Task, request: CancelTaskRequest
    ) -> CancelTaskSuccessResponse | JSONRPCErrorResponse:
        return JSONRPCErrorResponse(
            id=request.id, error=TaskNotCancelableError()
        )

    async def on_resubscribe(  # type: ignore
        self, task: Task, request: TaskResubscriptionRequest
    ) -> AsyncGenerator[SendTaskStreamingResponse, None]:
        yield SendTaskStreamingResponse(
            root=JSONRPCErrorResponse(
                id=request.id, error=UnsupportedOperationError()
            )
        )
