# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the application

The entry point is `src/app.py`. All commands must be run from the `src/` directory (or with the path adjusted):

```bash
# Development (Windows)
cd src
python app.py

# Production (Render / Unix)
python -m gunicorn app:app --bind 0.0.0.0:5000 --workers 3 --timeout 120
```

The app tries to connect to PostgreSQL (`DATABASE_URL` env var) on startup. If it fails, it falls back to SQLite at `src/uploads/fallback_local.db`.

## Database migrations

Migrations live in `src/migrations/versions/`. Always run from `src/`:

```bash
cd src
flask db migrate -m "description"
flask db upgrade
```

Seeds run automatically on first startup when using SQLite (no `DATABASE_URL` set).

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (optional, falls back to SQLite) |
| `SECRET_KEY` | JWT signing key |
| `UPLOAD_DIR` | Directory for file uploads (default: `src/uploads/`) |
| `OPENAI_API_KEY` | Optional — enables AI fallback in intent classifier |

## Architecture

### Request flow

All HTTP routes are in a single `src/routes.py` (~11k lines), registered as a Flask Blueprint (`api_bp`). There is also a smaller `agent_metrics_bp` from `src/services/agent/metrics_routes.py`.

### Bot / Agent pipeline

When a WhatsApp or Telegram message arrives at a webhook route in `routes.py`, it is processed by:

1. `ChatbotService` (`services/chatbot_service.py`) — platform-level parsing, conversation state management (`ChatbotConversationState` model), and reply dispatch.
2. `AgentService` (`services/agent/agent_service.py`) — orchestrates the NLU pipeline in sequence:
   - `IntentClassifier` — heuristic regex rules; falls back to OpenAI if `OPENAI_API_KEY` is set.
   - `EntityExtractor` — extracts client name, culture, variety, date, etc.
   - `EntityResolver` — maps extracted text to real DB IDs (fuzzy match).
   - `DecisionEngine` — maps (intent + entities) → action name.
   - `ActionExecutor` — runs the action (creates visit, generates PDF, lists schedule, etc.).
3. `decision_logger.log_from_agent_result` — writes every decision to `AgentDecisionLog` for quality metrics.

Bot intents: `CREATE_VISIT_LIKE_MESSAGE`, `LIST_WEEK`, `DAILY_ROUTINE`, `GENERATE_PDF`, `CONFIRM`, `CANCEL`, `STATEFUL_REPLY`, `UNKNOWN`.

### Data hierarchy

```
Client → Property → Plot → Planting
                          ↑
Visit (links client + property + plot + planting + consultant)
  └── VisitProduct, Photo
```

`FieldData` stores free-form field observations from the bot, categorized by type (praga, doença, etc.), separate from structured `Visit` records.

### Consultants

The `CONSULTANTS` list in `models.py` is a hardcoded fixture (IDs 1–5). The `Consultant` DB model also exists for Telegram binding (`telegram_link_code`) and is used by `TelegramContactBinding`. Always keep these in sync when adding consultants.

### File storage

Images and uploads go to Cloudflare R2 via `src/utils/r2_client.py` (boto3). Locally they are served from `UPLOAD_DIR` via the `/uploads/<filename>` route.
