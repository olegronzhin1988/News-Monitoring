# News Monitoring API

[![CI](https://github.com/olegronzhin1988/News-Monitoring/actions/workflows/ci.yml/badge.svg)](https://github.com/olegronzhin1988/News-Monitoring/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.138-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-4-FF6600?logo=rabbitmq&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-8.6-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-51%20passed-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

A learning project: an autonomous news monitoring service that tracks topics of interest, analyzes incoming articles with LLMs, detects significant sentiment shifts, and sends Telegram alerts — all without any manual interaction after initial setup.

Users create **subscriptions** for topics they want to follow (e.g. "Bitcoin", "Tesla", "The Beatles"). A scheduler picks up each subscription at its configured interval, fetches the latest news from NewsAPI, and sends the articles to an LLM (Groq with OpenRouter as fallback) for analysis. The LLM returns a sentiment score, a short summary, and a list of key events. Results are persisted to a PostgreSQL database, and if the sentiment has shifted significantly compared to the recent historical average, an alert is created and delivered to Telegram.

The entire pipeline runs asynchronously and fully containerized:

- **FastAPI** exposes a REST API for managing subscriptions (CRUD) with async SQLAlchemy 2.0 and Pydantic v2 for validation
- **Celery Beat** acts as the scheduler — every minute it checks which subscriptions are due for analysis and enqueues tasks
- **RabbitMQ** is the message broker — it holds the queue of incoming background tasks waiting to be processed
- **Celery Worker** consumes tasks from RabbitMQ and executes the actual pipeline: fetch → analyze → persist → alert
- **Redis** stores Celery task results (result backend)
- **PostgreSQL** is the primary database: subscriptions, analysis history, and alert records
- **Alembic** handles schema migrations
- **Groq / OpenRouter** provide LLM inference with automatic provider fallback
- **Telegram Bot API** delivers alerts when sentiment drift exceeds the configured threshold

The project was built progressively as a mentored learning exercise, going from a basic FastAPI CRUD service up through async ORM, multi-provider LLM orchestration, task queues, Docker Compose multi-service deployment, and a pytest suite with mocked external APIs and an isolated test database.

## Stack

- **FastAPI** + **SQLAlchemy 2.0 (async)** + **PostgreSQL** + **Alembic**
- **Celery** + **RabbitMQ** (broker) + **Redis** (result backend)
- **Groq** (primary LLM) + **OpenRouter** (fallback)
- **NewsAPI** — news source
- **Docker Compose** — infrastructure (postgres, redis, rabbitmq)

## Project structure

```
news-monitoring/
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions: spins up Postgres/Redis/RabbitMQ, runs pytest
├── docker-compose.yml
├── docker-compose.test.yml  # isolated Postgres for running tests locally
├── Dockerfile               # shared image for api / celery-worker / celery-beat
├── requirements.txt
├── requirements-test.txt
├── pytest.ini
├── TESTING.md
├── rabbitmq.conf
├── rabbitmq-init.sh
├── .env / .env.example
├── alembic/
├── tests/
│   ├── conftest.py
│   ├── test_subscriptions_api.py
│   ├── test_news_fetcher.py
│   ├── test_llm_analyzer.py
│   ├── test_telegram_notifier.py
│   ├── test_sentiment_drift.py
│   └── test_analysis_tasks.py
├── app/
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings), computed URLs
│   │   ├── database.py       # async engine, session, get_db dependency (for FastAPI)
│   │   └── celery_app.py     # Celery configuration, include with task modules
│   ├── models/
│   │   └── models.py          # SubscriptionsModel, NewsAnalysisModel, AlertsModel
│   ├── schemas/
│   │   └── subscription.py    # Pydantic schemas (Create/Update/Response)
│   ├── api/
│   │   └── subscriptions.py   # CRUD router for subscriptions
│   ├── services/
│   │   ├── news_fetcher.py     # NewsAPI integration (async httpx)
│   │   ├── llm_analyzer.py      # article analysis via Groq/OpenRouter with fallback
│   │   └── telegram_notifier.py # Telegram Bot API integration
│   └── tasks/
│       └── analysis_tasks.py    # Celery tasks: analyze_subscription, dispatch_due_analyses, send_pending_alerts
```

## Running

The whole stack — Postgres, Redis, RabbitMQ, the API, the Celery worker, and Celery Beat — now runs fully containerized via Docker Compose. No manual `uvicorn`/`celery` commands or extra terminals are needed.

1. Copy `.env.example` → `.env`, fill in real keys.
   **Important:** do NOT use quotes around values or spaces around `=` in `.env`.
   Correct: `RABBITMQ_USER=user`
   Incorrect: `RABBITMQ_USER = "user"` (breaks Docker Compose, even though pydantic silently tolerates it — a mismatch between how different consumers of the file parse it).

2. Build and start everything:
   ```bash
   docker-compose up -d --build
   ```

3. Apply migrations (one-off, run against the running `postgres` container):
   ```bash
   alembic upgrade head
   ```

4. Check it's alive:
   - API docs: `http://localhost:8000/docs`
   - RabbitMQ management UI: `http://localhost:15672`
   - Logs: `docker-compose logs -f api`, `docker-compose logs -f celery-worker`, `docker-compose logs -f celery-beat`

### Container networking — `localhost` vs service names

Inside the Docker network, services reach each other by **service name**, not `localhost`. `localhost` inside a container refers to that container itself, not its neighbors.

Because `.env` keeps `POSTGRES_HOST=localhost` / `REDIS_HOST=localhost` / `RABBITMQ_HOST=localhost` (useful for running the app directly on the host, outside Docker, during early development), the `api`, `celery-worker`, and `celery-beat` services override these three variables explicitly in `docker-compose.yml` via `environment:` (which takes precedence over `env_file:`):

```yaml
environment:
  POSTGRES_HOST: postgres
  REDIS_HOST: redis
  RABBITMQ_HOST: rabbitmq
```

If you change `environment:` values in `docker-compose.yml` without rebuilding the image, a plain `docker-compose up -d` may not pick up the change on already-running containers — use `docker-compose down && docker-compose up -d` (or `--force-recreate`) to be sure.

### Running outside Docker (optional, for quick local debugging)

If you ever need to run things directly on the host again (e.g. for fast iteration without rebuilding images):

```bash
uvicorn app.main:app --reload
celery -A app.core.celery_app worker --loglevel=info --pool=solo   # --pool=solo is mandatory on Windows
celery -A app.core.celery_app beat --loglevel=info
```

In that case `.env`'s `localhost` values are correct as-is, since the host reaches the containers through their published ports.

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

## Testing

A pytest suite covers the subscription CRUD API, `news_fetcher`, `llm_analyzer`
(including the Groq → OpenRouter fallback and JSON parsing edge cases),
`telegram_notifier`, sentiment drift detection, and the full async service
functions behind the three Celery tasks. External APIs (NewsAPI, Groq,
OpenRouter, Telegram) are always mocked; an isolated Postgres test database
(separate from the dev one) is used for everything that touches the DB.

```bash
pip install -r requirements.txt -r requirements-test.txt
docker-compose -f docker-compose.test.yml up -d
pytest
```

See `TESTING.md` for the full breakdown of what's covered, fixture design
notes, and a couple of documented gaps worth knowing about.

## CI

`.github/workflows/ci.yml` runs the same test suite on every push/PR to
`main`, using GitHub Actions' `services:` to spin up Postgres, Redis, and
RabbitMQ as sidecar containers for the job. All external third-party APIs
are mocked in the tests themselves, so CI needs no real API keys — only
harmless placeholder values to satisfy `pydantic-settings` at import time.

## TODO / next steps

- [x] Celery Beat — periodic analysis runs based on `check_interval_minutes`
- [x] Sentiment drift detection — comparison with the previous analysis
- [x] Alerts + Telegram notifications
- [x] Add Celery worker and Beat as services in `docker-compose.yml`
- [x] Dockerfile for `api` (shared by `api`, `celery-worker`, `celery-beat`)
- [x] pytest tests