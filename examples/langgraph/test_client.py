from a2a.client import A2AClient
from typing import Any
from uuid import uuid4
from a2a.types import (
    SendTaskResponse,
    GetTaskResponse,
    SendTaskSuccessResponse,
    Task,
    TaskState,
)
import httpx

AGENT_URL = 'http://localhost:10000'


def create_send_task_payload(
    task_id: str, text: str, session_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        'id': task_id,
        'message': {
            'role': 'user',
            'parts': [{'type': 'text', 'text': text}],
        },
    }
    if session_id:
        payload['sessionId'] = session_id
    return payload


def print_json_response(response: Any, description: str) -> None:
    """Helper function to print the JSON representation of a response."""
    print(f'--- {description} ---')
    if hasattr(response, 'root'):
        print(f'{response.root.model_dump_json()}\n')
    else:
        print(f'{response.model_dump()}\n')


async def run_single_turn_test(client: A2AClient) -> str:
    """Runs a single-turn non-streaming test."""
    task_id: str = uuid4().hex
    send_payload = create_send_task_payload(
        task_id, 'how much is 10 USD in CAD?'
    )
    # Send Task
    send_response: SendTaskResponse = await client.send_task(
        payload=send_payload
    )
    print_json_response(send_response, 'Single Turn Request Response')

    print('---Query Task---')
    # query the task
    task_id_payload = {'id': task_id}
    get_response: GetTaskResponse = await client.get_task(
        payload=task_id_payload
    )
    print_json_response(get_response, 'Query Task Response')
    return task_id  # Return task_id in case it's needed, though not used here


async def run_streaming_test(client: A2AClient) -> None:
    """Runs a single-turn streaming test."""
    task_id: str = uuid4().hex
    send_payload = create_send_task_payload(
        task_id, 'how much is 50 EUR in JPY?'
    )

    print('--- Single Turn Streaming Request ---')
    stream_response = client.send_task_streaming(payload=send_payload)
    async for chunk in stream_response:
        print_json_response(chunk, 'Streaming Chunk')


async def run_multi_turn_test(client: A2AClient) -> None:
    """Runs a multi-turn non-streaming test."""
    print('--- Multi-Turn Request ---')
    # --- First Turn ---
    task_id: str = uuid4().hex
    first_turn_payload = create_send_task_payload(
        task_id, 'how much is 100 USD?'
    )
    first_turn_response: SendTaskResponse = await client.send_task(
        payload=first_turn_payload
    )
    print_json_response(first_turn_response, 'Multi-Turn: First Turn Response')

    session_id: str | None = None
    if isinstance(first_turn_response.root, SendTaskSuccessResponse):
        task: Task = first_turn_response.root.result
        session_id = task.sessionId  # Capture session ID

        # --- Second Turn (if input required) ---
        if task.status.state == TaskState.input_required and session_id:
            print('--- Multi-Turn: Second Turn (Input Required) ---')
            second_turn_payload = create_send_task_payload(
                task_id, 'in GBP', session_id
            )
            second_turn_response = await client.send_task(
                payload=second_turn_payload
            )
            print_json_response(
                second_turn_response, 'Multi-Turn: Second Turn Response'
            )
        elif not session_id:
            print('Warning: Could not get session ID from first turn response.')
        else:
            print(
                'First turn completed, no further input required for this test case.'
            )


async def main() -> None:
    """Main function to run the tests."""
    print(f'Connecting to agent at {AGENT_URL}...')
    try:
        async with httpx.AsyncClient() as httpx_client:
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client, AGENT_URL
            )
            print('Connection successful.')

            await run_single_turn_test(client)
            await run_streaming_test(client)
            await run_multi_turn_test(client)

    except Exception as e:
        print(f'An error occurred: {e}')
        print('Ensure the agent server is running.')


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
