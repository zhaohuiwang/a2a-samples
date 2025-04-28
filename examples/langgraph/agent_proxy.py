from agent import CurrencyAgent
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
    TaskSendParams,
    TextPart,
    Message,
    Role,
    Part
)
from a2a.utils import get_text_artifact
from typing import Any
from datetime import datetime

class CurrencyAgentProxy(AgentProxy):
    """Current AgentProxy Example."""

    def __init__(self):
        self.agent = CurrencyAgent()

    async def on_send(
        self, task: Task, request: SendTaskRequest
    ) -> SendTaskSuccessResponse | JSONRPCErrorResponse:
        params: TaskSendParams = request.params

        query = self._get_user_query(params)
        
        agent_response:dict[str, Any] = self.agent.invoke(query, task.sessionId) 

        task.status.timestamp = datetime.now().isoformat()
        if agent_response["require_user_input"]:
            task.status.state = TaskState.input_required
            task.status.message = Message(role=Role.agent, parts=[Part(root=TextPart(text=agent_response["content"]))])            
        else:
            task.status.state = TaskState.completed
            if not task.artifacts:
                task.artifacts = []

            artifact: Artifact = get_text_artifact(agent_response["content"], len(task.artifacts))
            task.artifacts.append(artifact)
        
        return SendTaskSuccessResponse(id=request.id, result=task)

    async def on_send_subscribe(  # type: ignore
        self, task: Task, request: SendTaskStreamingRequest
    ) -> AsyncGenerator[SendTaskStreamingResponse, None]:
        params: TaskSendParams = request.params
        query = self._get_user_query(params)

        if not task.artifacts:
            task.artifacts = []
        
        new_index = len(task.artifacts)
        async for item in self.agent.stream(query, task.sessionId):
            is_task_complete = item["is_task_complete"]
            require_user_input = item["require_user_input"]
            parts: list[Part] = [Part(root=TextPart(text=item["content"]))]
            
            end_stream = False
            artifact = None
            message = None
            if not is_task_complete and not require_user_input:
                task_state = TaskState.working
                message = Message(role=Role.agent, parts=parts,)
            elif require_user_input:
                task_state = TaskState.input_required
                message = Message(role=Role.agent, parts=parts)
                end_stream = True
            else:
                task_state = TaskState.completed
                artifact = get_text_artifact(item["content"], new_index)
                end_stream = True

            if artifact:
                    task_artifact_update_event = TaskArtifactUpdateEvent(
                        id=task.id, artifact=artifact, append= False, lastChunk = True
                    )
                    yield SendTaskStreamingResponse(
                        root=SendTaskStreamingSuccessResponse(
                            id=request.id, result=task_artifact_update_event
                        )
                    )

            task_status_event = TaskStatusUpdateEvent(
                id=task.id, status=TaskStatus(state=task_state, message=message, timestamp = datetime.now().isoformat()), final=end_stream
            )
            
            yield SendTaskStreamingResponse(
                root=SendTaskStreamingSuccessResponse(
                    id=request.id, result=task_status_event
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

    def _get_user_query(self, task_send_params: TaskSendParams) -> str:
        part = task_send_params.message.parts[0].root
        if not isinstance(part, TextPart):
            raise ValueError("Only text parts are supported")
        return part.text