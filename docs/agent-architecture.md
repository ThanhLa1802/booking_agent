# Kiến trúc AI Agent — Trinity Exam Assistant

Tài liệu này mô tả chi tiết thiết kế và vận hành của AI Agent trong hệ thống Trinity.

---

## 1. Tổng quan

Agent là thành phần trung tâm của `fast_api_services/`, đóng vai trò **trợ lý hội thoại** đa vai trò:

**STUDENT / PARENT:**
- Tra cứu chương trình thi, cấp độ, học phí
- Kiểm tra slot thi còn trống
- Đọc chính sách, FAQ từ tài liệu Trinity
- Đặt, hủy, dời lịch thi (sau khi xác nhận)

**CENTER_ADMIN:**
- Xem lịch thi theo ngày/tháng
- Xem danh sách giám khảo và tải trọng theo ngày
- Gán giám khảo vào slot thi (sau khi xác nhận)
- Dời lịch booking của học viên

Hệ thống sử dụng **LangGraph SupervisorGraph** để định tuyến theo role: STUDENT/PARENT đến `BookingGraph` (ReAct agent), CENTER_ADMIN đến `SchedulingGraph` (StateGraph có cổng xác nhận 2 lượt). Kết quả được stream về frontend qua **SSE (Server-Sent Events)**.

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
│  1. Xác thực JWT        →  lấy user_id + raw_token                      │
│  2. Tải lịch sử         →  Redis  session:{user_id}                     │
│  3. Load pending proposal → Redis  proposal:{user_id}  (admin resume)   │
│  4. Khởi tạo LLM        →  get_llm()          (pluggable)              │
│  5. Khởi tạo Embeddings →  get_embeddings()   (pluggable)              │
│  6. Tạo Tools           →  make_tools(ToolContext)                      │
│                             make_scheduling_tools(SchedulingToolContext) │
│                             make_reschedule_tools(ctx, user_id)          │
│  7. Tạo SupervisorGraph →  create_supervisor_graph(...)                 │
│  8. Stream events       →  supervisor.astream_events(...)               │
│  9. Lưu proposal / clear → Redis  proposal:{user_id}                    │
│  10. Lưu lịch sử        →  save_history(redis, user_id, ...)           │
│                                                                           │
└──────────┬────────────────────────────────────────────────────────────--┘
           │
           │  LangGraph routing
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  SupervisorGraph  (agent/supervisor.py)                   │
│                                                                           │
│  _route_by_role(state)                                                   │
│  ├─ user_role == "CENTER_ADMIN"    → scheduling_subgraph_node            │
│  └─ user_role == "STUDENT"|"PARENT" → booking_subgraph_node             │
│                                                                           │
│  ┌────────────────────────────────┐  ┌──────────────────────────────┐   │
│  │     SchedulingGraph            │  │     BookingGraph              │   │
│  │   (agent/scheduling_graph.py)  │  │  (agent/booking_graph.py)    │   │
│  │                                │  │                               │   │
│  │  START                         │  │  START                        │   │
│  │   │ _route_from_start()        │  │   │                           │   │
│  │   ├─(new)→ classify_node       │  │   ▼                           │   │
│  │   └─(resume)→ execute_node     │  │  booking_node                 │   │
│  │       ▼                        │  │  (AgentExecutor ReAct)        │   │
│  │  fetch_node                    │  │   │                           │   │
│  │       ▼                        │  │  END                          │   │
│  │  propose_node                  │  └──────────────────────────────┘   │
│  │   ├─(read)→ END                │                                      │
│  │   └─(write)→ confirm_node      │                                      │
│  │       ├─(yes)→ execute_node    │                                      │
│  │       └─(no)→ END              │                                      │
│  │           ▼                    │                                      │
│  │       execute_node → END       │                                      │
│  └────────────────────────────────┘                                      │
└──────────┬─────────────────────────────────┬────────────────────────────┘
           │ scheduling tools                 │ booking tools
           ▼                                  ▼
┌──────────────────────────────┐  ┌──────────────────────────────────────┐
│  SchedulingTools             │  │  BookingTools  (agent/tools.py)       │
│  (agent/scheduling_tools.py) │  │                                       │
│                              │  │  search_exam_docs  → ChromaDB (RAG)  │
│  list_examiners              │  │  list_courses      → PostgreSQL       │
│  suggest_examiners_for_slot  │  │  list_available_slots → DB + Redis   │
│  get_exam_calendar           │  │  get_booking_detail → PostgreSQL     │
│  assign_examiner_to_slot ⚠️  │  │  list_my_bookings  → PostgreSQL     │
│  suggest_slots_for_reschedule│  │  create_booking ⚠️ → Django POST    │
│  reschedule_booking ⚠️       │  │  cancel_booking ⚠️ → Django PATCH   │
└──────────────┬───────────────┘  └──────────────┬────────────────────────┘
               │ reads + ⚠️ Django proxy           │ reads + ⚠️ Django proxy
               ▼                                   ▼
┌──────────────────────┐  ┌──────────────────┐  ┌───────────────────────┐
│    PostgreSQL 15     │  │     Redis 7       │  │  Django core_service  │
│  catalog + bookings  │  │  slot gate (Lua)  │  │  POST /api/bookings/  │
│  centers + examiners │  │  session history  │  │  PATCH /api/bookings/ │
└──────────────────────┘  │  proposal store   │  │  POST centers/slots/  │
                          └──────────────────┘  │    assign-examiner/   │
                                                 └───────────────────────┘
```

---

## 3. Các thành phần

### 3.1 Endpoint SSE — `routers/agent.py`

```
POST /api/agent/chat
Body:  { "message": "...", "session_id": null }
Response: text/event-stream
```

Mỗi request thực hiện các bước sau:

1. **Xác thực JWT** → lấy `user_id` và `raw_token`
2. **Resolve role** → query DB để lấy `user_role` (`STUDENT` / `PARENT` / `CENTER_ADMIN`) và `center_id`
3. **Load lịch sử** → `load_history(redis, user_id)`
4. **Load pending proposal** → `load_pending_proposal(redis, user_id)` — phục vụ resume xác nhận của CENTER_ADMIN
5. **Phát hiện ý định xác nhận** → so khớp tin nhắn với `{"xác nhận", "yes", "đồng ý", "confirm", "ok", "có"}`
6. **Khởi tạo Tools** → tạo `BookingTools`, `SchedulingTools`, `RescheduleTools` với context đúng role
7. **Build SupervisorGraph** → `create_supervisor_graph(...)`
8. **Xây dựng initial state** → nếu đang resume xác nhận (`_resume=True`), inject proposal + `confirmed=True` vào state
9. **Stream events** → `supervisor.astream_events(initial_state, ...)`
10. **Sau stream**: lưu proposal (nếu có) vào Redis, hoặc xóa nếu đã execute xong

**`_resume` logic:**
```python
_resume = bool(pending_proposal and is_confirmation)
initial_state = {
    "messages": [HumanMessage(content=request.message)],
    "user_role": user_role,
    "task_type": pending_proposal["task_type"] if _resume else "general",
    "proposal": pending_proposal["proposal"]  if _resume else None,
    "confirmed": True                          if _resume else False,
    "thread_id": str(user_id),
}
```

**Proposal persistence** (`on_chain_end` handler):
```python
# Khi scheduling_subgraph kết thúc:
if name == "scheduling_subgraph":
    proposal_out = output.get("proposal")
    confirmed_out = output.get("confirmed", False)
    if proposal_out and not confirmed_out:
        await save_pending_proposal(redis, user_id, ...)  # lưu để lượt sau resume
    else:
        await clear_pending_proposal(redis, user_id)      # đã execute hoặc đã read-only
```

> **Lý do không check `name == "propose_node"`**: LangGraph `astream_events()` đối với sub-graph được gọi qua `ainvoke()` chỉ emit tên node đã đăng ký trong `SupervisorGraph` (là `"scheduling_subgraph"`), không emit tên node bên trong sub-graph đó.

**SSE Events được emit:**

| Event type | Nội dung | Mục đích |
|------------|----------|----------|
| `token` | chunk text | Hiển thị phản hồi stream từng từ |
| `tool_start` | tên tool | Frontend hiển thị "đang tra cứu..." |
| `tool_end` | tên tool | Frontend ẩn spinner |
| `done` | phản hồi đầy đủ | Báo hiệu kết thúc stream |
| `error` | thông báo lỗi | Hiển thị lỗi cho người dùng |

> Các node nội bộ (`classify_node`, `fetch_node`) bị lọc ra — token từ các node này không stream ra frontend.

---

### 3.2 SupervisorGraph — `agent/supervisor.py`

Top-level LangGraph router. Định tuyến toàn bộ conversation đến đúng sub-graph dựa trên `user_role`.

```python
class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    user_role: str
    task_type: str
    proposal: Optional[dict]
    confirmed: bool
    thread_id: str
```

**Topology:**
```
START → _route_by_role() → scheduling_subgraph  (CENTER_ADMIN)
                         → booking_subgraph      (STUDENT / PARENT)
      → END
```

**State mapping vào sub-graph:**
- `scheduling_subgraph_node`: truyền đầy đủ `task_type`, `proposal`, `confirmed` vào `SchedulingState`
- `booking_subgraph_node`: truyền `messages`, `user_role` vào `BookingState`

---

### 3.3 SchedulingGraph — `agent/scheduling_graph.py`

StateGraph dành riêng cho CENTER_ADMIN. Hỗ trợ **human-in-the-loop confirmation** với luồng 2 lượt hội thoại.

```python
class SchedulingState(TypedDict):
    messages: Annotated[list, add_messages]
    user_role: str          # "CENTER_ADMIN"
    task_type: str          # "assign_examiner" | "view_calendar" | "reschedule" | "general"
    proposal: Optional[dict]
    confirmed: bool
```

**Topology:**
```
START
  │ _route_from_start()
  ├─ (proposal + confirmed=True) → execute_node   ← resume từ lượt trước
  └─ (mới)                       → classify_node
         ▼
     fetch_node
         ▼
     propose_node
      ├─ (view_calendar / general) → confirmed=True → END  ← không cần xác nhận
      └─ (assign_examiner / reschedule) → confirm_node
                ├─ (xác nhận)  → execute_node → END
                └─ (hủy / ??)  → END
```

**Mô tả từng node:**

| Node | Vai trò |
|------|---------|
| `classify_node` | Gọi LLM để phân loại intent: `assign_examiner` / `view_calendar` / `reschedule` / `general`. Bỏ qua nếu đang resume (proposal + confirmed đã set). |
| `fetch_node` | Gọi read-only tool phù hợp (`get_exam_calendar`) để lấy dữ liệu hiển thị. Preserve `proposal`/`confirmed` từ lượt trước. |
| `propose_node` | Gọi LLM tạo đề xuất hành động bằng tiếng Việt. Với `view_calendar`/`general`: trả lời thẳng, set `confirmed=True`. Với write ops: tạo `proposal` dict, set `confirmed=False`. |
| `confirm_node` | Kiểm tra tin nhắn có keyword xác nhận. Trả về `confirmed=True` nếu có, xóa proposal nếu hủy, hỏi lại nếu không rõ. |
| `execute_node` | Gọi write tool với `confirm=True`. Trích xuất `slot_id`/`examiner_id` từ `proposal["conversation_messages"]` bằng regex. |

**Proposal dict (lưu trong Redis):**
```python
proposal = {
    "task_type": "assign_examiner",
    "description": "🗓️ Đề xuất: Gán giám khảo Nguyễn A vào Slot 15...",
    "conversation_messages": ["...", "..."],  # toàn bộ messages để extract IDs
}
```

**State preservation:** `classify_node` và `fetch_node` luôn giữ nguyên `proposal`/`confirmed` khi return, tránh ghi đè state từ lượt trước.

---

### 3.4 BookingGraph — `agent/booking_graph.py`

Graph đơn giản cho STUDENT/PARENT: một node duy nhất bọc `AgentExecutor` ReAct.

```
START → booking_node (AgentExecutor) → END
```

Confirmation gate nằm ở **tool level** (`confirm=False` guard trong `create_booking`, `cancel_booking`, `reschedule_booking`), không phải graph level. Stateless mỗi request — context đến từ `chat_history` inject qua Redis.

---

### 3.5 Agent Factory — `agent/agent.py`

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
- KHÔNG bao giờ gọi `create_booking` / `cancel_booking` / `reschedule_booking` trước khi người dùng xác nhận
- CENTER_ADMIN: dùng `suggest_examiners_for_slot` → xác nhận → `assign_examiner_to_slot`
- Tối đa 5 tool calls mỗi lượt

**Prompt structure:**
```
[system]           ← SYSTEM_PROMPT
[chat_history]     ← MessagesPlaceholder (lịch sử từ Redis)
[human]            ← {input}
[agent_scratchpad] ← MessagesPlaceholder (ReAct scratch)
```

---

### 3.6 LLM Interface — `agent/llm.py`

Toàn bộ code agent gọi `get_llm()` và `get_embeddings()` — **không hardcode** tên model hay provider:

| `LLM_PROVIDER` | Model mặc định | Môi trường |
|----------------|----------------|-----------|
| `ollama` | `llama3.1:8b` | Local dev |
| `openai` | `gpt-4o-mini` | Production |
| `google` | `gemini-2.0-flash` | Production |

| `EMBEDDING_PROVIDER` | Model mặc định | Môi trường |
|----------------------|----------------|-----------|
| `ollama` | `nomic-embed-text` | Local dev |
| `openai` | `text-embedding-3-small` | Production |

---

### 3.7 Scheduling Tools — `agent/scheduling_tools.py`

Tools dành riêng cho CENTER_ADMIN. Được khởi tạo với `SchedulingToolContext`:

```python
@dataclass
class SchedulingToolContext:
    session_factory: async_sessionmaker
    user_token: str    # JWT — forward sang Django khi ghi
    center_id: int     # center của admin (lấy từ DB khi login)
```

**`make_scheduling_tools(ctx)` — 4 tools:**

| Tool | Loại | Mô tả |
|------|------|-------|
| `list_examiners(available_date?, style?)` | Đọc | Danh sách giám khảo của center, lọc theo ngày và style. |
| `suggest_examiners_for_slot(slot_id)` | Đọc | Gợi ý giám khảo phù hợp cho slot, xếp theo tải ít nhất. |
| `get_exam_calendar(date_from?, date_to?)` | Đọc | Lịch thi đầy đủ của center với thông tin giám khảo. |
| `assign_examiner_to_slot(slot_id, examiner_id, confirm)` | ⚠️ Ghi | Gán giám khảo vào slot — proxy đến Django `POST /api/centers/slots/{id}/assign-examiner/`. |

**`make_reschedule_tools(ctx, user_id)` — 2 tools (dùng được bởi cả admin và student):**

| Tool | Loại | Mô tả |
|------|------|-------|
| `suggest_slots_for_reschedule(booking_id, date_from?, date_to?, city?)` | Đọc | Tìm slot thay thế cho booking hiện có (cùng khóa học, còn chỗ). |
| `reschedule_booking(booking_id, new_slot_id, reason?, confirm)` | ⚠️ Ghi | Dời lịch booking — proxy đến Django `POST /api/bookings/{id}/reschedule/`. |

---

### 3.8 Booking Tools — `agent/tools.py`

Tools dành cho STUDENT/PARENT. Khởi tạo với `ToolContext`:

```python
@dataclass
class ToolContext:
    session_factory: async_sessionmaker
    redis: Any
    user_id: int
    user_token: str
    embeddings: Any
    persist_dir: str
    user_role: str
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

**Confirmation Gate (tool-level):**
```python
if not confirm:
    return (
        "⚠️ Confirmation required. Please explicitly confirm (yes / xác nhận)...\n"
        f"Action: Create booking — Slot {slot_id}, Student: {student_name}. "
        "Reply 'xác nhận' to proceed."
    )
```

Write tools gọi Django qua HTTP — không ghi DB trực tiếp:
```python
async with httpx.AsyncClient(timeout=10) as client:
    resp = await client.post(
        f"{settings.django_service_url}/api/bookings/",
        json=payload,
        headers={"Authorization": f"Bearer {ctx.user_token}"},
    )
```

---

### 3.9 RAG — `agent/rag.py`

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

**Chiến lược chunk:** `chunk_size=500`, `chunk_overlap=50`, metadata `{source, doc_type}`  
**Tìm kiếm:** top-4 chunks, optional filter theo `doc_type`

---

### 3.10 Conversation Memory — `agent/memory.py`

**Session history** (`session:{user_id}`) — lịch sử hội thoại:
```json
[
  { "type": "human", "content": "Tôi muốn thi Piano Grade 3" },
  { "type": "ai",    "content": "Môn Piano Grade 3 thuộc chương trình..." }
]
```

**Pending proposal** (`proposal:{user_id}`) — lưu đề xuất chờ xác nhận (CENTER_ADMIN):
```json
{
  "task_type": "assign_examiner",
  "proposal": {
    "task_type": "assign_examiner",
    "description": "🗓️ Đề xuất hành động...",
    "conversation_messages": ["...", "..."]
  },
  "proposal_text": "🗓️ Đề xuất hành động..."
}
```

| Key | TTL | Hành vi khi lỗi Redis |
|-----|-----|----------------------|
| `session:{user_id}` | 1800s | Trả về `[]` — agent vẫn chạy |
| `proposal:{user_id}` | 1800s | Trả về `None` — không resume xác nhận |
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

## 5. Giới hạn và bảo vệ

| Giới hạn | Giá trị | Mục đích |
|----------|---------|---------|
| `max_iterations` | 5 | Tránh vòng lặp tool call vô hạn |
| `ChatRequest.message` max_length | 2000 ký tự | Giới hạn input người dùng |
| Redis session TTL | 1800s (30 phút) | Tự động xóa session không hoạt động |
| Redis proposal TTL | 1800s (30 phút) | Tự động hết hạn đề xuất chưa xác nhận |
| `httpx.AsyncClient` timeout | 10 giây | Tránh treo khi gọi Django |
| Confirmation gate (tool-level) | `confirm=False` mặc định | Write tools không bao giờ tự chạy |
| Confirmation gate (graph-level) | `confirm_node` trong SchedulingGraph | Double-check trước khi execute |
| JWT forwarding | `Authorization: Bearer {token}` | Django validate quyền user |
| Internal node filtering | `classify_node`, `fetch_node` | Token nội bộ không stream ra frontend |

---

## 6. Cách mở rộng

### Thêm booking tool mới

1. Thêm async function với `@tool` decorator vào `agent/tools.py`
2. Thêm vào list return của `make_tools(ctx)`
3. Nếu là write tool, thêm `confirm: bool = False` và kiểm tra confirmation gate
4. Viết test trong `tests/test_agent_tools.py`

### Thêm scheduling tool mới

1. Thêm tool vào `make_scheduling_tools(ctx)` hoặc `make_reschedule_tools(ctx, user_id)` trong `agent/scheduling_tools.py`
2. Nếu là write tool, thêm confirmation gate + proxy sang Django
3. Cập nhật `execute_node` trong `scheduling_graph.py` để gọi tool đó khi `task_type` phù hợp
4. Cập nhật `classify_node` prompt để nhận diện intent mới

### Thêm task_type mới cho SchedulingGraph

1. Thêm keyword vào `classification_prompt` trong `_make_classify_node()`
2. Thêm nhánh xử lý trong `fetch_node` (tool nào cần gọi để fetch data)
3. Thêm nhánh xử lý trong `execute_node` (tool nào cần gọi để execute)

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
