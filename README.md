# OpenAI-basic

Minimal OpenAI chat agent. Same Microsoft 365 Agents SDK hosting shape as
the OpenAI-weather sample, but the brain is a single streaming call to the
OpenAI Chat Completions API — no Semantic Kernel, no plugins.

Two deployment targets are planned:
1. **Local** — anonymous mode, no Azure required (this README).
2. **AWS ECS Fargate + Azure Bot Service** — added later.

## Quick start (local)

```powershell
cd C:\sourcecode\OpenAI-basic
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item env.TEMPLATE .env
# edit .env and paste OPENAI_API_KEY

python -m src.main
# ======== Running on http://0.0.0.0:3978 ========
```

In another terminal:

```powershell
# Health check
(Invoke-WebRequest http://localhost:3978/api/messages).StatusCode  # → 200

# Interactive chat (requires `npm i -g @microsoft/agents-playground-cli`)
agentsplayground -e "http://localhost:3978/api/messages" -c "emulator"
```

## Files

| File | Purpose |
|---|---|
| `src/main.py` | Process entry, starts the aiohttp server |
| `src/app.py` | AgentApplication wiring + OpenAI streaming handler |
| `requirements.txt` | Python deps (Agents SDK + openai) |
| `Dockerfile` | python:3.12-slim image, exposes 3978 |
| `env.TEMPLATE` | Copy to `.env` and fill in `OPENAI_API_KEY` |
| `.gitignore` | Excludes `.env`, `.venv/`, caches |

## Environment variables

| Var | Required | Default | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | — | Your OpenAI key |
| `OPENAI_MODEL` | no | `gpt-4o-mini` | Any chat-completions model |
| `SYSTEM_PROMPT` | no | friendly assistant | System message for every chat |
| `HOST` | no | `0.0.0.0` | aiohttp bind address |
| `PORT` | no | `3978` | aiohttp port |
| `ANONYMOUS_AUTH` | no | `true` | Set `false` in cloud |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` | only when `ANONYMOUS_AUTH=false` | — | Entra app id / secret / tenant |
