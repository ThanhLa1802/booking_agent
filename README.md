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

### Luồng đặt lịch thi (STUDENT / PARENT)

```
1. Đăng nhập  →  2. Tìm kiếm slot  →  3. Trợ lý tư vấn  →  4. Xác nhận đặt lịch
                                                                        ↓
                                              Redis giữ chỗ (atomic Lua) 30 giây
                                                                        ↓
                                               Django tạo Booking trong DB
                                                                        ↓
                                              Celery gửi email xác nhận + nhắc thi
```

### Luồng xếp lịch hàng loạt (CENTER_ADMIN)

```
Admin gõ "xếp lịch thi tháng 5"  →  FastAPI nhận yêu cầu
                                           ↓
                           Agent phát hiện ý định batch scheduling
                                           ↓
               ⏳ Phản hồi ngay: "Đang xếp lịch, vui lòng đợi..."
                                           ↓
            Django POST /api/centers/schedule/batch/ → Celery task
                                           ↓
              OR-Tools CP-SAT solver (tối ưu phân công giám khảo)
                                           ↓
            Kết quả lưu Redis schedule_task:{task_id} (TTL 2h)
                                           ↓
               FastAPI poll Redis 15 lần × 1s → đọc kế hoạch
                                           ↓
            Hiển thị bảng kế hoạch cho admin + yêu cầu xác nhận
                                           ↓
              Admin gõ "xác nhận"  →  Django ghi vào DB hàng loạt
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
       │    hết hạn  │         DB 0: slot gate, session,
       │  • Email    │              schedule_task:{id} (2h)
       │    nhắc thi │         DB 1: Celery broker
       │  • Xếp lịch │         DB 2: Celery result backend
       │    tối ưu   │
       │  (OR-Tools  │    ┌───────────────────────────────────┐
       │   CP-SAT)   │    │  ChromaDB  (local vector store)   │
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
| Xếp lịch hàng loạt (batch) | Scheduling Agent (LangGraph) |
| Celery: OR-Tools CP-SAT solver | Redis slot cache + schedule poll |
| Django ORM migrations | ChromaDB RAG |
| django-axes (brute-force) | Xác thực JWT (shared secret) |

---

## Trợ lý AI (Agent)

### Công cụ — Student / Parent

| Tool | Mô tả | Ghi/Đọc |
|------|-------|--------|
| `search_exam_docs` | Tìm kiếm trong syllabus, chính sách, FAQ qua ChromaDB | Đọc |
| `list_courses` | Danh sách môn thi, cấp độ, học phí | Đọc |
| `list_available_slots` | Slot còn chỗ trống | Đọc |
| `get_booking_detail` | Chi tiết một booking | Đọc |
| `list_my_bookings` | Lịch sử thi của học sinh | Đọc |
| `suggest_slots_for_reschedule` | Gợi ý slot thay thế cho một booking | Đọc |
| `create_booking` | **Đặt lịch thi** — xác nhận server-side bắt buộc | ⚠️ Ghi |
| `cancel_booking` | **Hủy lịch thi** — xác nhận server-side bắt buộc | ⚠️ Ghi |
| `pay_booking` | **Thanh toán (MOCK)** — xác nhận server-side bắt buộc | ⚠️ Ghi |
| `reschedule_booking` | **Đổi lịch thi** — xác nhận server-side bắt buộc | ⚠️ Ghi |

### Công cụ — CENTER_ADMIN (Scheduling Agent)

| Tool | Mô tả | Ghi/Đọc |
|------|-------|--------|
| `list_examiners` | Danh sách giám khảo của trung tâm (kèm tải trong ngày) | Đọc |
| `suggest_examiners_for_slot` | Gợi ý giám khảo phù hợp cho một slot | Đọc |
| `search_available_slots` | Tìm slot trống | Đọc |
| `get_exam_calendar` | Xem lịch thi theo khoảng ngày | Đọc |
| `get_examiner_schedule` | Xem lịch riêng của một giám khảo | Đọc |
| `auto_plan_schedule` | Gọi Celery solver → poll Redis → trả về kế hoạch tối ưu | Đọc |
| `assign_examiner_to_slot` | Phân công giám khảo vào một slot — xác nhận server-side | ⚠️ Ghi |
| `confirm_schedule_plan` | Lưu toàn bộ kế hoạch đã đề xuất vào DB | ⚠️ Ghi |
| `suggest_slots_for_reschedule` / `reschedule_booking` | Đổi lịch thí sinh | Đọc / ⚠️ Ghi |

### Luồng xử lý Agent — Student/Parent (ReAct)

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

### Luồng xử lý Agent — CENTER_ADMIN (LangGraph multi-node)

```
Admin gõ "xếp lịch thi tháng 5 2026"
        │
        ▼
  classify_node — phân loại: batch_assign / assign_single / view_calendar / general
        │
        ▼
  fetch_node — gọi auto_plan_schedule() hoặc view_exam_calendar()
               (auto_plan_schedule: dispatch Celery task → poll Redis 15s)
        │
        ▼
  propose_node — hiển thị kế hoạch từ DB (verbatim, không qua LLM)
               → lưu pending_proposal vào Redis
               → kết thúc lượt, trả SSE về frontend
        │
    [Turn mới: admin gõ "xác nhận"]
        │
        ▼
  execute_node — đọc pending_proposal từ Redis
               → gọi Django POST /api/centers/schedule/confirm/
               → lưu lịch vào DB hàng loạt
```

> **Cơ chế resume:** `pending_proposal` được lưu trong Redis (TTL 30 phút). Khi admin gửi "xác nhận" ở lượt tiếp theo, agent router phát hiện `_resume=True` và đưa thẳng vào `execute_node` — bỏ qua lại toàn bộ pipeline fetch/propose.

### SSE Events (streaming)

```json
{ "type": "token",      "content": "Dựa trên..." }
{ "type": "tool_start", "tool": "list_available_slots" }
{ "type": "tool_end",   "tool": "list_available_slots" }
{ "type": "done",       "content": "<toàn bộ nội dung cuối cùng>" }
{ "type": "error",      "content": "Lỗi kết nối..." }
```

> **Lưu ý:** Frontend ưu tiên `done.content` để ghi đè nội dung streaming. Điều này đảm bảo thông báo "⏳ Đang xếp lịch..." ban đầu được thay thế hoàn toàn bằng bảng kế hoạch thực tế khi phản hồi đến.

---

## Tính năng MOCK (ghép nối sau)

Các phần dưới đây đã có đủ model/endpoint/flow nhưng **provider thật chưa nối**:

| Nhóm | Trạng thái | Điểm ghép nối |
|------|-----------|----------------|
| **Thanh toán** | `MockPaymentGateway` (initiate/confirm/refund), booking có `PENDING_PAYMENT`/`PAID` | `bookings/payments.py` → thay bằng VNPay/MoMo/ZaloPay/Stripe |
| **Giữ chỗ** | `hold_slot`/`release_slot` Redis TTL + `hold_expires_at` trên Booking | `fast_api_services/services/slot_cache.py` |
| **Hết hạn chưa thanh toán** | Celery `expire_unpaid_holds` (beat 5 phút) | `bookings/tasks.py` |
| **Thông báo** | `Notification` model + provider log-only, task gửi + nhắc thi | `notifications/providers.py` → SMTP/Twilio/FCM |
| **Chính sách hủy/đổi/hoàn** | Hàm thuần trong `bookings/policies.py` (số liệu placeholder) | cập nhật theo policy Trinity VN thật |
| **Hồ sơ thí sinh** | Thêm field + `CandidateDocument` (upload chỉ lưu `file_ref`) | `bookings/views.py` → storage thật |
| **Kết quả/chứng chỉ** | `ExamResult` + `Certificate`, endpoint publish | `bookings/views.py` |
| **Audit log** | `AuditLog` append-only + `log_action()` | `auditing/services.py` |
| **Vai trò** | Thêm `TEACHER`, `EXAMINER`, `REGIONAL_ADMIN`; `Examiner.user` liên kết login | `accounts/models.py`, `centers/models.py` |

## AI Engineering (P0)

> **Provider LLM mặc định:** `openai` / `gpt-4o-mini` + `text-embedding-3-small` (xem `fast_api_services/.env`). Ollama LLaMA 3.1 8B + `nomic-embed-text` là nhánh local/fallback khi `LLM_PROVIDER=ollama`.

- **Server-side write authorization:** không tin `confirm=True` của LLM. `agent/authorization.py` chỉ cho ghi khi tin nhắn thô của user là xác nhận rõ ràng và khớp hash của `pending_action:{user_id}` ghi ở lượt trước.
- **Structured intent classification:** `get_classifier_llm()` dùng `with_structured_output(TaskType)` + retry + fallback model; chỉ fallback về parse text nếu provider không hỗ trợ.
- **LLM resilience:** `get_llm()` áp timeout/retries; cấu hình `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_FALLBACK_PROVIDER`, `LLM_FALLBACK_MODEL`.
- **Grounding guard:** `agent/grounding.py` phát hiện số liệu (>= 4 chữ số) trong câu trả lời không xuất hiện trong tool output; log cảnh báo, `GROUNDING_GUARD_STRICT=true` để thay bằng câu an toàn.

---

## Hướng dẫn chạy đầy đủ (Full Run Guide)

Hai cách: **Docker Compose** (mọi thứ trong container — khuyến nghị) hoặc **local dev** (tách tiến trình để phát triển).

### 0. Yêu cầu hệ thống

| Công cụ | Phiên bản | Dùng cho |
|---------|-----------|----------|
| Docker + Docker Compose | 24+ | Cách A (khuyến nghị); hạ tầng DB/Redis cho cách B |
| Python | 3.12+ | Django + FastAPI (cách B) |
| Node.js | 20+ | Frontend (cách B) |
| PostgreSQL | 15 | Cách B (nếu không dùng Docker cho DB) |
| Redis | 7 | Cách B (nếu không dùng Docker cho Redis) |

### 1. Biến môi trường (bắt buộc)

```bash
cp core_service/.env.example core_service/.env
cp fast_api_services/.env.example fast_api_services/.env
```

- **`SECRET_KEY` phải GIỐNG NHAU ở cả hai file.** Django ký JWT bằng `SECRET_KEY` (`core_service/core_service/settings.py:123` → `SIMPLE_JWT.SIGNING_KEY`); FastAPI xác thực bằng cùng key (`fast_api_services/config.py`). Lệch key → mọi request cần auth trả `401 Invalid or expired token`.
  Sinh key: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
  FastAPI từ chối khởi động nếu `SECRET_KEY` còn là giá trị mặc định.
- **`core_service/.env`**: đặt `SECRET_KEY`, `DB_*`, `REDIS_URL`, `CELERY_*`.
- **`fast_api_services/.env`**: đặt `SECRET_KEY` (giống trên), `DATABASE_URL`, `REDIS_URL`, `LLM_PROVIDER` + key tương ứng (`OPENAI_API_KEY` là mặc định).

> Không có biến `JWT_SECRET_KEY` — khóa dùng chung chính là `SECRET_KEY` ở cả hai service.

### Cách A — Docker Compose (chạy toàn bộ hệ thống)

```bash
cd deployment
docker compose up --build          # lần đầu build image (vài phút)
# hoặc chạy nền: docker compose up -d --build
```

Compose khởi động: `db`, `redis`, `django`, `celery`, `celery-beat`, `fast_api`, `frontend`, `nginx`.

> **Không có service Ollama.** LLM mặc định là OpenAI (`LLM_PROVIDER=openai`) nên cần `OPENAI_API_KEY`; muốn dùng local thì trỏ `OLLAMA_BASE_URL` tới một Ollama chạy sẵn và đặt `LLM_PROVIDER=ollama`.

Vì Postgres trong compose tạo bằng `${DB_NAME:-trinity_dev}` / `${DB_USER:-postgres}` / `${DB_PASSWORD:-postgres}`, khi chạy Docker hãy đặt hai file `.env` khớp với host nội bộ `db`:

```dotenv
# core_service/.env
SECRET_KEY=<random-giống-fastapi>
DB_NAME=trinity_dev
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,django,nginx

# fast_api_services/.env
SECRET_KEY=<random-giống-django>
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/trinity_dev
REDIS_URL=redis://redis:6379/0
DJANGO_SERVICE_URL=http://django:8000
```

Container `django` tự động chạy khi khởi động: `migrate` → `collectstatic` → `loaddata` catalog/centers (chỉ lần đầu, nếu chưa có center) → `gunicorn`.

**Truy cập:**

| Mục | URL |
|-----|-----|
| Ứng dụng (React qua Nginx) | http://localhost:8080 |
| Django admin | http://localhost:8080/admin/ |
| Nginx health (→ Django) | http://localhost:8080/api/health/ |
| FastAPI trực tiếp | http://localhost:8001 · `/health` · `/docs` |

**Tạo tài khoản + dữ liệu demo** (sau khi `docker compose ps` báo healthy):

```bash
cd deployment
docker compose exec django python manage.py createsuperuser   # tài khoản đăng nhập Django/admin
docker compose exec django python manage.py seed_scheduling   # superadmin / Admin@1234 + giám khảo + slot mẫu
# tùy chọn: seed_slots, seed_examiners
```

**Vận hành:**

```bash
docker compose logs -f django fast_api     # xem log
docker compose ps                          # trạng thái + health
docker compose restart fast_api            # FastAPI mount code read-only + --reload nên tự nạp, restart khi cần
docker compose down                        # dừng, giữ volume
docker compose down -v                      # dừng + xóa DB/Redis (reset sạch)
```

### Cách B — Local dev (tách tiến trình)

Thứ tự khởi động: **DB/Redis → Django → Celery → FastAPI → Frontend**. Hai service tách tiến trình nhưng **chung DB và chung `SECRET_KEY`**.

**1) Hạ tầng (Postgres + Redis) bằng Docker:**

```bash
cd deployment
docker compose up -d db redis
```

Dùng `.env.example` (mặc định `DB_HOST=localhost`, `DB_NAME=trinity_db`, cổng host `5432`). Nếu đổi, cập nhật cả hai file `.env` cho khớp.

**2) Django (`core_service/`):**

```bash
cd core_service
python -m venv .venv
.venv\Scripts\activate                 # Windows; Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                   # sửa SECRET_KEY, DB_*, REDIS_URL
python manage.py migrate
python manage.py loaddata fixtures/initial_catalog.json fixtures/initial_centers.json
python manage.py createsuperuser       # tạo tài khoản để đăng nhập
python manage.py runserver 8000        # http://localhost:8000
```

**3) Celery (2 terminal, cùng venv Django):**

```bash
python -m celery -A core_service worker -l info -Q default
python -m celery -A core_service beat   -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**4) FastAPI (`fast_api_services/`):**

```bash
cd fast_api_services
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                   # SECRET_KEY giống Django; DATABASE_URL trỏ localhost; OPENAI_API_KEY
uvicorn main:app --reload --port 8001  # http://localhost:8001
```

**5) Frontend (`frontend/`):**

```bash
cd frontend
npm install
npm run dev                            # http://localhost:3000
```

Vite proxy sẵn (`frontend/vite.config.js`): `/api/auth` → `:8000` (Django), mọi `/api` khác → `:8001` (FastAPI).

### 2. Xác minh nhanh

```bash
# Health
curl http://localhost:8001/health                 # FastAPI
curl http://localhost:8080/api/health/            # Docker: Nginx → Django (local dev: http://localhost:8000/api/health/)

# Đăng nhập lấy JWT — LoginView nhận EMAIL + password
curl -X POST http://localhost:8080/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"<email>","password":"<mat-khau>"}'
# → { "access": "...", "refresh": "..." }

# Gọi agent (SSE) — dán access token ở trên
curl -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access>" \
  -d '{"message":"Có những khóa Classical & Jazz nào?"}'
```

### 3. Lỗi thường gặp

| Triệu chứng | Nguyên nhân / cách sửa |
|-------------|------------------------|
| `SECRET_KEY is set to the insecure default value` | Chưa đặt `SECRET_KEY` thật trong `fast_api_services/.env` |
| Agent/bookings trả `401 Invalid or expired token` | `SECRET_KEY` hai service khác nhau — đặt giống nhau |
| Django báo không kết nối được DB (Docker) | `DB_NAME/DB_USER/DB_PASSWORD` trong `core_service/.env` phải khớp Postgres của compose, `DB_HOST=db` |
| Agent trả lỗi LLM | Thiếu `OPENAI_API_KEY`, hoặc `OLLAMA_BASE_URL` chưa trỏ tới Ollama đang chạy |
| `502` qua Nginx sau khi restart container | Chờ healthcheck xanh; Nginx tự re-resolve DNS (30s) |
| Cổng đã bị chiếm | 5432/6379/8000/8001/8080 đang dùng bởi tiến trình khác |

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
| `SECRET_KEY` | Khóa bí mật Django **và** ký JWT (dùng chung với FastAPI) | `django-insecure-...` |
| `ACCESS_TOKEN_LIFETIME_MINUTES` | Thời hạn access token | `15` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | Thời hạn refresh token | `7` |
| `PAYMENT_PROVIDER` | Provider thanh toán (MOCK) | `MOCK` |
| `BOOKING_HOLD_TTL_SECONDS` | Thời gian giữ chỗ chờ thanh toán | `900` |
| `CANCEL_FULL_REFUND_DAYS` / `CANCEL_PARTIAL_REFUND_DAYS` / `CANCEL_PARTIAL_REFUND_PCT` | Cửa sổ hoàn tiền | `30` / `7` / `50` |
| `RESCHEDULE_DEADLINE_DAYS` / `MAX_RESCHEDULES` | Hạn & số lần đổi lịch | `7` / `2` |
| `BOOKING_POLICY_ENFORCED` | Bật thực thi chính sách | `true` |
| `NOTIFICATIONS_ENABLED` / `NOTIFICATIONS_DISPATCH_ENABLED` | Bật tạo/gửi thông báo (MOCK) | `true` / `true` |

### `fast_api_services/.env`

| Biến | Mô tả | Ví dụ |
|------|-------|-------|
| `DATABASE_URL` | SQLAlchemy async URL | `postgresql+asyncpg://postgres:pass@localhost/trinity` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `SECRET_KEY` | Khóa xác thực JWT — **phải giống `core_service/.env`** | *(bắt buộc)* |
| `LLM_PROVIDER` | Backend LLM | `ollama` (local) / `openai` / `google` |
| `LLM_MODEL` | Tên model | `llama3.1:8b` / `gpt-4o-mini` |
| `EMBEDDING_MODEL` | Model embedding | `nomic-embed-text` / `text-embedding-3-small` |
| `OLLAMA_BASE_URL` | URL server Ollama | `http://ollama:11434` (Docker) |
| `OPENAI_API_KEY` | API key OpenAI (dùng cho prod) | `sk-...` |
| `DJANGO_SERVICE_URL` | URL nội bộ Django | `http://django:8000` |
| `CHROMA_PERSIST_DIR` | Thư mục lưu ChromaDB | `./chromadb_data` |
| `DOCS_DIR` | Thư mục tài liệu RAG | `../docs` |
| `LLM_TIMEOUT_SECONDS` | Timeout gọi LLM (giây) | `30` |
| `LLM_MAX_RETRIES` | Số lần retry LLM | `2` |
| `LLM_FALLBACK_PROVIDER` / `LLM_FALLBACK_MODEL` | Model dự phòng (rỗng = tắt) | `openai` / `gpt-4o-mini` |
| `SLOT_HOLD_TTL_SECONDS` | TTL giữ chỗ Redis | `900` |
| `GROUNDING_GUARD_ENABLED` / `GROUNDING_GUARD_STRICT` | Bật/độ nghiêm grounding guard | `true` / `false` |

---

## Cấu trúc dự án

```
trinity_ai/
├── core_service/               Django 5 — xác thực + ghi booking
│   ├── accounts/               Model User, JWT config, django-axes
│   ├── bookings/               Model Booking, Celery tasks (nhắc thi, hủy slot)
│   ├── catalog/                Model Instrument, Grade, ExamSlot, ExamCenter
│   ├── centers/                ExamCenter, Examiner; BatchScheduleView;
│   │                           Celery task solve_schedule_plan (OR-Tools CP-SAT)
│   ├── fixtures/               Dữ liệu ban đầu (catalog, centers)
│   └── tests/                  11 pytest-django tests
│
├── fast_api_services/          FastAPI — đọc + AI agent
│   ├── agent/
│   │   ├── llm.py              get_llm() + get_embeddings() (hỗ trợ ollama/openai/google)
│   │   ├── rag.py              ChromaDB: index_docs(), search_docs()
│   │   ├── memory.py           Redis: hội thoại (TTL 30') + pending_proposal
│   │   ├── tools.py            7 LangChain tools (student/parent) + confirmation gate
│   │   ├── scheduling_tools.py Scheduling tools cho CENTER_ADMIN
│   │   ├── scheduling_graph.py LangGraph: classify→fetch→propose→execute
│   │   ├── booking_graph.py    LangGraph: booking/cancel flow cho student
│   │   ├── supervisor.py       Multi-agent supervisor (routing theo role)
│   │   ├── state.py            Shared state schemas
│   │   └── agent.py            ReAct agent + system prompt tiếng Việt
│   ├── routers/
│   │   ├── catalog.py          GET /catalog/courses, /catalog/slots
│   │   ├── bookings.py         GET /bookings/
│   │   ├── scheduling.py       GET /scheduling/examiners, /scheduling/calendar
│   │   └── agent.py            POST /agent/chat (SSE) — _resume mechanism
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
│           │                   Hỗ trợ Markdown (bảng, in đậm, danh sách)
│           ├── ConfirmBanner.jsx Banner xác nhận trước khi đặt/hủy/lưu lịch
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
# Django (83 tests)
cd core_service
pytest --no-header -q

# FastAPI (94 tests)
cd fast_api_services
pytest tests/ -v

# Frontend (19 tests)
cd frontend
npm test
```

Tổng: **177 backend tests** + **19 frontend tests** = **196 tests**

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

**Student / Parent — ReAct agent**
- **Framework:** LangChain ReAct (Reason + Act), max 5 tool calls per turn
- **Tools:** `search_exam_docs`, `list_courses`, `list_available_slots`, `get_booking_detail`, `list_my_bookings`, `create_booking`, `cancel_booking`
- **Confirmation gate:** `create_booking` and `cancel_booking` require explicit `confirm` from the user before execution
- **Memory:** Redis conversation history, TTL 30 min per session
- **RAG:** ChromaDB, 500-token chunks, `nomic-embed-text` embeddings, documents from `docs/`

**CENTER_ADMIN — LangGraph scheduling agent**
- **Framework:** LangGraph multi-node graph (`classify_node → fetch_node → propose_node → execute_node`)
- **Tools:** `list_examiners`, `view_exam_calendar`, `auto_plan_schedule`, `assign_examiner_to_slot`, `confirm_schedule_plan`
- **Batch scheduling:** `auto_plan_schedule` dispatches a Celery task that runs OR-Tools CP-SAT solver; FastAPI polls Redis for up to 15 s then streams the result
- **Confirmation gate:** Admin must reply `xác nhận` in a separate turn before any write is committed; pending proposal is stored in Redis (`proposal:{user_id}`, TTL 30 min)
- **Resume mechanism:** On the confirmation turn, the agent router detects `_resume=True` and routes directly to `execute_node`, skipping classify/fetch/propose

### Redis slot gate

Atomic Lua script prevents race conditions on slot reservation:
- `hold_slot(slot_id)` → `1` (held) / `0` (full) / `-1` (cache miss → DB fallback)
- `release_slot(slot_id)` — rollback on booking failure

### Redis key layout

| DB | Key pattern | Purpose | TTL |
|----|-------------|---------|-----|
| 0 | `slot:{slot_id}` | Atomic slot counter (Lua gate) | — |
| 0 | `hold:{slot_id}` | TTL seat hold while a user is still confirming | 900 s |
| 0 | `session:{user_id}` | LangChain conversation history | 30 min |
| 0 | `proposal:{user_id}` | Pending scheduling proposal | 30 min |
| 0 | `pending_action:{user_id}` | Write action awaiting server-side confirmation | 30 min |
| 0 | `schedule_task:{task_id}` | OR-Tools solver result (JSON) | 2 h |
| 1 | Celery broker queues | Task messages | — |
| 2 | Celery result backend | Task state/result | — |

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
# Edit both files — set DB_PASSWORD and the SAME SECRET_KEY in both
# (full guide: see "Hướng dẫn chạy đầy đủ" above)

# 3. Start everything
cd deployment
docker compose up --build

# App is available at http://localhost:8080
# (no Ollama service in compose — default LLM is OpenAI; set OPENAI_API_KEY)
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
| `SECRET_KEY` | Shared secret for Django + JWT signing | *(required; same as FastAPI)* |
| `ACCESS_TOKEN_LIFETIME_MINUTES` | JWT access token TTL | `15` |
| `REFRESH_TOKEN_LIFETIME_DAYS` | JWT refresh token TTL | `7` |

### `fast_api_services/.env`

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL | `postgresql+asyncpg://postgres:pass@localhost/trinity` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `SECRET_KEY` | Shared secret for JWT auth — must match Django | *(required)* |
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
GET  /api/bookings/                     List my bookings (kèm payment_status, price)
GET  /api/bookings/{id}                 Booking detail
POST /api/bookings/                     { slot_id, student_name, student_dob, ... } → create (Django)
                                        Header: Idempotency-Key (optional) — chống tạo trùng
POST /api/bookings/{id}/cancel          { reason, confirm }
POST /api/bookings/{id}/pay             { method, confirm }   — MOCK gateway
POST /api/bookings/{id}/refund          { confirm }           — MOCK, tính theo policy
POST /api/bookings/{id}/documents       { doc_type, file_ref } — MOCK upload
GET  /api/bookings/{id}/result          Kết quả + chứng chỉ (nếu đã công bố)
POST /api/bookings/{id}/result/publish  CENTER_ADMIN công bố kết quả (MOCK)
```

### Agent (FastAPI SSE)

```
POST /api/agent/chat
Body: { "message": "...", "session_id": "uuid" }

SSE events:
  { "type": "token",      "content": "..." }
  { "type": "tool_start", "tool": "list_courses" }
  { "type": "tool_end",   "tool": "list_courses" }
  { "type": "done",       "content": "<full final content>" }
  { "type": "error",      "content": "..." }
```

### Scheduling (Django writes / FastAPI reads)

```
# Dispatch batch scheduling Celery task (CENTER_ADMIN only)
POST /api/centers/schedule/batch/
Body: { "date_from": "2026-05-01", "date_to": "2026-05-31" }
→ { "task_id": "uuid" }   (Celery task dispatched; result written to Redis)

# Commit proposed plan to DB after admin confirms
POST /api/centers/schedule/batch/{task_id}/confirm/
→ { "assigned_count": 42, "skipped": [] }

# Center analytics (CENTER_ADMIN)
GET  /api/centers/reports/summary/?date_from=2026-05-01&date_to=2026-05-31

# Read scheduling data (FastAPI)
GET  /api/scheduling/examiners        List examiners for the admin's center
GET  /api/scheduling/calendar         ?date_from=2026-05-01&date_to=2026-05-31
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
│   │   ├── memory.py           Redis conversation history + pending_proposal
│   │   ├── tools.py            7 LangChain tools + confirmation gate
│   │   ├── scheduling_tools.py Scheduling tools (CENTER_ADMIN)
│   │   ├── scheduling_graph.py LangGraph scheduling: classify→fetch→propose→execute
│   │   ├── booking_graph.py    LangGraph booking/cancel flow
│   │   ├── supervisor.py       Multi-agent supervisor (routes by user role)
│   │   ├── state.py            Shared LangGraph state schemas
│   │   └── agent.py            ReAct agent + Vietnamese system prompt
│   ├── routers/
│   │   ├── catalog.py          GET /catalog/courses, /catalog/slots
│   │   ├── bookings.py         GET /bookings/
│   │   ├── scheduling.py       GET /scheduling/examiners, /scheduling/calendar
│   │   └── agent.py            POST /agent/chat (SSE) — _resume mechanism
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

Total: **177 backend tests** (83 Django + 94 FastAPI) + **19 frontend tests**
