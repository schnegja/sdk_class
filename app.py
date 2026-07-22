"""OpenAI-basic: a minimal chat agent.

Same hosting/auth shape as a Microsoft 365 Agents SDK bot, but the brain
is a direct call to the OpenAI Chat Completions API (no Semantic Kernel,
no plugins). Conversation history is stored per-conversation in
``ConversationState`` so multi-turn context works.
"""
from __future__ import annotations

from os import environ
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from microsoft_agents.hosting.core import (
    AgentApplication,
    TurnState,
    TurnContext,
    MemoryStorage,
    StoreItem,
)
from microsoft_agents.hosting.core.authorization import AgentAuthConfiguration
from microsoft_agents.hosting.aiohttp import CloudAdapter

load_dotenv()

# ---------------------------------------------------------------------------
# OpenAI configuration (NOT Azure OpenAI). Provide via .env:
#   OPENAI_API_KEY=sk-...
#   OPENAI_MODEL=gpt-4o-mini
# ---------------------------------------------------------------------------
OPENAI_API_KEY = environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = environ.get("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = environ.get(
    "SYSTEM_PROMPT", "You are a friendly, concise assistant."
)

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Copy env.TEMPLATE to .env and fill in your key."
    )

OPENAI_CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Auth mode toggle.
#   ANONYMOUS_AUTH=true   → no MSAL, anyone can POST /api/messages (LOCAL).
#   ANONYMOUS_AUTH=false  → JWT validated against an Entra app (CLOUD).
# ---------------------------------------------------------------------------
ANONYMOUS_AUTH = environ.get("ANONYMOUS_AUTH", "true").lower() == "true"

STORAGE = MemoryStorage()

if ANONYMOUS_AUTH:
    AGENT_APP = AgentApplication[TurnState](
        storage=STORAGE, adapter=CloudAdapter()
    )
    AUTH_CONFIGURATION = AgentAuthConfiguration(anonymous_allowed=True)
else:
    from microsoft_agents.hosting.core import Authorization
    from microsoft_agents.authentication.msal import MsalConnectionManager
    from microsoft_agents.activity import load_configuration_from_env

    agents_sdk_config = load_configuration_from_env(environ)
    CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
    ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)
    AUTHORIZATION = Authorization(STORAGE, CONNECTION_MANAGER, **agents_sdk_config)
    AGENT_APP = AgentApplication[TurnState](
        storage=STORAGE,
        adapter=ADAPTER,
        authorization=AUTHORIZATION,
        **agents_sdk_config,
    )
    AUTH_CONFIGURATION = CONNECTION_MANAGER.get_default_connection_configuration()


# ---------------------------------------------------------------------------
# Conversation history persisted by the SDK's ConversationState.
# We keep it as a plain list[{"role","content"}] so it serializes cleanly.
# ---------------------------------------------------------------------------
class ChatHistoryStoreItem(StoreItem):
    def __init__(self, messages: Optional[list[dict]] = None):
        self.messages: list[dict] = messages or []

    def store_item_to_json(self) -> dict:
        return {"messages": self.messages}

    @staticmethod
    def from_json_to_store_item(json_data: dict) -> "ChatHistoryStoreItem":
        return ChatHistoryStoreItem(messages=list(json_data.get("messages", [])))


@AGENT_APP.conversation_update("membersAdded")
async def on_members_added(context: TurnContext, _state: TurnState):
    for member in context.activity.members_added or []:
        if member.id != context.activity.recipient.id:
            await context.send_activity(
                f"Hi! I'm a basic OpenAI chat agent (model: {OPENAI_MODEL}). "
                "Ask me anything."
            )


@AGENT_APP.activity("message")
async def on_message(context: TurnContext, state: TurnState):
    user_text = (context.activity.text or "").strip()
    if not user_text:
        return

    context.streaming_response.queue_informative_update("Thinking...")

    history = state.get_value(
        "ConversationState.chatHistory",
        lambda: ChatHistoryStoreItem(),
        target_cls=ChatHistoryStoreItem,
    )

    # Build the message list: system prompt + prior turns + this user turn.
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history.messages)
    messages.append({"role": "user", "content": user_text})

    # Stream the OpenAI response back to the channel as it arrives.
    full_reply_parts: list[str] = []
    try:
        stream = await OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                full_reply_parts.append(piece)
                context.streaming_response.queue_text_chunk(piece)
    except Exception as exc:  # noqa: BLE001 — surface any OpenAI/network error
        err = f"Sorry, the model call failed: {exc}"
        context.streaming_response.queue_text_chunk(err)
        await context.streaming_response.end_stream()
        return

    await context.streaming_response.end_stream()

    # Persist this turn so future requests have context.
    full_reply = "".join(full_reply_parts).strip()
    history.messages.append({"role": "user", "content": user_text})
    if full_reply:
        history.messages.append({"role": "assistant", "content": full_reply})
    state.set_value("ConversationState.chatHistory", history)
