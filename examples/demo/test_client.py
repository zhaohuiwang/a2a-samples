from a2a.client import A2AClient
from typing import Any
import httpx


async def main() -> None:
    async with httpx.AsyncClient() as httpx_client:
        client = await A2AClient.get_client_from_agent_card_url(
            httpx_client, 'http://localhost:9999'
        )
        send_task_payload: dict[str, Any] = {
            'id': '133',
            'message': {
                'role': 'user',
                'parts': [
                    {'type': 'text', 'text': 'how much is 10 USD in INR?'}
                ],
            },
        }

        response = await client.send_task(payload=send_task_payload)
        print(response)

        get_task_payload = {'id': '133'}
        get_response = await client.get_task(payload=get_task_payload)
        print(get_response)

        stream_response = client.send_task_streaming(payload=send_task_payload)
        async for chunk in stream_response:
            print(chunk)

        cancel_task_payload = {'id': '133'}
        cancel_response = await client.cancel_task(payload=cancel_task_payload)
        print(cancel_response)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
