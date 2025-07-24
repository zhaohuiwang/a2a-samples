import logging
import traceback

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    FilePart,
    InternalError,
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import are_modalities_compatible, new_agent_text_message
from a2a.utils.errors import ServerError
from agents.llama_index_file_chat.agent import (
    ChatResponseEvent,
    InputEvent,
    LogEvent,
    ParseAndChat,
)


logger = logging.getLogger(__name__)


class LlamaIndexAgentExecutor(AgentExecutor):
    """LlamaIndex AgentExecutor implementation."""

    # Technically supports basically anything, but we'll limit to some common types
    SUPPORTED_INPUT_TYPES = [
        'text/plain',
        'application/pdf',
        'application/msword',
        'image/png',
        'image/jpeg',
    ]
    SUPPORTED_OUTPUT_TYPES = ['text', 'text/plain']

    def __init__(
        self,
        agent: ParseAndChat,
    ):
        self.agent = agent
        # Store context state by session ID
        # Ideally, you would use a database or other kv store the context state
        self.ctx_states: Dict[str, Dict[str, Any]] = {}

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        input_event = self._get_input_event(context)
        context_id = context.context_id
        task_id = context.task_id
        try:
            ctx = None
            handler = None

            # Check if we have a saved context state for this session
            print(f'Len of ctx_states: {len(self.ctx_states)}', flush=True)
            saved_ctx_state = self.ctx_states.get(context_id, None)

            if saved_ctx_state is not None:
                # Resume with existing context
                logger.info(f'Resuming session {context_id} with saved context')
                ctx = Context.from_dict(self.agent, saved_ctx_state)
                handler = self.agent.run(
                    start_event=input_event,
                    ctx=ctx,
                )
            else:
                # New session!
                logger.info(f'Starting new session {context_id}')
                handler = self.agent.run(
                    start_event=input_event,
                )

            # Emit an initial task object
            updater = TaskUpdater(event_queue, task_id, context_id)
            await updater.submit()
            async for event in handler.stream_events():
                if isinstance(event, LogEvent):
                    # Send log event as intermediate message
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(event.msg, context_id, task_id),
                    )

            # Wait for final response
            final_response = await handler
            if isinstance(final_response, ChatResponseEvent):
                content = final_response.response
                metadata = (
                    final_response.citations
                    if hasattr(final_response, 'citations')
                    else None
                )
                if metadata is not None:
                    # ensure metadata is a dict of str keys
                    metadata = {str(k): v for k, v in metadata.items()}

                # save the context state to resume the current session
                self.ctx_states[context_id] = handler.ctx.to_dict()

                await updater.add_artifact(
                    [Part(root=TextPart(text=content))],
                    name='llama_summary',
                    metadata=metadata,
                )
                await updater.complete()
            else:
                await updater.failed(f'Unexpected completion {final_response}')

        except Exception as e:
            logger.error(f'An error occurred while streaming the response: {e}')
            logger.error(traceback.format_exc())

            # Clean up context in case of error
            if context_id in self.ctx_states:
                del self.ctx_states[context_id]
            raise ServerError(
                error=InternalError(
                    message=f'An error occurred while streaming the response: {e}'
                )
            )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())

    def _validate_request(self, context: RequestContext) -> bool:
        """True means invalid, false is valid."""
        invalidOutput = self._validate_output_modes(
            context, self.SUPPORTED_OUTPUT_TYPES
        )
        return invalidOutput or self._validate_push_config(context)

    def _get_input_event(self, context: RequestContext) -> InputEvent:
        """Extract file attachment if present in the message parts."""
        file_data = None
        file_name = None
        text_parts = []
        for p in context.message.parts:
            part = p.root
            if isinstance(part, FilePart):
                file_data = part.file.bytes
                file_name = part.file.name
                if file_data is None:
                    raise ValueError('File data is missing!')
            elif isinstance(part, TextPart):
                text_parts.append(part.text)
            else:
                raise ValueError(f'Unsupported part type: {type(part)}')

        return InputEvent(
            msg='\n'.join(text_parts),
            attachment=file_data,
            file_name=file_name,
        )

    def _validate_output_modes(
        self,
        context: RequestContext,
        supportedTypes: list[str],
    ) -> bool:
        accepted_output_modes = (
            context.configuration.accepted_output_modes
            if context.configuration
            else []
        )
        if not are_modalities_compatible(
            accepted_output_modes,
            supportedTypes,
        ):
            logger.warning(
                'Unsupported output mode. Received %s, Support %s',
                accepted_output_modes,
                supportedTypes,
            )
            return True
        return False

    def _validate_push_config(
        self,
        context: RequestContext,
    ) -> bool:
        push_notification_config = (
            context.configuration.push_notification_config
            if context.configuration
            else None
        )
        if push_notification_config and not push_notification_config.url:
            logger.warning('Push notification URL is missing')
            return True

        return False
