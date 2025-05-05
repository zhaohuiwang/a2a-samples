import asyncio

from collections.abc import AsyncGenerator

from a2a.server import AgentProxy
from a2a.types import (
    Artifact,
    CancelTaskRequest,
    CancelTaskResponse,
    JSONRPCErrorResponse,
    SendTaskRequest,
    SendTaskResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    SendTaskStreamingSuccessResponse,
    SendTaskSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskResubscriptionRequest,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    UnsupportedOperationError,
)
from a2a.utils import build_text_artifact


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
    ) -> SendTaskResponse:
        result = await self.agent.invoke()

        if not task.artifacts:
            task.artifacts = []

        artifact: Artifact = build_text_artifact(result, len(task.artifacts))
        task.artifacts.append(artifact)
        task.status.state = TaskState.completed

        return SendTaskResponse(
            root=SendTaskSuccessResponse(id=request.id, result=task)
        )

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
                artifact=build_text_artifact(chunk, new_index),
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
    ) -> CancelTaskResponse:
        return CancelTaskResponse(
            root=JSONRPCErrorResponse(
                id=request.id, error=UnsupportedOperationError()
            )
        )

    async def on_resubscribe(  # type: ignore
        self, task: Task, request: TaskResubscriptionRequest
    ) -> AsyncGenerator[SendTaskStreamingResponse, None]:
        yield SendTaskStreamingResponse(
            root=JSONRPCErrorResponse(
                id=request.id, error=UnsupportedOperationError()
            )
        )
