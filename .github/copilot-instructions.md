# Project Coding Standards

## Domain
Agentic AI system for music exam booking and student advisory — modelled on Trinity College London.
Covers Classical & Jazz, Rock & Pop, Theory of Music — Grades 1–8.
Target users: students (18+), parents booking on behalf of children, exam center admins.

## Stack
- **Django 5** + DRF + SimpleJWT + django-axes — `core_service/` (port 8000), auth + transactional booking writes
- **FastAPI** + SQLModel + asyncpg — `fast_api_services/` (port 8001), all reads + AI agent layer
- **PostgreSQL 15** — primary database (shared by both services)
- **Redis** — slot gate (Lua atomic reservation), conversation session memory (TTL 30 min), rate limiting
- **ChromaDB** — local vector store for RAG (syllabus, policy, FAQ documents)
- **LangChain** + **Ollama LLaMA 3.1 8B** — ReAct agent, tool calling, advisory reasoning
- **Celery** + **Celery Beat** — background tasks (slot expiry, exam reminders, notifications)
- **React 18** + Vite + Material UI + Zustand + Axios — `frontend/` (port 3000), Nginx reverse proxy
- **docker-compose** — `deployment/docker-compose.yaml` orchestrates all services
- **k6** — load & performance tests (`k6/`)

### LLM interface rule
Always program against the LLM interface — never hardcode `ChatOllama` directly in business logic.
This allows swapping to Gemini Flash or GPT-4o-mini for production without changing tool/agent code:
```python
# GOOD: injected via dependency / config
llm = get_llm()  # returns ChatOllama locally, ChatGoogleGenerativeAI in prod

# BAD: hardcoded
llm = ChatOllama(model="llama3.1:8b")
```

## Testing
- Write tests before code (TDD); for bugs: failing test first, then fix
- Test hierarchy: unit > integration > e2e (use lowest level that captures behavior)
- Run tests before every commit

### FastAPI (fast_api_services/tests/)
- Framework: `pytest` + `pytest-asyncio` + `httpx.AsyncClient`
- Mock Redis with `fakeredis[aioredis]`; mock DB with `AsyncMock` or test DB
- Mock ChromaDB with in-memory collection for RAG tests
- Run: `pytest fast_api_services/tests/`

### Django (core_service/)
- Framework: `pytest-django`
- Unit tests: no real DB — use `@pytest.mark.django_db` only for integration tests
- Place test files adjacent to source: `core_service/bookings/tests/test_services.py`

### React (frontend/)
- Framework: Vitest + React Testing Library
- Run: `npm run test` inside `frontend/`

## Code Quality
- Review across five axes: correctness, readability, architecture, security, performance
- Python: `ruff check`, `mypy` for type checking
- TypeScript: `tsc --noEmit`, ESLint
- No secrets in code or version control — use `.env` files (never committed)

## Architecture Patterns

### Request flow
```
Client → Nginx (frontend/:3000)
         ├─ /api/auth/*      → Django core_service/:8000   (auth, JWT issue)
         ├─ /api/bookings/   → Django core_service/:8000   (transactional booking write)
         └─ /api/*           → FastAPI fast_api_services/:8001
                               ├─ GET  /catalog/courses    → PostgreSQL (instruments, grades, fees)
                               ├─ GET  /catalog/slots      → PostgreSQL + Redis cache
                               ├─ POST /agent/chat         → LangChain ReAct Agent (SSE stream)
                               │    ├─ tool: search_docs()         → ChromaDB RAG
                               │    ├─ tool: search_courses()      → PostgreSQL
                               │    ├─ tool: get_available_slots() → Redis-cached
                               │    ├─ tool: hold_slot()           → Redis Lua atomic
                               │    └─ tool: create_booking()      → Django via HTTP
                               └─ GET /bookings/           → PostgreSQL (student booking history)
```

### Auth
- Django issues JWT: `POST /api/auth/login/` → `accessToken` (short-lived) + `refreshToken`
- FastAPI validates JWT: shared `SECRET_KEY` env var, `HS256`, extracts `user_id` from `sub` claim
- `accessToken` kept **in memory only** (no XSS risk); `refreshToken` persisted to localStorage
- On app mount, existing `refreshToken` → call `refreshAccessToken()` → restore session
- Brute-force protection: django-axes + Nginx `auth` zone (5 req/min per IP)
- Roles: `STUDENT`, `PARENT`, `CENTER_ADMIN` — enforced at API boundary, not client-side

### Redis keys (slot gate)
- `slot:{slot_id}` — atomic slot counter (warmed on startup via `warm_all_slots()`)
- Lua script: `hold_slot(slot_id)` → 1 (held), 0 (fully booked), -1 (cache miss → DB fallback)
- `release_slot(slot_id)` — rollback on booking failure or TTL expiry
- `session:{user_id}` — conversation memory for LangChain agent (TTL 1800s)

### Agent & RAG patterns
- Agent uses **ReAct** (Reason + Act) loop; max tool call depth = 5 per turn
- **Confirmation gate** — agent MUST receive explicit `confirm=True` from user before calling any write tool:
  `create_booking()`, `cancel_booking()`, `reschedule_booking()`
- RAG chunk size: 500 tokens, overlap: 50 tokens
- `search_docs(query, doc_type?)` — `doc_type` one of `"syllabus"`, `"policy"`, `"faq"`, or `None` (all)
- Documents live in `docs/` — syllabus, policies, FAQ; indexed into ChromaDB at startup
- Embedding model: `nomic-embed-text` via Ollama (local, no external API call)

### Frontend state
- Zustand (`authStore`) persisted to localStorage: `refreshToken`; `accessToken` in memory only
- `examStore` — selected instrument, grade, style; current booking flow state
- `chatStore` — conversation history, streaming status, pending confirmation
- Axios (`api/client.js`) — auto-attach Bearer token, silent token refresh on 401
- Material UI components throughout; React Router v6 for routing

## Implementation
- Build in small, verifiable increments: implement → test → verify → commit
- Never mix formatting changes with behavior changes
- Slot reservation MUST use the Lua atomic pattern (never race-prone DB check-then-decrement)
- Django handles all writes that need transactions; FastAPI handles all reads and agent tools
- Agent tools are thin wrappers — business logic lives in the service/DB layer, not inside tool functions

## Boundaries
- **Always:** Run tests before commits, validate user input at system boundaries
- **Ask first:** Database schema changes (`makemigrations`), new `pip`/`npm` dependencies, changing LLM provider
- **Never:** Commit secrets, remove failing tests, skip verification, let agent write to DB without confirmation gate

## Skills
Load the relevant skill before starting work in these areas:

| Task | Skill |
|------|-------|
| Writing tests, fixing bugs, TDD | `.github/skills/test-driven-development/SKILL.md` |
| Security review, auth, input handling, secrets | `.github/skills/security-and-hardening/SKILL.md` |
| Code review, PR quality gate | `.github/skills/code-review-and-quality/SKILL.md` |
| Performance, load testing, profiling | `.github/skills/performance-optimization/SKILL.md` |
| Multi-file features, incremental changes | `.github/skills/incremental-implementation/SKILL.md` |
