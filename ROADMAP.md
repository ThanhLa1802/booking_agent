# Trinity AI — Lộ trình Production Readiness

> Đánh giá ngày 2026-10-02. Trạng thái hiện tại: **dev/demo-grade** — kiến trúc logic đúng,
> code nội bộ tốt (slot lock atomic, confirmation gate, solver tách biệt), nhưng config deploy,
> bảo mật và khả năng scale chưa đạt prod.

## Nguyên tắc thực thi
- Sửa **từng giai đoạn độc lập, ship được**, mỗi giai đoạn có test + verify trước khi sang bước sau.
- Ưu tiên theo rủi ro: P0 chặn prod → P1 hardening → P2 scale/tối ưu.
- Không trộn thay đổi format với thay đổi hành vi trong cùng commit.
- Mọi thay đổi schema/dependency/provider phải hỏi trước.

---

## Ưu tiên tổng hợp

| ID | Mức | Vấn đề | Vị trí |
|----|-----|--------|--------|
| D1 | P0 | Compose là dev config: `uvicorn --reload`, mount source đè image, 1 process | `deployment/docker-compose.yaml:82` |
| D2 | P0 | Không TLS (nginx chỉ `listen 80`) | `deployment/nginx/nginx.conf:21` |
| D3 | P0 | DB/Redis/8001 port-mapped ra host, Redis không password, DB pass mặc định | `docker-compose.yaml:12,23,75` |
| S1 | P0 | `/api/agent/chat` không rate-limit/quota (đốt tiền LLM) | `nginx.conf:14` |
| S2 | P0 | Confirmation gate chưa là security boundary cứng (regex blacklist vô nghĩa, substring confirm) | `routers/agent.py:44,132` |
| S3 | P0 | Refresh token không revoke được (`BLACKLIST_AFTER_ROTATION=False`) | `settings.py:118` |
| R1 | P0 | Không CI; không observability; health check nông | `.github/`, `main.py:77` |
| R2 | P1 | Chroma embedded + index trong lifespan → cold start & không scale ngang | `main.py:36` |
| R3 | P1 | FastAPI raw SQL vào schema Django → coupling chặt | `routers/agent.py:100` |
| R4 | P1 | `CELERY_RESULT_BACKEND` trỏ localhost trong compose | `.env.example:21` |
| R5 | P1 | Không PgBouncer/pool tuning; Redis không persistence/HA | `docker-compose.yaml` |
| O1 | P2 | Polling Redis 15×1s; agent LLM chạy trong request SSE | `scheduling_graph`/`agent.py` |
| O2 | P2 | LangGraph checkpointer trên Redis TTL thay vì Postgres | `supervisor.py` |
| O3 | P2 | Frontend Dockerfile copy static + `tail -f /dev/null` (race) | `frontend/Dockerfile:17` |

---

## Giai đoạn 0 — Baseline an toàn & CI ✅ (hoàn tất 2026-10-02)
**Mục tiêu:** có lưới an toàn trước khi sửa.
- [x] Xác nhận toàn bộ test pass: Django 59, FastAPI 45, Frontend 19.
      → sửa 2 test FastAPI stale (SSE event-loop + shape event supervisor).
- [x] Thêm GitHub Actions `.github/workflows/ci.yml`: ruff + mypy (FastAPI), pytest (Django/FastAPI), eslint + vitest (Frontend).
      → bỏ `tsc` vì frontend là JS thuần, không có TypeScript.
- [x] Thêm `ruff.toml` + `mypy.ini`; dọn 88 lỗi lint tự động, sửa 5 lỗi type thật.
- [x] ESLint 0 error (2 warning `exhaustive-deps` để lại).
**DoD đạt:** CI xanh cục bộ trên cả 3 tầng; lint/typecheck sạch.
**Chuyển sang GĐ1:** pin image + `compose.prod` (là concern deploy, không phải baseline).

## Giai đoạn 1 — Deploy prod (D1, D2, D3) ✅ (code-complete 2026-10-02)
**Mục tiêu:** image immutable, đóng bề mặt tấn công, TLS. Chọn: Let's Encrypt + 1 VM docker compose.
- [x] Pin image runtime theo digest: postgres:15-alpine, redis:7-alpine, nginx:1.27-alpine, certbot/certbot.
- [x] Tạo `deployment/docker-compose.prod.yaml` (tách khỏi compose dev).
- [x] FastAPI: bỏ `--reload` + bỏ mount source; chạy `uvicorn --workers ${FASTAPI_WORKERS}` (mặc định 1 vì Chroma embedded — GĐ4 mở khoá).
- [x] Django: `gunicorn --workers ${GUNICORN_WORKERS:-3}`.
- [x] Đóng port DB/Redis/Django/FastAPI; chỉ nginx expose 80/443 (đã verify `compose config`).
- [x] Redis: `--requirepass` + AOF; DB/Redis password đưa từ `deployment/.env` (không default).
- [x] nginx TLS qua template `${DOMAIN}`: 443, redirect 80→443, HSTS + security headers, ACME webroot. Đã verify `nginx -t` với cert path render đúng.
- [x] `DEBUG=False`, `ALLOWED_HOSTS`/`CORS_ORIGINS`/`CSRF_TRUSTED_ORIGINS` theo `${DOMAIN}`.
- [x] `SECRET_KEY` chung 1 biến (Django ký JWT, FastAPI verify) — ghi rõ trong `.env.prod.example`.
- [x] Thêm `.dockerignore` (không bake `.env`/tests) + `deployment/.env.prod.example` + certbot renew service.
**DoD (code):** compose/template render + validate OK. **Còn lại để lên prod thật:** cấp cert trên VM, `up -d`, seed catalog 1 lần, cron reload nginx.

## Giai đoạn 2 — Security (S1, S2, S3)
**Mục tiêu:** chống abuse chi phí + bịt lỗ hổng confirmation/revoke.
- [ ] Server-side confirmation gate: phát `proposal_id` + nonce, lưu Redis; user gửi lại đúng token mới thực thi. Khớp exact-match, không substring (`"ok"`/`"có"`).
- [ ] Rate limit + per-user quota cho `/api/agent/chat` (theo IP + user_id, ví dụ token budget/ngày).
- [ ] Bật token blacklist; thêm endpoint logout/revoke refresh; cân nhắc `ROTATE_REFRESH_TOKENS` + blacklist app.
- [ ] Bỏ regex "bảo mật" giả (`routers/agent.py:44`), thay bằng validation/độ dài + không tin client.
- [ ] Rà soát toàn bộ center-scoping trong `scheduling_tools`/reschedule.
**DoD:** prompt injection chèn `confirm=True` không tạo được booking; spam chat bị chặn; logout vô hiệu refresh token.

## Giai đoạn 3 — Reliability & Observability (R1, R4, R5)
**Mục tiêu:** biết hệ thống hỏng ở đâu, chịu tải cơ bản.
- [ ] Health check sâu: `/health` kiểm DB + Redis (+ Chroma) và trả 503 khi lỗi.
- [ ] Structured logging (JSON) + Sentry (cả Django & FastAPI).
- [ ] Đồng bộ `CELERY_RESULT_BACKEND` cho môi trường container.
- [ ] PgBouncer + cấu hình pool Django/asyncpg; thêm healthcheck cho celery/celery-beat.
- [ ] Backup PostgreSQL định kỳ + script restore đã test.
**DoD:** dashboard lỗi + alert; kill Redis/DB → health trả 503 đúng; restore DB thành công trên staging.

## Giai đoạn 4 — Scale & tối ưu kiến trúc (R2, R3, O1, O2, O3)
**Mục tiêu:** scale ngang, bỏ coupling nóng.
- [ ] RAG indexing tách khỏi lifespan (job/worker); cân nhắc Chroma server mode hoặc pgvector.
- [ ] FastAPI bỏ raw SQL vào schema Django → dùng view/API nội bộ hoặc read replica.
- [ ] Agent LLM chạy qua worker queue; batch scheduling bỏ polling 15×1s → SSE/webhook.
- [ ] Chuyển LangGraph checkpointer sang Postgres; FastAPI chạy nhiều worker sau nginx LB.
- [ ] Sửa `frontend/Dockerfile` (nginx serve build trực tiếp, bỏ `tail -f`).
**DoD:** scale FastAPI ≥2 replica không lỗi Chroma; load test đạt mục tiêu; không còn polling dài.

---

## Thứ tự thực thi đề xuất
`GĐ0 → GĐ1 → GĐ2 → GĐ3 → GĐ4`

GĐ0–GĐ2 là điều kiện tối thiểu để gọi là "prod chấp nhận được" (~1–2 tuần).
GĐ3–GĐ4 là hardening/scale có thể chạy song song sau khi lên prod.
