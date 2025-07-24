# CrewAI Agent with A2A Protocol

This sample demonstrates a simple image generation agent built with [CrewAI](https://www.crewai.com/open-source) and exposed through the A2A protocol.

## How It Works

This agent utilizes CrewAI and the Google Gemini API to generate images based on text prompts. The A2A protocol enables standardized interaction with the agent, allowing clients to send requests and receive images as artifacts.

```mermaid
sequenceDiagram
    participant Client as A2A Client
    participant Server as A2A Server
    participant Agent as CrewAI Agent
    participant API as Gemini API

    Client->>Server: Send task with text prompt
    Server->>Agent: Forward prompt to image agent
    Note over Server,Agent: Optional: Simulated streaming updates
    Agent->>API: Generate image using Gemini
    API->>Agent: Return generated image
    Agent->>Server: Store image and return ID
    Server->>Client: Respond with image artifact
```

## Key Components

- **CrewAI Agent**: Image generation agent with specialized tools
- **A2A Server**: Provides standardized protocol for interacting with the agent
- **Image Generation**: Uses Gemini API to create images from text descriptions
- **Cache System**: Stores generated images for retrieval (in-memory or file-based)

## Prerequisites

- Python 3.12 or higher
- [UV](https://docs.astral.sh/uv/) package manager (recommended)
- Google API Key (for Gemini access)

## Setup & Running

1. Navigate to the samples directory:

   ```bash
   cd samples/python/agents/crewai
   ```

2. Create an environment file with your API key (or Vertex AI credentials):

   ```bash
   echo "GOOGLE_API_KEY=your_api_key_here" > .env
   ```

3. Set up the Python environment:

   ```bash
   uv python pin 3.13
   uv venv
   source .venv/bin/activate
   ```

4. Run the agent with desired options:

   ```bash
   # Basic run
   uv run .

   # On custom host/port
   uv run . --host 0.0.0.0 --port 8080
   ```

5. Run the A2A client:

   In a separate terminal:

   ```bash
   # Connect to the agent (specify the agent URL with correct port and host)
   cd samples/python/hosts/cli
   uv run . --agent http://localhost:10001
   
   # If you changed the port when starting the agent, use that port instead
   # uv run . --agent http://localhost:YOUR_PORT
   ```

## Build Container Image

Agent can also be built using a container file.

1. Navigate to the `samples/python` directory:

   ```bash
   cd samples/python
   ```

2. Build the container file

    ```bash
    podman build -f agents/crewai/Containerfile . -t crewai-a2a-server
    ```

   > [!Tip]  
   > Podman is a drop-in replacement for `docker` which can also be used in these commands.

3. Run your container

    ```bash
    podman run -p 10001:10001 -e GOOGLE_API_KEY=your_api_key_here crewai-a2a-server
    ```

4. Run A2A client (follow step 5 from the section above)

> [!Important]
>
> - **Access URL:** You must access the A2A client through the URL `0.0.0.0:10001`. Using `localhost` will not work.
> - **Hostname Override:** If you're deploying to an environment where the hostname is defined differently outside the container, use the `HOST_OVERRIDE` environment variable to set the expected hostname on the Agent Card. This ensures proper communication with your client application.

## Features & Improvements

**Features:**

- Text-to-image generation using Google Gemini
- Support for modifying existing images using references
- Robust error handling with automatic retries
- Optional file-based cache persistence
- Improved artifact ID extraction from queries

**Limitations:**

- No true streaming (CrewAI doesn't natively support it)
- Limited agent interactions (no multi-turn conversations)

## Learn More

- [A2A Protocol Documentation](https://a2a-protocol.org)
- [CrewAI Documentation](https://docs.crewai.com/introduction)
- [Google Gemini API](https://ai.google.dev/gemini-api)
