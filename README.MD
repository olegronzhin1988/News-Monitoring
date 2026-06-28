# News Monitoring API

A learning project: news monitoring by subscription topic with AI analysis (sentiment, summary, key events) and asynchronous processing via Celery + RabbitMQ.

## Stack

- **FastAPI** + **SQLAlchemy 2.0 (async)** + **PostgreSQL** + **Alembic**
- **Celery** + **RabbitMQ** (broker) + **Redis** (result backend)
- **Groq** (primary LLM) + **OpenRouter** (fallback)
- **NewsAPI** — news source
- **Docker Compose** — infrastructure (postgres, redis, rabbitmq)

## Project structure

```
app/
├── core/
│   ├── config.py        # Settings (pydantic-settings), computed URLs
│   ├── database.py       # async engine, session, get_db dependency (for FastAPI)
│   └── celery_app.py     # Celery configuration, include with task modules
├── models/
│   └── models.py          # SubscriptionsModel, NewsAnalysisModel, AlertsModel
├── schemas/
│   └── subscription.py    # Pydantic schemas (Create/Update/Response)
├── api/
│   └── subscriptions.py   # CRUD router for subscriptions
├── services/
│   ├── news_fetcher.py     # NewsAPI integration (async httpx)
│   └── llm_analyzer.py      # article analysis via Groq/OpenRouter with fallback
└── tasks/
    └── analysis_tasks.py    # Celery task analyze_subscription
```

## Running (development)

1. Copy `.env.example` → `.env`, fill in real keys.
   **Important:** do NOT use quotes around values or spaces around `=` in `.env`.
   Correct: `RABBITMQ_USER=user`
   Incorrect: `RABBITMQ_USER = "user"` (breaks Docker Compose, even though pydantic silently tolerates it — a mismatch between how different consumers of the file parse it).

2. Start the infrastructure:
   ```bash
   docker-compose up -d
   ```

3. Apply migrations:
   ```bash
   alembic upgrade head
   ```

4. Start the API:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Start the Celery worker (Windows — `--pool=solo` is mandatory):
   ```bash
   celery -A app.core.celery_app worker --loglevel=info --pool=solo
   ```

## Known infrastructure quirks (worth reading)

### RabbitMQ 4.x — password may not apply on first startup

On RabbitMQ 4.x (especially with `khepri_db` enabled), seeding the user via `RABBITMQ_DEFAULT_USER`/`RABBITMQ_DEFAULT_PASSWORD` sometimes fails to hash the password correctly on first initialization of an **empty** volume. The user is created (visible in logs as `Created user 'user'`), but login is actually rejected as `invalid credentials`.

**This is already automated**: `rabbitmq-init.sh` runs alongside `rabbitmq-server` (see `command` in `docker-compose.yml`) and forcibly calls `rabbitmqctl change_password` after startup. If for some reason the automation doesn't kick in — run manually:
```bash
docker exec news-monitoring-rabbitmq-1 rabbitmqctl change_password user <password_from_.env>
```

Checking credentials directly (bypassing network and app layers):
```bash
docker exec news-monitoring-rabbitmq-1 rabbitmqctl authenticate_user user <password>
```

### RabbitMQ 4.x — deprecated feature breaks Celery mingle

RabbitMQ 4.x denies the deprecated `transient_nonexcl_queues` feature by default, which Celery's `mingle` protocol (worker discovery on startup) relies on. Without explicitly permitting it, the worker crashes with `RestartFreqExceeded` and a `Feature 'transient_nonexcl_queues' is deprecated` error.

**Fix**: `rabbitmq.conf` is mounted into `/etc/rabbitmq/conf.d/` with:
```
deprecated_features.permit.transient_nonexcl_queues = true
```

### RabbitMQ volume must be recreated when credentials change

`RABBITMQ_DEFAULT_USER`/`PASSWORD` are only applied on the **first** initialization of the volume. If you change the password in `.env` after the container has already started — the old password stays in the volume. You need to:
```bash
docker-compose down
docker volume rm news-monitoring_rabbitmq_data
docker-compose up -d
```

### Windows + shell scripts mounted into a Linux container

- `rabbitmq-init.sh` must be saved with **LF** line endings, not CRLF (otherwise `bash: $'\r': command not found`). In VS Code — the toggle is in the bottom-right status bar.
- In the container's `command`, the script is invoked explicitly via `bash /rabbitmq-init.sh`, not `./rabbitmq-init.sh` — this works around the exec bit not being preserved correctly when mounting from NTFS into Linux.

### Celery on Windows

- `--pool=solo` is mandatory — the default `prefork` pool doesn't work on Windows.
- Tasks must be explicitly included via `include=["app.tasks.analysis_tasks"]` in `celery_app.py` — otherwise the worker won't know about the task (`Received unregistered task`), even if it exists in the code.
- After any change to task code or Celery configuration — **the worker must be restarted**, there is no auto-reload.

### asyncpg + Celery + asyncio.run() on Windows

Multiple calls to `asyncio.run()` across different Celery tasks **must not reuse the same global SQLAlchemy `engine`** — asyncpg connections are bound to the event loop they were created on. A second `asyncio.run()` call creates a new loop, and reusing the old engine causes `RuntimeError: Event loop is closed`.

**Fix**: a **local** engine is created inside the Celery task on every call, and is always released via `finally: await engine.dispose()`.

### httpx/groq client cleanup + asyncio.run() on Windows

Always use `AsyncGroq(...)` (and any other async SDK client built on top of `httpx.AsyncClient`) as an async context manager (`async with`), not as a bare object created and left to garbage collection. Without it, the SDK's internal HTTP client may finalize its connections in a background task scheduled via `call_soon`, which can run *after* `asyncio.run()` has already closed the event loop for that task — producing a noisy (but non-fatal) `RuntimeError: Event loop is closed` / `Task exception was never retrieved` in the worker logs. The task itself still succeeds; only the cleanup log is affected. Wrapping the client creation in `async with AsyncGroq(api_key=...) as client:` resolved this in our case.

### `.env` — general rules

- No quotes around values, no spaces around `=`.
- `pydantic-settings` strips quotes automatically when parsing — which is why the Docker Compose-side error went unnoticed for a long time on the Python side.
- `.env` must live in the project root (not in `app/core/`) — alongside `docker-compose.yml`, and relative to the working directory `uvicorn`/`celery` are launched from.

## TODO / next steps

- [ ] Celery Beat — periodic analysis runs based on `check_interval_minutes`
- [ ] Sentiment drift detection — comparison with the previous analysis
- [ ] Alerts + Telegram notifications (create a bot via `@BotFather`, get `chat_id`)
- [ ] Add Celery worker and Beat as services in `docker-compose.yml`
- [ ] Dockerfile for `api` (currently a placeholder `image: python:3.12-slim` without actually running the app)
- [ ] pytest tests (after functionality is complete)