import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import InternalError, TaskState, UnsupportedOperationError
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from agent import MindsDBAgent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MindsDBAgentExecutor(AgentExecutor):
    """A MindsDB agent executor."""

    def __init__(self):
        self.agent = MindsDBAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            async for item in self.agent.stream(query, task.context_id):
                is_task_complete = item['is_task_complete']
                if not is_task_complete:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item['metadata'],
                            task.context_id,
                            task.id,
                        ),
                    )
                else:
                    parts = item['parts']
                    await updater.add_artifact(parts)
                    await updater.complete()
                    break

        except Exception as e:
            logger.error(f'An error occurred while streaming the response: {e}')
            raise ServerError(error=InternalError()) from e

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())
