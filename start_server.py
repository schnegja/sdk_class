"""Bind the AgentApplication to an aiohttp server on HOST:PORT."""
from os import environ

from aiohttp.web import Application, Request, Response, run_app

from microsoft_agents.hosting.core import (
    AgentApplication,
    AgentAuthConfiguration,
)
from microsoft_agents.hosting.aiohttp import (
    CloudAdapter,
    jwt_authorization_middleware,
    start_agent_process,
)


def start_server(
    agent_application: AgentApplication,
    auth_configuration: AgentAuthConfiguration,
):
    """Wire the AgentApplication into aiohttp and bind HOST:PORT."""

    async def entry_point(req: Request) -> Response:
        agent: AgentApplication = req.app["agent_app"]
        adapter: CloudAdapter = req.app["adapter"]
        return await start_agent_process(req, agent, adapter)

    app = Application(middlewares=[jwt_authorization_middleware])
    app.router.add_post("/api/messages", entry_point)
    # GET returns 200 — used as a load-balancer / Container Apps liveness probe.
    app.router.add_get("/api/messages", lambda _: Response(status=200, text="OK"))
    app["agent_configuration"] = auth_configuration
    app["agent_app"] = agent_application
    app["adapter"] = agent_application.adapter

    run_app(
        app,
        host=environ.get("HOST", "0.0.0.0"),
        port=int(environ.get("PORT", "3978")),
    )
