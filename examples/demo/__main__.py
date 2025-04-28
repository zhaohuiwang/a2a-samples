from agent_proxy import TestAgentProxy

from a2a.server import A2AServer, DefaultA2ARequestHandler
from a2a.types import AgentAuthentication, AgentCapabilities, AgentCard


if __name__ == '__main__':
    agent_card = AgentCard(
        name='Test Agent',
        description='Just a test agent',
        url='http://localhost:9999/',
        version='1.0.0',
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(),
        skills=[],
        authentication=AgentAuthentication(schemes=['public']),
    )

    request_handler = DefaultA2ARequestHandler(agent_proxy=TestAgentProxy())

    server = A2AServer(agent_card=agent_card, request_handler=request_handler)
    server.start(host='0.0.0.0', port=9999)
