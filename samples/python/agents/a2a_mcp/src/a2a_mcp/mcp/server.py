# type: ignore
import json
import os
import sqlite3
import traceback

from pathlib import Path

import httpx
from google import genai
import numpy as np
import pandas as pd


#from a2a_mcp.common.utils import init_api_key
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger



from dotenv import load_dotenv, set_key


# Define the path to the .env file
env_file_path = Path(__file__).parent.parent.parent.parent / ".env"

# Load environment variables from the specified .env file
load_dotenv(dotenv_path=env_file_path)
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

logger = get_logger(__name__)

AGENT_CARDS_DIR = 'agent_cards'
MODEL = 'models/gemini-embedding-001'
# Embedding models
# Generally available model: gemini-embedding-001
# embedding-001 (Deprecating on August 14, 2025)
# text-embedding-004 (Deprecating on January 14, 2026)

SQLLITE_DB = 'travel_agency.db'
PLACES_API_URL = 'https://places.googleapis.com/v1/places:searchText'


def generate_embeddings(text):
    """Generates embeddings for the given text using Google Generative AI.

    Args:
        text: The input string for which to generate embeddings.

    Returns:
        A list of embeddings representing the input text.
    """
    result = client.models.embed_content(
        model=MODEL,
        contents=text,
        config=genai.types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT"
            ),
    )
    return result.embeddings


def load_agent_cards():
    """Loads agent card data from JSON files within a specified directory.

    Returns:
        A list containing JSON data from an agent card file found in the specified directory.
        Returns an empty list if the directory is empty, contains no '.json' files,
        or if all '.json' files encounter errors during processing.
    """
    card_uris = []
    agent_cards = []
    dir_path = Path(AGENT_CARDS_DIR)
    if not dir_path.is_dir():
        logger.error(
            f'Agent cards directory not found or is not a directory: {AGENT_CARDS_DIR}'
        )
        return agent_cards

    logger.info(f'Loading agent cards from card repo: {AGENT_CARDS_DIR}')

    for filename in os.listdir(AGENT_CARDS_DIR):
        if filename.lower().endswith('.json'):
            file_path = dir_path / filename

            if file_path.is_file():
                logger.info(f'Reading file: {filename}')
                try:
                    with file_path.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                        card_uris.append(
                            f'resource://agent_cards/{Path(filename).stem}'
                        )
                        agent_cards.append(data)
                except json.JSONDecodeError as jde:
                    logger.error(f'JSON Decoder Error {jde}')
                except OSError as e:
                    logger.error(f'Error reading file {filename}: {e}.')
                except Exception as e:
                    logger.error(
                        f'An unexpected error occurred processing {filename}: {e}',
                        exc_info=True,
                    )
    logger.info(
        f'Finished loading agent cards. Found {len(agent_cards)} cards.'
    )
    return card_uris, agent_cards


def build_agent_card_embeddings() -> pd.DataFrame:
    """Loads agent cards, generates embeddings for them, and returns a DataFrame.

    Returns:
        Optional[pd.DataFrame]: A Pandas DataFrame containing the original
        'agent_card' data and their corresponding 'Embeddings'. Returns None
        if no agent cards were loaded initially or if an exception occurred
        during the embedding generation process.
    """
    card_uris, agent_cards = load_agent_cards()
    logger.info('Generating Embeddings for agent cards')
    try:
        if agent_cards:
            df = pd.DataFrame(
                {'card_uri': card_uris, 'agent_card': agent_cards}
            )
            df['card_embeddings'] = df.apply(
                lambda row: generate_embeddings(json.dumps(row['agent_card'])),
                axis=1,
            )
            return df
        logger.info('Done generating embeddings for agent cards')
    except Exception as e:
        logger.error(f'An unexpected error occurred : {e}.', exc_info=True)
        return None


def serve(host, port, transport):  # noqa: PLR0915
    """Initializes and runs the Agent Cards MCP server.

    Args:
        host: The hostname or IP address to bind the server to.
        port: The port number to bind the server to.
        transport: The transport mechanism for the MCP server (e.g., 'stdio', 'sse').

    Raises:
        ValueError: If the 'GOOGLE_API_KEY' environment variable is not set.
    """
    #init_api_key()
    logger.info('Starting Agent Cards MCP Server')
    mcp = FastMCP('agent-cards', host=host, port=port)

    df = build_agent_card_embeddings()

    @mcp.tool(
        name='find_agent',
        description='Finds the most relevant agent card based on a natural language query string.',
    )
    def find_agent(query: str) -> str:
        """Finds the most relevant agent card based on a query string.

        This function takes a user query, typically a natural language question or a task generated by an agent,
        generates its embedding, and compares it against the
        pre-computed embeddings of the loaded agent cards. It uses the dot
        product to measure similarity and identifies the agent card with the
        highest similarity score.

        Args:
            query: The natural language query string used to search for a
                   relevant agent.

        Returns:
            The json representing the agent card deemed most relevant
            to the input query based on embedding similarity.
        """
        query_embedding = genai.embed_content(
            model=MODEL, content=query, task_type='retrieval_query'
        )
        dot_products = np.dot(
            np.stack(df['card_embeddings']), query_embedding['embedding']
        )
        best_match_index = np.argmax(dot_products)
        logger.debug(
            f'Found best match at index {best_match_index} with score {dot_products[best_match_index]}'
        )
        return df.iloc[best_match_index]['agent_card']

    @mcp.tool()
    def query_places_data(query: str):
        """Query Google Places."""
        logger.info(f'Search for places : {query}')
        api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        if not api_key:
            logger.info('GOOGLE_PLACES_API_KEY is not set')
            return {'places': []}

        headers = {
            'X-Goog-Api-Key': api_key,
            'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress',
            'Content-Type': 'application/json',
        }
        payload = {
            'textQuery': query,
            'languageCode': 'en',
            'maxResultCount': 10,
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    PLACES_API_URL, headers=headers, json=payload
                    )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as http_err:
            logger.info(f'HTTP error occurred: {http_err}')
            logger.info(f'Response content: {response.text}')
        except httpx.ConnectError as conn_err:
            logger.info(f'Connection error occurred: {conn_err}')
        except httpx.TimeoutException as timeout_err:
            logger.info(f'Timeout error occurred: {timeout_err}')
        except httpx.RequestError as req_err:
            logger.info(
                f'An unexpected error occurred with the request: {req_err}'
                )
        except json.JSONDecodeError:
            logger.info(
                f'Failed to decode JSON response. Raw response: {response.text}'
            )

        return {'places': []}

    @mcp.tool()
    def query_travel_data(query: str) -> dict:
        """ "name": "query_travel_data",
        "description": "Retrieves the most up-to-date, ariline, hotel and car rental availability. Helps with the booking.
        This tool should be used when a user asks for the airline ticket booking, hotel or accommodation booking, or car rental reservations.",
        "parameters": {
            "type": "object",
            "properties": {
            "query": {
                "type": "string",
                "description": "A SQL to run against the travel database."
            }
            },
            "required": ["query"]
        }
        """
        # The above is to influence gemini to pickup the tool.
        logger.info(f'Query sqllite : {query}')

        if not query or not query.strip().upper().startswith('SELECT'):
            raise ValueError(f'In correct query {query}')

        try:
            with sqlite3.connect(SQLLITE_DB) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                result = {'results': [dict(row) for row in rows]}
                return json.dumps(result)
        except Exception as e:
            logger.error(f'Exception running query {e}')
            logger.error(traceback.format_exc())
            if 'no such column' in e:
                return {
                    'error': f'Please check your query, {e}. Use the table schema to regenerate the query'
                }
            return {'error': {e}}

    @mcp.resource('resource://agent_cards/list', mime_type='application/json')
    def get_agent_cards() -> dict:
        """Retrieves all loaded agent cards as a json / dictionary for the MCP resource endpoint.

        This function serves as the handler for the MCP resource identified by
        the URI 'resource://agent_cards/list'.

        Returns:
            A json / dictionary structured as {'agent_cards': [...]}, where the value is a
            list containing all the loaded agent card dictionaries. Returns
            {'agent_cards': []} if the data cannot be retrieved.
        """
        resources = {}
        logger.info('Starting read resources')
        resources['agent_cards'] = df['card_uri'].to_list()
        return resources

    @mcp.resource(
        'resource://agent_cards/{card_name}', mime_type='application/json'
    )
    def get_agent_card(card_name: str) -> dict:
        """Retrieves an agent card as a json / dictionary for the MCP resource endpoint.

        This function serves as the handler for the MCP resource identified by
        the URI 'resource://agent_cards/{card_name}'.

        Returns:
            A json / dictionary
        """
        resources = {}
        logger.info(
            f'Starting read resource resource://agent_cards/{card_name}'
        )
        resources['agent_card'] = (
            df.loc[
                df['card_uri'] == f'resource://agent_cards/{card_name}',
                'agent_card',
            ]
        ).to_list()

        return resources

    logger.info(
        f'Agent cards MCP Server at {host}:{port} and transport {transport}'
    )
    mcp.run(transport=transport)
