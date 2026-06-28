# Running the test suite

## 1. Install test dependencies

```bash
pip install -r requirements.txt -r requirements-test.txt
```

## 2. Start the isolated test database

This uses a **separate** Postgres container (port 5433 on the host, ephemeral
`tmpfs` storage) so it never touches your development data or volume.

```bash
docker-compose -f docker-compose.test.yml up -d
```

## 3. Run the tests

From the project root:

```bash
pytest
```

To run a single file or test:

```bash
pytest tests/test_sentiment_drift.py
pytest tests/test_subscriptions_api.py::test_create_subscription_returns_201_with_full_payload
```

## 4. Stop the test database when done

```bash
docker-compose -f docker-compose.test.yml down -v
```

---

## What's covered

| File | What it tests | DB? | Mocked? |
|---|---|---|---|
| `test_subscriptions_api.py` | `/subscriptions` CRUD endpoints (incl. 404s, PATCH partial-update semantics) | yes (via test client) | no external APIs involved |
| `test_news_fetcher.py` | `fetch_news` — success, `[Removed]` filtering, 401/429/5xx handling, API-level error field | no | NewsAPI (httpx) |
| `test_llm_analyzer.py` | `_parse_llm_response` (markdown fences, trailing text, no-JSON), `_build_prompt` truncation, Groq→OpenRouter fallback, both-fail case | no | Groq, OpenRouter |
| `test_telegram_notifier.py` | success / non-200 / network exception | no | Telegram Bot API |
| `test_sentiment_drift.py` | `_check_sentiment_drift` — first analysis, no-drift, drop, spike, 24h average baseline, fallback to last analysis outside the window, per-subscription isolation | yes | no |
| `test_analysis_tasks.py` | Full service functions behind the three Celery tasks: `_analyze_subscription_async`, `_dispatch_due_analyses_async`, `_send_pending_alerts_async` | yes | NewsAPI, LLM, Telegram |

## Notes for review

- `_call_groq` and `_call_openrouter` are mocked directly at the
  `app.services.llm_analyzer` module boundary rather than mocking deeper into
  the `groq`/`httpx` SDKs — this keeps the tests stable across SDK version
  changes and only tests *our* fallback/parsing logic.
- `test_telegram_notifier.py::test_propagates_network_level_exceptions`
  documents a real gap: `send_telegram_message` currently only handles
  non-200 HTTP responses, not network-level exceptions (timeouts, connection
  errors). If you want it to degrade gracefully on those too, wrap the
  `httpx` call in a `try/except` and update that test accordingly.
- The Celery task wrappers themselves (`analyze_subscription_task`,
  `dispatch_due_analyses_task`, `send_pending_alerts_task` — the
  `asyncio.run(...)` entry points) are intentionally **not** unit-tested
  directly, since `asyncio.run()` inside a test runner that already has an
  event loop running is awkward to test reliably. Instead, the underlying
  `_*_async` functions are tested directly, which covers all real logic;
  the wrappers are a thin, low-risk pass-through.
- `docker-compose.test.yml` reuses `POSTGRES_USER`/`POSTGRES_PASSWORD` from
  your existing `.env` (same credentials, different database name and port),
  so no extra secrets are needed.
