---
name: security-and-hardening
description: Hardens code against vulnerabilities. Use when handling user input, authentication, data storage, or external integrations. Use when building any feature that accepts untrusted data, manages user sessions, or interacts with third-party services.
---

# Security and Hardening

## Overview

Treat every external input as hostile, every secret as sacred, and every authorization check as mandatory. Security isn't a phase — it's a constraint on every line of code that touches user data, authentication, or external systems.

## When to Use

- Building anything that accepts user input
- Implementing authentication or authorization
- Storing or transmitting sensitive data
- Integrating with external APIs or services

## The Three-Tier Boundary System

### Always Do (No Exceptions)

- **Validate all external input** at the system boundary (API routes, handlers)
- **Parameterize all database queries** — never concatenate user input into SQL
- **Encode output** to prevent injection (use framework auto-escaping)
- **Use HTTPS** for all external communication
- **Hash passwords** with bcrypt/scrypt/argon2 (never store plaintext)
- **Never log sensitive data** (passwords, tokens, OTPs)

### Ask First (Requires Human Approval)

- Adding new authentication flows or changing auth logic
- Storing new categories of sensitive data (PII, payment info)
- Changing CORS configuration
- Modifying rate limiting or throttling

### Never Do

- **Never commit secrets** to version control (API keys, passwords, tokens)
- **Never log sensitive data** (passwords, tokens, full OTPs)
- **Never trust client-side validation** as a security boundary
- **Never expose stack traces** or internal error details to users
- **Never hardcode OTPs** or predictable values (e.g., `"123456"`, `"111111"`)

## OWASP Top 10 — Python/FastAPI/Django Patterns

### 1. Injection

```python
# BAD: SQL injection via string concat
query = f"SELECT * FROM devices WHERE id = '{device_id}'"

# GOOD: Django ORM parameterizes automatically
device = Device.objects.get(id=device_id)

# GOOD: raw query parameterized
Device.objects.raw("SELECT * FROM devices WHERE id = %s", [device_id])
```

### 2. Broken Authentication

```python
# BAD: secret in code
SECRET_KEY = "django-insecure-hardcoded"

# GOOD: from environment via django-environ
SECRET_KEY = env("SECRET_KEY")  # loaded from .env, never committed
```

### 3. Sensitive Data Exposure

```python
# BAD: password or token returned in response
return Response({"password": user.password})  # never expose

# GOOD: DRF serializer excludes sensitive fields
# password field has write_only=True on UserSerializer
```

### 4. Broken Access Control

```python
# FastAPI — always scope queries to the authenticated user
@router.get("/orders/")
async def list_orders(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    # BAD: returns all orders
    result = await db.execute(select(Order))

    # GOOD: scoped to authenticated user only
    result = await db.execute(select(Order).where(Order.user_id == user_id))
```

### 5. Security Misconfiguration

- Rate limiter in FastAPI must use real client IP (`request.client.host`), not hardcoded string
- CORS origin restricted to known domains (`CORS_ALLOWED_ORIGINS`, not `CORS_ALLOW_ALL_ORIGINS=True`)
- JWT secret must be strong random value loaded from `SECRET_KEY` env var (shared by Django & FastAPI)
- `DEBUG=False` in any non-development settings

## Secrets Management

```
core_service/
  .env.example  → Committed (template with placeholder values)
  .env          → NOT committed (contains real secrets)

.gitignore must include:
  .env
  *.pem
  *.key
```

## Rate Limiting — Key Rules

```python
# BAD: hardcoded key — all users share one counter
key = f"ratelimit:hardcoded:{url_path}"

# GOOD: per-user key (authenticated endpoints)
userid = current_user.id
key = f"ratelimit:{userid}:{url_path}"

# GOOD: per-IP key (login/register — unauthenticated)
key = f"ratelimit:{request.client.host}:{url_path}"
# Nginx also enforces: auth zone = 5 req/min, checkout zone = 10 req/min
```

## Security Review Checklist

```markdown
### Authentication
- [ ] Passwords hashed (Django handles via AbstractBaseUser/bcrypt)
- [ ] Login has rate limiting with per-IP key (django-axes + Nginx)
- [ ] JWT secret loaded from env (`SECRET_KEY`), not hardcoded
- [ ] accessToken stored in memory only (not localStorage)
- [ ] refreshToken stored in localStorage (acceptable trade-off for UX)

### Authorization
- [ ] Every protected endpoint uses `Depends(get_current_user_id)`
- [ ] Users can only access their own orders, cart, wishlist, reviews

### Input
- [ ] All user input validated at the boundary (Pydantic schemas in FastAPI, DRF serializers in Django)
- [ ] SQL queries use ORM or parameterized raw queries (never string concat)
### Data
- [ ] No secrets in code or version control
    - [ ] core_service/.env in .gitignore
    - [ ] Password fields write_only in serializers
    - [ ] JWT tokens not logged
- [ ] Rate limiter uses real client IP
- [ ] Error messages don't expose internal details
```

## Red Flags (Project-Specific)

- `SECRET_KEY` hardcoded in `core_service/core/settings.py` instead of loaded from env
- `CORS_ALLOW_ALL_ORIGINS = True` in settings
- `accessToken` persisted to localStorage (must stay in memory only)
- Django `DEBUG=True` in production
- Missing `Depends(get_current_user_id)` on any protected FastAPI endpoint
- Lua stock reservation bypassed with raw DB decrement (race condition risk)

## Verification

- [ ] No secrets in source code or git history
- [ ] All user input validated at system boundaries
- [ ] Auth and authz checked on every protected endpoint
- [ ] Rate limiting uses real client identity (IP or userID)
- [ ] Error responses don't expose internal details
