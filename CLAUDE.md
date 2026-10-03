# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Trinity AI — agentic platform for Trinity College London music exam booking in Vietnam. Students/parents chat with a Vietnamese-language AI assistant to browse syllabi, check slots, and book exams. Center admins use batch scheduling with OR-Tools CP-SAT optimization.

## Architecture

```
React SPA (:3000) → Nginx (:80)
  ├─ /api/auth/*      → Django :8000   (auth, JWT, transactional writes)
  └─ /api/* (else)    → FastAPI :8001  (reads, AI agent SSE, catalog)
                          ├─ PostgreSQL 15
                          ├─ Redis 7 (slot gate, sessions, scheduling proposals)
                          ├─ ChromaDB (RAG: syllabus, policy, FAQ)
                          └─ Ollama :11434 (LLaMA 3.1 8B + nomic-embed-text)
```

**Two-service split:** Django handles all writes requiring transactions (bookings, auth, migrations). FastAPI handles all reads and the AI agent layer. They share the same PostgreSQL database and validate the same JWT (HS256, `user_id` claim).

**Agent routing:** `POST /api/agent/chat` → `SupervisorGraph` routes by `user_role`:
- `STUDENT`/`PARENT` → `BookingGraph` (ReAct agent: 10 tools with confirmation gate)
- `CENTER_ADMIN` → `SchedulingGraph` (LangGraph multi-node: classify → fetch → propose → execute)

**Confirmation gate:** The agent MUST receive explicit user confirmation (`xác nhận`/`confirm`) before calling any write tool (`create_booking`, `cancel_booking`, `pay_booking`, `reschedule_booking`, `assign_examiner_to_slot`, `confirm_schedule_plan`). Pending scheduling proposals persist in Redis (`proposal:{user_id}`, TTL 30 min). Booking/assignment writes are gated **server-side**: the model's `confirm` argument is never trusted — `authorize_write()` (`agent/authorization.py`) only allows a write when the user's raw message is an explicit confirmation AND its `(tool, args)` hash matches the `pending_action:{user_id}` recorded on a prior turn.

**Redis key layout:**
| DB | Key | Purpose |
|----|-----|---------|
| 0 | `slot:{id}` | Slot availability counter |
| 0 | `hold:{slot_id}` | TTL seat hold while user confirms (TTL `SLOT_HOLD_TTL_SECONDS`, default 900 s) |
| 0 | `session:{user_id}` | Conversation history (TTL 30 min) |
| 0 | `proposal:{user_id}` | Pending admin proposal (TTL 30 min) |
| 0 | `pending_action:{user_id}` | Write action awaiting user confirmation (server-side gate, TTL 30 min) |
| 0 | `schedule_task:{task_id}` | OR-Tools solver result (TTL 2 h) |
| 1 | — | Celery broker |
| 2 | — | Celery result backend |

**LLM provider abstraction:** Always inject via `get_llm()` — never hardcode a provider in business logic. Actual default config is **openai / `gpt-4o-mini`** + `text-embedding-3-small` (see `fast_api_services/.env`); ollama/openai/google are all supported. `get_llm()` applies timeout/retries; `get_classifier_llm()` adds structured output + optional fallback model.

## Common Commands

### Run services (dev)

```bash
# Django
cd core_service
pip install -r requirements.txt
cp .env.example .env        # fill DB_PASSWORD, SECRET_KEY, JWT_SECRET_KEY
python manage.py migrate
python manage.py loaddata fixtures/initial_catalog.json fixtures/initial_centers.json
python manage.py runserver 8000

# FastAPI
cd fast_api_services
pip install -r requirements.txt
cp .env.example .env        # fill DATABASE_URL, REDIS_URL, JWT_SECRET_KEY
uvicorn main:app --reload --port 8001

# Celery worker + beat (from core_service venv)
celery -A core_service worker -l info -Q default
celery -A core_service beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Frontend
cd frontend
npm install
npm run dev                  # → http://localhost:3000
```

### Run all via Docker

```bash
cd deployment
cp ../core_service/.env.example ../core_service/.env
cp ../fast_api_services/.env.example ../fast_api_services/.env
# Edit both .env files
docker compose up --build   # → http://localhost:8080
```

### Testing

```bash
# Django (pytest-django, SQLite in-memory, 83 tests)
cd core_service
pytest --no-header -q
# DJANGO_SETTINGS_MODULE=core_service.test_settings is set in pytest.ini / conftest

# FastAPI (pytest + pytest-asyncio + fakeredis, 94 tests)
cd fast_api_services
pytest tests/ -v
# Tests use fakeredis + AsyncMock DB — no real Redis/DB needed

# Frontend (Vitest + React Testing Library, 19 tests)
cd frontend
npm test

# Single test examples:
cd core_service && pytest bookings/tests/test_policies.py -q
cd fast_api_services && pytest tests/test_mock_features.py -v
```

### Linting & type checking

```bash
# Python
ruff check .                          # lint
mypy fast_api_services/               # type check (FastAPI)
mypy core_service/                    # type check (Django)

# Frontend
cd frontend
npx tsc --noEmit                      # TypeScript type check
npx eslint .                          # lint
```

## Key Source Layout

```
core_service/                  Django 5 — auth + transactional writes
├── accounts/                  User model, JWT config, django-axes; UserRole (STUDENT,
│                              PARENT, TEACHER, EXAMINER, CENTER_ADMIN, REGIONAL_ADMIN)
├── bookings/                  Booking model + payment/policy/candidate/result models
│   ├── models.py              Booking, Payment, CandidateDocument, ExamResult, Certificate
│   ├── payments.py            MockPaymentGateway (initiate/confirm/refund)
│   ├── policies.py            Cancellation/refund/reschedule windows (pure functions)
│   ├── serializers.py         Booking CRUD + policy enforcement + idempotency
│   └── tasks.py               Celery: expire_unpaid_holds
├── catalog/                   Instrument, Course (Grade, fee) models
├── centers/                   ExamCenter, Examiner, ExaminerUnavailability, ExamSlot;
│   ├── solver.py              OR-Tools CP-SAT solver (pure Python, no ORM)
│   ├── tasks.py               Celery task: solve_schedule_plan
│   └── views.py               BatchScheduleView, CenterReportView, AssignExaminerView
├── notifications/             MOCK email/SMS: Notification model, providers, tasks
├── auditing/                  AuditLog model + log_action() helper (append-only)
├── core_service/
│   ├── settings.py            Production settings (PostgreSQL) + policy/notification flags
│   └── test_settings.py       SQLite in-memory for tests (policy enforcement off)
└── fixtures/                  initial_catalog.json, initial_centers.json

fast_api_services/             FastAPI — reads + AI agent (SSE)
├── agent/
│   ├── agent.py               ReAct agent + Vietnamese system prompt
│   ├── tools.py               10 LangChain tools + ToolContext dataclass
│   ├── scheduling_tools.py   Admin tools (examiners, batch schedule, reschedule)
│   ├── supervisor.py          Top-level router: role → subgraph
│   ├── booking_graph.py       STUDENT/PARENT LangGraph wrapper
│   ├── scheduling_graph.py    CENTER_ADMIN: classify→fetch→propose→execute
│   ├── state.py               BookingState, SchedulingState TypedDicts + TaskType enum
│   ├── memory.py              Redis conversation history + pending_proposal/pending_action
│   ├── authorization.py       Server-side write gate (action_hash, authorize_write)
│   ├── grounding.py           Grounding guard (ungrounded-number detection)
│   ├── rag.py                 ChromaDB indexing + search_docs()
│   └── llm.py                 get_llm(), get_classifier_llm(), get_embeddings()
├── routers/
│   ├── agent.py               POST /agent/chat — SSE stream, _resume mechanism
│   ├── catalog.py             GET /catalog/courses, /catalog/slots
│   ├── bookings.py            GET/POST /bookings + pay/refund/documents/result
│   └── scheduling.py          GET /scheduling/examiners, /scheduling/calendar
├── services/
│   ├── slot_cache.py          Redis client + hold_slot/release_slot (TTL)
│   └── booking_service.py     Read-side booking queries (SQLAlchemy)
├── auth.py                    JWT validation (shared SECRET_KEY, HS256)
├── config.py                  Pydantic Settings (env-driven)
├── database.py                Async SQLAlchemy engine + session factory
└── tests/
    ├── conftest.py            fakeredis + AsyncMock DB + httpx AsyncClient
    └── test_*.py              All async tests against the real FastAPI app

frontend/                      React 18 + Vite + MUI + Zustand
└── src/
    ├── api/client.js          Axios + silent JWT refresh interceptor
    ├── stores/                authStore, examStore, chatStore (Zustand)
    ├── pages/                 Login, Register, Catalog, Chat, Bookings
    └── components/            Navbar, ChatBubble, ConfirmBanner, ProtectedRoute

deployment/
├── docker-compose.yaml        8 services: db, redis, django, fast_api, celery×2, frontend, nginx
└── nginx/nginx.conf           Reverse proxy + rate limiting
```

## Critical Patterns

### 1. Confirmation gate (agent write tools)
Write tools enforce `confirm=True`. The agent must ask the user "are you sure?" first. Example from `tools.py`:
```python
@tool
def create_booking(slot_id: int, confirm: bool = False):
    if not confirm:
        return _CONFIRM_REQUIRED
    # ... proceed with HTTP call to Django
```

### 2. Scheduling resume mechanism
When admin requests batch scheduling, the graph stores a `pending_proposal` in Redis. On the next turn, if the admin types "xác nhận", the router detects `_resume=True` and routes directly to `execute_node` — bypassing classify/fetch/propose entirely.

### 3. LLM interface
```python
# CORRECT — inject via dependency
llm = get_llm()   # returns ChatOllama locally, ChatOpenAI/ChatGoogleGenerativeAI in prod

# WRONG — hardcoded
llm = ChatOllama(model="llama3.1:8b")
```

### 4. Slot reservation
Concurrency-safe via `select_for_update()` in Django views. The FastAPI `slot_cache.py` provides Redis client access; slot availability queries go to the DB directly.

### 5. Auth flow
- Django issues JWT: `POST /api/auth/token/` → `access` + `refresh`
- FastAPI decodes the same JWT with shared `SECRET_KEY` (HS256, `user_id` claim)
- `accessToken` stored in JS memory only (no localStorage) to prevent XSS
- `refreshToken` in localStorage; Axios interceptor silently refreshes on 401

### 6. Server-side write authorization (P0)
Never trust the LLM's `confirm=True`. `authorize_write(ctx, tool, args, confirm)` (`agent/authorization.py`):
- When `ctx.authorized_actions` is a real `frozenset` (production), the write passes only if `action_hash(tool, args)` is in it. Otherwise the action is recorded in `pending_action:{user_id}` and refused.
- The router sets `authorized_actions` only when the user's raw message is an explicit confirmation AND a matching pending action exists.
- `action_hash` ignores the `confirm` key so the first (confirm=False) and second (confirm=True) calls share a signature.
- A `MagicMock`/unmanaged ctx falls back to the `confirm` flag (legacy/tests).

### 7. Structured intent classification (P0)
`SchedulingGraph.classify_node` prefers `get_classifier_llm()` → `with_structured_output(TaskType)` (no free-text parsing), with retry + optional fallback model. It falls back to the legacy text parse only if structured output is unavailable/fails.

### 8. Grounding guard (P0)
`agent/grounding.py` flags significant numbers (>= 4 digits) in the reply that do not appear in any tool output for that turn. `routers/agent.py` collects `tool_outputs` from `on_tool_end` and logs violations; set `GROUNDING_GUARD_STRICT=true` to replace the reply with a safe message. Toggle via `GROUNDING_GUARD_ENABLED`.

## Django App: centers

The `centers` app contains model definitions in `centers/models.py`. Serializers, views, and URLs are also under `centers/`. The batch scheduling flow is:

1. Admin sends chat message → FastAPI `classify_node` detects batch scheduling intent
2. `fetch_node` calls `auto_plan_schedule` → Django `POST /api/centers/schedule/batch/` → Celery task
3. Celery task runs `solver.solve()` (OR-Tools CP-SAT), writes result to Redis `schedule_task:{task_id}`
4. FastAPI polls Redis up to 15× (1 s intervals) → streams plan to admin
5. Admin confirms → Django commits assignments in bulk

## Important Boundaries

- **Always run tests before committing.** Django tests use `DJANGO_SETTINGS_MODULE=core_service.test_settings` (SQLite in-memory).
- **Ask before:** DB schema changes (`makemigrations`), new pip/npm dependencies, changing LLM provider.
- **Never:** commit `.env` files or secrets, let the agent write to DB without confirmation gate, skip the Lua/select_for_update pattern for slot reservation.
- **Build in small increments:** implement → test → verify → commit. Keep formatting and behavior changes in separate commits.
- **Top-level `docs/` is read-only RAG data** — mounted into the FastAPI container as `/app/docs:ro`.
