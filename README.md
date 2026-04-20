# Trinity AI — Hệ thống Đặt lịch Thi Âm nhạc

Nền tảng AI tự động hỗ trợ đặt lịch thi và tư vấn học sinh cho các kỳ thi âm nhạc **Trinity College London** tại Việt Nam.

Học sinh (hoặc phụ huynh) trò chuyện bằng tiếng Việt với trợ lý AI. Trợ lý có thể tra cứu chương trình thi, kiểm tra lịch trống, giải thích chính sách — và đặt/hủy lịch thi sau khi người dùng xác nhận.

---

## Nghiệp vụ (Business)

### Đối tượng người dùng

| Vai trò | Mô tả |
|---------|-------|
| `STUDENT` | Học sinh từ 18 tuổi, tự đăng ký thi |
| `PARENT` | Phụ huynh đăng ký thay con |
| `CENTER_ADMIN` | Quản trị viên trung tâm thi |

### Luồng đặt lịch thi

```
1. Đăng nhập  →  2. Tìm kiếm slot  →  3. Trợ lý tư vấn  →  4. Xác nhận đặt lịch
                                                                        ↓
                                              Redis giữ chỗ (atomic Lua) 30 giây
                                                                        ↓
                                               Django tạo Booking trong DB
                                                                        ↓
                                              Celery gửi email xác nhận + nhắc thi
```

### Chương trình thi hỗ trợ

| Loại hình | Cấp độ |
|-----------|--------|
| **Classical & Jazz** (nhạc cổ điển & jazz) | Grade 1 → Grade 8 |
| **Rock & Pop** | Grade 1 → Grade 8 |
| **Theory of Music** (lý thuyết âm nhạc) | Grade 1 → Grade 8 |

### Quy tắc nghiệp vụ quan trọng

- **Xác nhận bắt buộc:** Trợ lý AI không được tự động đặt/hủy lịch. Phải nhận phản hồi `xác nhận` từ người dùng trước khi gọi bất kỳ thao tác ghi nào.
- **Giữ chỗ atomic:** Slot được giữ qua Lua script trên Redis — không xảy ra race condition dù nhiều người đặt cùng lúc.
- **JWT an toàn:** `accessToken` chỉ tồn tại trong bộ nhớ trình duyệt (không lưu localStorage) để chống XSS. `refreshToken` lưu localStorage và dùng để lấy lại `accessToken` khi hết hạn.
- **Bảo vệ brute-force:** django-axes chặn IP sau nhiều lần đăng nhập sai; Nginx giới hạn 5 req/phút cho `/api/auth/*`.

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Trình duyệt (React SPA)                       │
│   authStore (Zustand)  │  examStore  │  chatStore                    │
│   accessToken: memory  │  catalog    │  SSE stream messages          │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP / SSE
                         ▼
              ┌──────────────────┐
              │   Nginx (:80)    │  ← Reverse proxy + rate limiting
              └──┬───────────┬───┘
                 │           │
        /api/auth/*    /api/* + /
                 │           │
                 ▼           ▼
       ┌──────────────┐  ┌─────────────────────────────────────┐
       │ Django :8000 │  │         FastAPI :8001                │
       │              │  │                                      │
       │  • Đăng nhập │  │  • GET /catalog/courses             │
       │  • JWT issue  │  │  • GET /catalog/slots (Redis cache) │
       │  • Tạo/hủy   │  │  • GET /bookings/                   │
       │    booking    │  │  • POST /agent/chat  ──► SSE stream │
       │  • Migrations │  │         │                           │
       └──────┬───────┘  └─────────┼───────────────────────────┘
              │                    │
              ▼                    ▼
       ┌─────────────────────────────────┐
       │         PostgreSQL 15           │
       │  (Nguồn dữ liệu duy nhất)       │
       └─────────────────────────────────┘
              ▲                    ▲
              │                    │
       ┌──────┴──────┐    ┌────────┴──────────────────────────┐
       │  Celery     │    │  Redis 7                           │
       │  Worker     │    │  • slot:{id}  ← Lua atomic gate    │
       │  Beat       │    │  • session:{user_id} ← hội thoại  │
       │             │    │  • cache catalog/slots             │
       │  • Hủy slot │    └───────────────────────────────────┘
       │    hết hạn  │
       │  • Email    │    ┌───────────────────────────────────┐
       │    nhắc thi │    │  ChromaDB  (local vector store)   │
       └─────────────┘    │  • Syllabus Trinity               │
                          │  • Chính sách thi                 │
                          │  • FAQ                            │
                          └────────────┬──────────────────────┘
                                       │ nomic-embed-text
                                       ▼
                          ┌───────────────────────────────────┐
                          │  LLM backend (pluggable)          │
                          │  • Ollama LLaMA 3.1 8B (local)   │
                          │  • OpenAI gpt-4o-mini (prod)      │
                          │  • Google Gemini Flash (prod)     │
                          └───────────────────────────────────┘
```

### Phân tách trách nhiệm Django ↔ FastAPI

| Django (`core_service/`) | FastAPI (`fast_api_services/`) |
|--------------------------|-------------------------------|
| Xác thực & cấp JWT | Đọc dữ liệu catalog/bookings |
| Ghi booking (transaction) | AI Agent + SSE streaming |
| Django ORM migrations | ChromaDB RAG |
| Celery tasks | Redis slot cache |
| django-axes (brute-force) | Xác thực JWT (shared secret) |

---

## Trợ lý AI (Agent)

### Công cụ (Tools)

| Tool | Mô tả | Ghi/Đọc |
|------|-------|---------|
| `search_exam_docs` | Tìm kiếm trong syllabus, chính sách, FAQ qua ChromaDB | Đọc |
| `list_courses` | Danh sách môn thi, cấp độ, học phí | Đọc |
| `list_available_slots` | Slot còn chỗ trống (Redis-cached) | Đọc |
| `get_booking_detail` | Chi tiết một booking | Đọc |
| `list_my_bookings` | Lịch sử thi của học sinh | Đọc |
| `create_booking` | **Đặt lịch thi** — yêu cầu `confirm=True` | ⚠️ Ghi |
| `cancel_booking` | **Hủy lịch thi** — yêu cầu `confirm=True` | ⚠️ Ghi |

### Luồng xử lý Agent (ReAct)

```
Câu hỏi người dùng
        │
        ▼
  [Suy luận] Agent phân tích ý định
        │
        ├─► Cần tra thông tin? → search_exam_docs / list_courses / list_available_slots
        │
        ├─► Cần xem lịch thi? → list_my_bookings / get_booking_detail
        │
        └─► Muốn đặt/hủy?   → Trả về cảnh báo ⚠️ "Vui lòng xác nhận"
                                      │
                            Người dùng gõ "xác nhận"
                                      │
                                      ▼
                            create_booking / cancel_booking
                                      │
                            Redis Lua hold_slot()
                                      │
                            Django POST /api/bookings/create/
```

### SSE Events (streaming)

```json
{ "type": "token",      "content": "Dựa trên..." }
{ "type": "tool_start", "tool": "list_available_slots" }
{ "type": "tool_end",   "tool": "list_available_slots" }
{ "type": "done" }
{ "type": "error",      "content": "Lỗi kết nối..." }
```

---

## Cài đặt nhanh (Docker)

```bash
# 1. Clone repo
git clone https://github.com/your-org/trinity_ai.git
cd trinity_ai

# 2. Tạo file env
cp core_service/.env.example core_service/.env
cp fast_api_services/.env.example fast_api_services/.env
# Điền DB_PASSWORD, SECRET_KEY, JWT_SECRET_KEY vào cả 2 file

# 3. Khởi động toàn bộ hệ thống
cd deployment
docker compose up --build

# Ứng dụng chạy tại: http://localhost
# Lần đầu Ollama tự động tải LLaMA 3.1 8B (~5 GB) — mất vài phút
```

---

## Cài đặt môi trường Dev

### Django

```bash
cd core_service
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
cp .env.example .env            # điền biến môi trường

python manage.py migrate
python manage.py loaddata fixtures/initial_catalog.json fixtures/initial_centers.json
python manage.py runserver 8000
```

### FastAPI

```bash
cd fast_api_services
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

uvicorn main:app --reload --port 8001
```

### Frontend React

```bash
cd frontend
npm install
npm run dev     # → http://localhost:3000
```

### Celery

```bash
# Trong môi trường Django
celery -A core_service worker -l info -Q default
celery -A core_service beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Biến môi trường

### `core_service/.env`

| Biến | Mô tả | Ví dụ |
|------|-------|-------|
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `DEBUG` | Chế độ debug | `True` (dev) |
| `DB_NAME` | Tên database PostgreSQL | `trinity` |
| `DB_USER` | User PostgreSQL | `postgres` |
| `DB_PASSWORD` | Mật khẩu PostgreSQL | *(bắt buộc)* |
| `DB_HOST` | Host PostgreSQL | `localhost` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | URL broker Celery | `redis://localhost:6379/1` |
| `JWT_SECRET_KEY` | Khóa bí mật JWT dùng chung | *(bắt buộc, giống FastAPI)* |
| `ACCESS_TOKEN_LIFETIME_MINUTES` | Thời hạn access token | `15` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | Thời hạn refresh token | `7` |

### `fast_api_services/.env`

| Biến | Mô tả | Ví dụ |
|------|-------|-------|
| `DATABASE_URL` | SQLAlchemy async URL | `postgresql+asyncpg://postgres:pass@localhost/trinity` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | Khóa bí mật JWT dùng chung | *(giống Django)* |
| `LLM_PROVIDER` | Backend LLM | `ollama` (local) / `openai` / `google` |
| `LLM_MODEL` | Tên model | `llama3.1:8b` / `gpt-4o-mini` |
| `EMBEDDING_MODEL` | Model embedding | `nomic-embed-text` / `text-embedding-3-small` |
| `OLLAMA_BASE_URL` | URL server Ollama | `http://ollama:11434` (Docker) |
| `OPENAI_API_KEY` | API key OpenAI (dùng cho prod) | `sk-...` |
| `DJANGO_SERVICE_URL` | URL nội bộ Django | `http://django:8000` |
| `CHROMA_PERSIST_DIR` | Thư mục lưu ChromaDB | `./chromadb_data` |
| `DOCS_DIR` | Thư mục tài liệu RAG | `../docs` |

---

## Cấu trúc dự án

```
trinity_ai/
├── core_service/               Django 5 — xác thực + ghi booking
│   ├── accounts/               Model User, JWT config, django-axes
│   ├── bookings/               Model Booking, Celery tasks (nhắc thi, hủy slot)
│   ├── catalog/                Model Instrument, Grade, ExamSlot, ExamCenter
│   ├── fixtures/               Dữ liệu ban đầu (catalog, centers)
│   └── tests/                  11 pytest-django tests
│
├── fast_api_services/          FastAPI — đọc + AI agent
│   ├── agent/
│   │   ├── llm.py              get_llm() + get_embeddings() (hỗ trợ ollama/openai/google)
│   │   ├── rag.py              ChromaDB: index_docs(), search_docs()
│   │   ├── memory.py           Redis: lưu lịch sử hội thoại (TTL 30 phút)
│   │   ├── tools.py            7 LangChain tools + confirmation gate
│   │   └── agent.py            ReAct agent + system prompt tiếng Việt
│   ├── routers/
│   │   ├── catalog.py          GET /catalog/courses, /catalog/slots
│   │   ├── bookings.py         GET /bookings/
│   │   └── agent.py            POST /agent/chat (SSE EventSourceResponse)
│   ├── services/
│   │   └── slot_cache.py       Redis Lua atomic slot gate
│   └── tests/                  36 pytest-asyncio tests
│
├── frontend/                   React 18 + Vite + Material UI + Zustand
│   └── src/
│       ├── api/
│       │   ├── client.js       Axios + silent JWT refresh interceptor
│       │   └── index.js        Tất cả API calls (login, catalog, bookings, agent)
│       ├── stores/
│       │   ├── authStore.js    Zustand: accessToken (memory), refreshToken (localStorage)
│       │   ├── examStore.js    Zustand: trạng thái duyệt catalog
│       │   └── chatStore.js    Zustand: messages, streaming, pendingConfirm
│       ├── pages/
│       │   ├── LoginPage.jsx   Form đăng nhập (bằng email)
│       │   ├── RegisterPage.jsx Tạo tài khoản mới
│       │   ├── CatalogPage.jsx Danh mục kỳ thi + filter
│       │   ├── ChatPage.jsx    Giao diện chat SSE streaming (ChatGPT-style)
│       │   └── BookingsPage.jsx Lịch sử thi
│       └── components/
│           ├── Navbar.jsx
│           ├── ChatBubble.jsx  Avatar + full-width bot text, bubble user, blinking cursor
│           ├── ConfirmBanner.jsx Banner xác nhận trước khi đặt/hủy
│           └── ProtectedRoute.jsx Route guard kiểm tra auth
│
├── deployment/
│   ├── docker-compose.yaml     Orchestration: db, redis, ollama, django,
│   │                           fast_api, celery, celery-beat, frontend, nginx
│   └── nginx/nginx.conf        Reverse proxy + rate limiting
│
├── docs/                       Tài liệu RAG: syllabus, chính sách, FAQ
├── k6/                         Load test scripts
└── README.md                   Tài liệu này
```

---

## Chạy kiểm thử

```bash
# Django (11 tests)
cd core_service
pytest --no-header -q

# FastAPI (36 tests)
cd fast_api_services
pytest tests/ -v

# Frontend (19 tests)
cd frontend
npm test
```

Tổng: **47 backend tests** + **19 frontend tests** = **66 tests**

---

## Triển khai Production

| Hạng mục | Khuyến nghị |
|---------|-------------|
| **LLM** | Đổi `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini` |
| **Embedding** | `EMBEDDING_MODEL=text-embedding-3-small` |
| **TLS** | Thêm Certbot sidecar hoặc terminate TLS tại load balancer |
| **Secrets** | Dùng Docker Secrets hoặc Vault — không commit file `.env` |
| **GPU** | Thêm `deploy.resources.reservations.devices` vào service `ollama` để dùng CUDA |
| **Scaling** | FastAPI chạy nhiều replica; Django dùng gunicorn multi-worker |
| **Monitoring** | Prometheus + Grafana hoặc Sentry cho error tracking |


An agentic AI platform for Trinity College London music exam booking and student advisory.  
Students chat with a Vietnamese-language AI assistant to browse the syllabus, check available slots, and book exams — the agent reasons, calls tools, and asks for confirmation before any write.

---

## Architecture

```
Client (React SPA :3000)
        │
        ▼
    Nginx (:80)
   ┌────┴───────────────────────────┐
   │                                │
/api/auth/*               /api/* + /
   │                                │
   ▼                                ▼
Django :8000              FastAPI :8001
(auth, JWT, bookings)     (reads, AI agent, SSE)
   │                          │         │
PostgreSQL 15          Redis 7     ChromaDB
                               │
                           Ollama :11434
                         (LLaMA 3.1 8B + nomic-embed-text)
```

### Request flow

| Path | Service | Description |
|------|---------|-------------|
| `POST /api/auth/token/` | Django | Login — returns `access` + `refresh` JWT |
| `POST /api/auth/token/refresh/` | Django | Silent token refresh |
| `POST /api/bookings/create/` | Django | Transactional booking write |
| `GET /api/catalog/courses` | FastAPI | Instruments, grades, fees |
| `GET /api/catalog/slots` | FastAPI | Available exam slots (Redis-cached) |
| `GET /api/bookings/` | FastAPI | Student booking history |
| `POST /api/agent/chat` | FastAPI | AI chat — SSE stream of tokens/tool events |

### AI Agent

- **Framework:** LangChain ReAct (Reason + Act), max 5 tool calls per turn
- **Tools:** `search_exam_docs`, `list_courses`, `list_available_slots`, `get_booking_detail`, `list_my_bookings`, `create_booking`, `cancel_booking`
- **Confirmation gate:** `create_booking` and `cancel_booking` require the user to send `confirm=True` before execution
- **Memory:** Redis conversation history, TTL 30 min per session
- **RAG:** ChromaDB, 500-token chunks, `nomic-embed-text` embeddings, documents from `docs/`

### Redis slot gate

Atomic Lua script prevents race conditions on slot reservation:
- `hold_slot(slot_id)` → `1` (held) / `0` (full) / `-1` (cache miss → DB fallback)
- `release_slot(slot_id)` — rollback on booking failure

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker + Docker Compose | 24+ |
| Node.js | 20+ (frontend dev only) |
| Python | 3.12+ (backend dev only) |
| Ollama | Latest (local LLM, dev only — skip if using OpenAI) |

---

## Quick Start (Docker)

```bash
# 1. Clone
git clone https://github.com/your-org/trinity_ai.git
cd trinity_ai

# 2. Copy and fill env files
cp core_service/.env.example core_service/.env
cp fast_api_services/.env.example fast_api_services/.env
# Edit both files — set DB_PASSWORD, SECRET_KEY, JWT_SECRET_KEY

# 3. Start everything
cd deployment
docker compose up --build

# App is available at http://localhost
# (Ollama pulls LLaMA 3.1 8B on first start — ~5 GB, takes a few minutes)
```

---

## Development Setup

### Django (`core_service/`)

```bash
cd core_service
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env    # fill in values

python manage.py migrate
python manage.py loaddata fixtures/initial_catalog.json fixtures/initial_centers.json
python manage.py runserver 8000
```

Run tests:
```bash
pytest --no-header -q
```

### FastAPI (`fast_api_services/`)

```bash
cd fast_api_services
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in values

uvicorn main:app --reload --port 8001
```

Run tests:
```bash
pytest tests/ -v
```

### React frontend (`frontend/`)

```bash
cd frontend
npm install
npm run dev     # → http://localhost:3000
```

Run tests:
```bash
npm test
```

### Celery workers

```bash
# Worker
celery -A core_service worker -l info -Q default

# Beat scheduler
celery -A core_service beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Environment Variables

### `core_service/.env`

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `DEBUG` | Debug mode | `True` (dev) / `False` (prod) |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name | `trinity` |
| `DB_USER` | PostgreSQL user | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | *(required)* |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/1` |
| `JWT_SECRET_KEY` | Shared secret for JWT | *(required, same as FastAPI)* |
| `ACCESS_TOKEN_LIFETIME_MINUTES` | JWT access token TTL | `15` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | JWT refresh token TTL | `7` |

### `fast_api_services/.env`

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL | `postgresql+asyncpg://postgres:pass@localhost/trinity` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | Shared secret for JWT | *(same as Django)* |
| `LLM_PROVIDER` | LLM backend | `ollama` / `openai` / `google` |
| `LLM_MODEL` | Model name | `llama3.1:8b` / `gpt-4o-mini` |
| `EMBEDDING_MODEL` | Embedding model | `nomic-embed-text` / `text-embedding-3-small` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI key (if provider=openai) | `sk-...` |
| `GOOGLE_API_KEY` | Google key (if provider=google) | `...` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./chromadb_data` |
| `DOCS_DIR` | Path to RAG documents | `../docs` |

---

## API Reference

### Auth (Django)

```
POST /api/auth/token/            { email, password } → { access, refresh }
POST /api/auth/token/refresh/    { refresh } → { access }
POST /api/auth/register/         { email, password, role }
```

### Catalog (FastAPI)

```
GET  /api/catalog/courses        ?exam_type=classical_jazz&grade=3
GET  /api/catalog/slots          ?available_only=true&grade=3&exam_type=rock_pop
```

### Bookings (FastAPI reads / Django writes)

```
GET  /api/bookings/              List my bookings
GET  /api/bookings/{id}          Booking detail
POST /api/bookings/create/       { slot_id } → create booking (Django)
```

### Agent (FastAPI SSE)

```
POST /api/agent/chat
Body: { "message": "...", "session_id": "uuid" }

SSE events:
  { "type": "token",      "content": "..." }
  { "type": "tool_start", "tool": "list_courses" }
  { "type": "tool_end",   "tool": "list_courses" }
  { "type": "done" }
  { "type": "error",      "content": "..." }
```

---

## Project Structure

```
trinity_ai/
├── core_service/               Django 5 — auth + booking writes
│   ├── accounts/               User model, JWT config
│   ├── bookings/               Booking model, Celery tasks
│   ├── catalog/                Instrument, Grade, ExamSlot models
│   └── fixtures/               Initial data (catalog, centers)
│
├── fast_api_services/          FastAPI — reads + AI agent
│   ├── agent/
│   │   ├── llm.py              get_llm() + get_embeddings() (provider-agnostic)
│   │   ├── rag.py              ChromaDB indexing + semantic search
│   │   ├── memory.py           Redis conversation history
│   │   ├── tools.py            7 LangChain tools + confirmation gate
│   │   └── agent.py            ReAct agent + system prompt
│   ├── routers/
│   │   ├── catalog.py          GET /catalog/courses, /catalog/slots
│   │   ├── bookings.py         GET /bookings/
│   │   └── agent.py            POST /agent/chat (SSE)
│   ├── services/
│   │   └── slot_cache.py       Redis Lua slot gate
│   └── tests/                  36 pytest tests
│
├── frontend/                   React 18 + Vite + MUI + Zustand
│   └── src/
│       ├── api/                Axios client + API calls
│       ├── stores/             authStore, examStore, chatStore
│       ├── pages/              Login, Catalog, Chat, Bookings
│       └── components/         Navbar, ChatBubble, ConfirmBanner
│
├── deployment/
│   ├── docker-compose.yaml     All services orchestration
│   └── nginx/nginx.conf        Reverse proxy config
│
├── docs/                       RAG documents (syllabus, policy, FAQ)
└── k6/                         Load & performance tests
```

---

## Production Notes

- **LLM:** Switch to `LLM_PROVIDER=openai` + `LLM_MODEL=gpt-4o-mini` + `EMBEDDING_MODEL=text-embedding-3-small`
- **Secrets:** Store in environment variables or a secrets manager — never commit `.env` files
- **TLS:** Add a Certbot/Let's Encrypt sidecar or terminate TLS at your load balancer
- **Scaling:** FastAPI can run multiple replicas; Django uses gunicorn with multiple workers
- **GPU (Ollama):** Add `deploy.resources.reservations.devices` to the `ollama` service in docker-compose for CUDA access

---

## Running All Tests

```bash
# Django
cd core_service && pytest --no-header -q

# FastAPI
cd fast_api_services && pytest tests/ -v

# Frontend
cd frontend && npm test
```

Total: **47 backend tests** (11 Django + 36 FastAPI) + **19 frontend tests**
