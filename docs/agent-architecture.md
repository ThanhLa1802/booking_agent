# Kiến trúc AI Agent — Trinity Exam Assistant

Tài liệu này mô tả chi tiết thiết kế và vận hành của AI Agent trong hệ thống Trinity.

---

## 1. Tổng quan

Agent là thành phần trung tâm của `fast_api_services/`, đóng vai trò **trợ lý hội thoại** cho phép học sinh và phụ huynh:

- Tra cứu chương trình thi, cấp độ, học phí
- Kiểm tra slot thi còn trống
- Đọc chính sách, FAQ từ tài liệu Trinity
- Đặt và hủy lịch thi (sau khi người dùng xác nhận)

Agent vận hành theo mô hình **ReAct** (Reason + Act): mỗi lượt hội thoại, agent suy luận → chọn tool → xử lý kết quả → phản hồi. Kết quả được stream về frontend qua **SSE (Server-Sent Events)**.

---

## 2. Sơ đồ kiến trúc

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Frontend (React / chatStore)                      │
│           EventSource  POST /api/agent/chat                              │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ SSE stream (text/event-stream)
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   FastAPI  /api/agent/chat  (routers/agent.py)            │
│                                                                           │
│  1. Xác thực JWT  →  lấy user_id + raw_token                            │
│  2. Tải lịch sử   →  Redis  session:{user_id}                           │
│  3. Khởi tạo LLM  →  get_llm()          (pluggable)                    │
│  4. Khởi tạo Emb  →  get_embeddings()   (pluggable)                    │
│  5. Tạo Tools     →  make_tools(ToolContext)                            │
│  6. Tạo Agent     →  create_agent(llm, tools, chat_history)             │
│  7. Stream        →  agent_executor.astream_events(...)                 │
│  8. Lưu lịch sử   →  save_history(redis, user_id, ...)                 │
│                                                                           │
└──────────┬──────────────────────────────────────────────────────────────┘
           │
           │  tool calls
           ▼
┌──────────────────────────────────────────────────────┐
│                    Tools (tools.py)                   │
│                                                       │
│  search_exam_docs  ──►  ChromaDB (RAG)               │
│  list_courses      ──►  PostgreSQL (async)           │
│  list_available_slots ► PostgreSQL + Redis cache     │
│  get_booking_detail ──► PostgreSQL (async)           │
│  list_my_bookings  ──►  PostgreSQL (async)           │
│  create_booking    ──►  Django POST /api/bookings/   │
│  cancel_booking    ──►  Django PATCH /api/bookings/  │
└──────────────────────────────────────────────────────┘
           │
           │  reads/writes
           ▼
┌──────────────────────┐  ┌──────────────────┐  ┌───────────────────────┐
│    PostgreSQL 15     │  │     Redis 7       │  │  Django core_service  │
│  catalog + bookings  │  │  slot gate (Lua)  │  │  POST /api/bookings/  │
└──────────────────────┘  │  session history  │  └───────────────────────┘
                          └──────────────────┘
```

---

## 3. Các thành phần

### 3.1 Endpoint SSE — `routers/agent.py`

```
POST /api/agent/chat
Body:  { "message": "...", "session_id": null }
Response: text/event-stream
```

Mỗi request tạo một `AgentExecutor` mới, inject `chat_history` từ Redis. Agent **không giữ trạng thái giữa các request** — toàn bộ ngữ cảnh hội thoại đến từ Redis.

**SSE Events được emit:**

| Event type | Nội dung | Mục đích |
|------------|----------|----------|
| `token` | chunk text | Hiển thị phản hồi stream từng từ |
| `tool_start` | tên tool | Frontend hiển thị "đang tra cứu..." |
| `tool_end` | tên tool | Frontend ẩn spinner |
| `done` | phản hồi đầy đủ | Báo hiệu kết thúc stream |
| `error` | thông báo lỗi | Hiển thị lỗi cho người dùng |

---

### 3.2 Agent Factory — `agent/agent.py`

```python
agent_executor = AgentExecutor(
    agent=create_tool_calling_agent(llm, tools, prompt),
    tools=tools,
    max_iterations=5,       # tối đa 5 tool calls / lượt
    handle_parsing_errors=True,
)
```

**System prompt** hướng dẫn agent:
- Trả lời bằng tiếng Việt nếu người dùng viết tiếng Việt
- KHÔNG bao giờ gọi `create_booking` / `cancel_booking` trước khi người dùng xác nhận
- Tối đa 5 tool calls mỗi lượt để tránh vòng lặp vô hạn

**Prompt structure (LangChain `ChatPromptTemplate`):**

```
[system]         ← SYSTEM_PROMPT (hướng dẫn cứng)
[chat_history]   ← MessagesPlaceholder (lịch sử từ Redis)
[human]          ← {input} (câu hỏi hiện tại)
[agent_scratchpad] ← MessagesPlaceholder (ReAct scratch)
```

---

### 3.3 LLM Interface — `agent/llm.py`

Toàn bộ code agent gọi `get_llm()` và `get_embeddings()` — **không hardcode** tên model hay provider. Cho phép đổi backend bằng biến môi trường `.env`:

| `LLM_PROVIDER` | Model | Môi trường |
|----------------|-------|-----------|
| `ollama` (mặc định) | `llama3.1:8b` | Local dev |
| `openai` | `gpt-4o-mini` | Production |
| `google` | `gemini-2.0-flash` | Production |

| `EMBEDDING_PROVIDER` | Model | Môi trường |
|----------------------|-------|-----------|
| `ollama` (mặc định) | `nomic-embed-text` | Local dev |
| `openai` | `text-embedding-3-small` | Production |

---

### 3.4 Tools — `agent/tools.py`

Mỗi tool là một async function được bọc bởi `@tool` decorator của LangChain. Tất cả tools nhận `ToolContext` qua closure — không dùng global state.

```python
@dataclass
class ToolContext:
    session_factory: async_sessionmaker   # mỗi tool mở DB session riêng
    redis: Any                             # aioredis client
    user_id: int                           # user hiện tại
    user_token: str                        # JWT token — forward sang Django
    embeddings: Any                        # model embedding (ChromaDB)
    persist_dir: str                       # thư mục ChromaDB
```

**7 tools:**

| Tool | Loại | Mô tả |
|------|------|-------|
| `search_exam_docs(query, doc_type?)` | Đọc | RAG qua ChromaDB. `doc_type`: `"syllabus"` / `"policy"` / `"faq"` / `None` |
| `list_courses(style?, grade?)` | Đọc | Danh sách khóa thi, học phí từ PostgreSQL |
| `list_available_slots(course_id, city?, date_from?, date_to?)` | Đọc | Slot còn chỗ, kết hợp DB + Redis cache |
| `get_booking_detail(booking_id)` | Đọc | Chi tiết một booking của user hiện tại |
| `list_my_bookings()` | Đọc | Tất cả booking của user hiện tại |
| `create_booking(slot_id, student_name, student_dob, notes, confirm)` | ⚠️ Ghi | Đặt lịch — bắt buộc `confirm=True` |
| `cancel_booking(booking_id, reason, confirm)` | ⚠️ Ghi | Hủy lịch — bắt buộc `confirm=True` |

**Confirmation Gate** (cổng xác nhận):

```python
if not confirm:
    return (
        "⚠️ Confirmation required. Please explicitly confirm (yes / xác nhận) "
        "before I proceed with this action.\n"
        f"Action: Create booking — Slot {slot_id}, Student: {student_name}. "
        "Reply 'xác nhận' to proceed."
    )
```

Nếu `confirm=False`, tool trả về chuỗi cảnh báo thay vì thực hiện ghi. Agent sau đó relay cảnh báo đó cho người dùng. Chỉ khi người dùng gõ "xác nhận" / "yes" / "đồng ý", agent mới gọi lại tool với `confirm=True`.

**Write tools gọi Django qua HTTP (không ghi DB trực tiếp):**

```python
async with httpx.AsyncClient(timeout=10) as client:
    resp = await client.post(
        f"{settings.django_service_url}/api/bookings/",
        json=payload,
        headers={"Authorization": f"Bearer {ctx.user_token}"},  # forward JWT
    )
```

Lý do: Django giữ transaction integrity + business logic validation. FastAPI chỉ là orchestration layer.

---

### 3.5 RAG — `agent/rag.py`

Tài liệu gốc trong `docs/` được index vào ChromaDB khi khởi động:

```
docs/
├── syllabus/     ← doc_type = "syllabus"
│   ├── classical_jazz_grades_1_8.md
│   ├── rock_pop_grades_1_8.md
│   └── theory_grades_1_8.md
├── policies/     ← doc_type = "policy"
│   ├── cancellation_policy.md
│   └── rescheduling_special_consideration.md
└── faq/          ← doc_type = "faq"
    ├── candidate_faq.md
    └── parent_faq.md
```

**Chiến lược chunk:**
- `chunk_size = 500` ký tự
- `chunk_overlap = 50` ký tự
- Mỗi chunk lưu metadata `{ source, doc_type }`

**Tìm kiếm:**
- Similarity search top-4 chunks
- Nếu truyền `doc_type`, filter theo metadata trước khi search
- Trả về text chunks nối bằng `---`

---

### 3.6 Conversation Memory — `agent/memory.py`

Lịch sử hội thoại lưu trong Redis theo key `session:{user_id}`:

```json
[
  { "type": "human", "content": "Tôi muốn thi Piano Grade 3" },
  { "type": "ai",    "content": "Môn Piano Grade 3 thuộc chương trình..." }
]
```

| Hành vi | Chi tiết |
|---------|----------|
| TTL | 1800 giây (30 phút) — reset sau mỗi lượt chat |
| Load | Đầu mỗi request: `load_history(redis, user_id)` |
| Save | Cuối mỗi request: `save_history(redis, user_id, human, ai)` |
| Lỗi Redis | Trả về `[]` (không crash) — agent vẫn hoạt động không có lịch sử |

---

## 4. Luồng xử lý đầy đủ (sequence)

```
User gõ: "Đặt lịch thi Piano Grade 1 slot 33 cho con tôi tên Minh"
                │
                ▼
        POST /api/agent/chat
        JWT validation → user_id=42
                │
                ▼
        load_history(redis, 42) → chat_history = [...]
                │
                ▼
        AgentExecutor.astream_events(input, chat_history)
                │
                ▼ Lượt ReAct 1: Suy luận
        "Người dùng muốn đặt lịch → cần xác nhận"
                │
                ▼ Lượt ReAct 2: Gọi create_booking(confirm=False)
        tool trả về: "⚠️ Confirmation required..."
                │
                ▼ Agent trả lời người dùng
        SSE: { type: "token", content: "Bạn muốn đặt..." }
        SSE: { type: "done" }
                │
                ▼
        save_history(redis, 42, input, response)

─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
User gõ: "xác nhận"
                │
                ▼
        load_history(redis, 42) → có context "đặt slot 33 cho Minh"
                │
                ▼ ReAct: Gọi create_booking(slot_id=33, student_name="Minh", confirm=True)
                │
                ▼ tool gọi Django POST /api/bookings/
                  Django: kiểm tra slot, tạo Booking, return 201
                │
                ▼
        SSE: { type: "done", content: "✅ Đặt lịch thành công! Booking #7" }
```

---

## 5. Giới hạn và bảo vệ

| Giới hạn | Giá trị | Mục đích |
|----------|---------|---------|
| `max_iterations` | 5 | Tránh vòng lặp tool call vô hạn |
| `ChatRequest.message` max_length | 2000 ký tự | Giới hạn input người dùng |
| Redis session TTL | 1800s (30 phút) | Tự động xóa session không hoạt động |
| `httpx.AsyncClient` timeout | 10 giây | Tránh treo khi gọi Django |
| Confirmation gate | `confirm=False` mặc định | Write tools không bao giờ tự chạy |
| JWT forwarding | `Authorization: Bearer {token}` | Django validate quyền user |

---

## 6. Cách mở rộng

### Thêm tool mới

1. Thêm async function với `@tool` decorator vào `tools.py`
2. Thêm vào list return của `make_tools(ctx)`
3. Nếu là write tool, thêm `confirm: bool = False` và kiểm tra confirmation gate
4. Viết test trong `tests/test_agent_tools.py`

### Đổi LLM provider

Chỉ cần đổi biến môi trường — không thay đổi code:

```env
# .env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

### Thêm tài liệu RAG

1. Đặt file `.md` vào `docs/syllabus/`, `docs/policies/`, hoặc `docs/faq/`
2. Xóa ChromaDB cache: `rm -rf chromadb_data/`
3. Restart FastAPI — tài liệu tự động được index lại khi khởi động
