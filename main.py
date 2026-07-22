"""Process entry point: `python -m src.main`."""
import logging

from .app import AGENT_APP, AUTH_CONFIGURATION
from .start_server import start_server

logging.basicConfig(level=logging.INFO)
logging.getLogger("microsoft_agents").setLevel(logging.INFO)

start_server(
    agent_application=AGENT_APP,
    auth_configuration=AUTH_CONFIGURATION,
)
