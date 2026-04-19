---
name: test-driven-development
description: Drives development with tests. Use when implementing any logic, fixing any bug, or changing any behavior. Use when you need to prove that code works, when a bug report arrives, or when you're about to modify existing functionality.
---

# Test-Driven Development

## Overview

Write a failing test before writing the code that makes it pass. For bug fixes, reproduce the bug with a test before attempting a fix. Tests are proof — "seems right" is not done.

## When to Use

- Implementing any new logic or behavior
- Fixing any bug (the Prove-It Pattern)
- Modifying existing functionality
- Adding edge case handling

**When NOT to use:** Pure configuration changes, documentation updates, or static content changes with no behavioral impact.

## The TDD Cycle

```
RED → GREEN → REFACTOR
Write failing test → Make it pass → Clean up
```

### Step 1: RED — Write a Failing Test

Write the test first. It must fail. A test that passes immediately proves nothing.

```python
# RED: This test fails because the feature doesn't exist yet
@pytest.mark.asyncio
async def test_checkout_out_of_stock_returns_400(override_redis):
    # stock counter at 0 — product sold out
    await override_redis.set("stock:99", 0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/orders/checkout",
                                     json={"items": [{"product_id": 99, "quantity": 1}]},
                                     headers={"Authorization": "Bearer <valid_token>"})
    assert response.status_code == 400  # FAILS until reserve_stock() returns 0 → 400 path is wired
```

### Step 2: GREEN — Make It Pass

Write the minimum code to make the test pass. Don't over-engineer.

### Step 3: REFACTOR — Clean Up

With tests green, improve the code without changing behavior. Run tests after every refactor step.

## The Prove-It Pattern (Bug Fixes)

```
Bug report arrives
    ↓
Write a test that demonstrates the bug (it FAILS)
    ↓
Implement the fix
    ↓
Test PASSES → bug fixed, regression guarded
    ↓
Run full test suite (no regressions)
```

## Test Pyramid

```
      ╱╲
     ╱  ╲       E2E Tests (~5%)
    ╱────╲
   ╱      ╲     Integration Tests (~15%)
  ╱────────╲
 ╱          ╲   Unit Tests (~80%)
╱────────────╲
```

## Project-Specific Guidelines

### FastAPI (fast_api_services/tests/)

- Framework: `pytest` + `pytest-asyncio` + `httpx.AsyncClient`
- Mock Redis with `fakeredis[aioredis]`; mock DB with `AsyncMock` or test DB
- Run: `pytest fast_api_services/tests/`

```python
# Fixture pattern — shared across tests
@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)

@pytest.fixture
def override_redis(fake_redis):
    async def _get_redis_override():
        yield fake_redis
    app.dependency_overrides[get_redis] = _get_redis_override
    yield fake_redis
    app.dependency_overrides.clear()

# Test pattern — checkout with mocked stock gate
@pytest.mark.asyncio
async def test_checkout_reserves_stock(override_redis):
    # Seed stock counter
    await override_redis.set("stock:42", 10)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/orders/checkout", json={"items": [{"product_id": 42, "quantity": 2}]},
                                     headers={"Authorization": "Bearer <valid_token>"})
    assert response.status_code == 201
    assert int(await override_redis.get("stock:42")) == 8
```

### Django (core_service/)

- Framework: `pytest-django`
- Unit tests: no DB access — use `@pytest.mark.django_db` only for integration tests
- Place test files adjacent to source: `core_service/orders/tests/test_services.py`
- Parametrize for multiple cases:

```python
@pytest.mark.parametrize("qty,stock,expected", [
    (1, 5, True),    # normal purchase
    (5, 5, True),    # buy all remaining stock
    (6, 5, False),   # over-stock → should fail
])
def test_create_order_stock_check(qty, stock, expected):
    ...
```

### React (frontend/)

- Framework: Vitest + React Testing Library
- Run: `npm run test` inside `frontend/`
- Never rely on real API — mock with `vi.mock` or MSW
- Components use Material UI; test behavior not MUI internals

## Writing Good Tests

- **Test state, not interactions** — assert on outcomes, not which methods were called
- **DAMP over DRY** — each test should be self-contained and readable
- **Arrange-Act-Assert** pattern
- **One assertion per concept**
- **Descriptive names**: `TestLogin_WrongPassword_ReturnsUnauthorized`

## Anti-Patterns to Avoid

| Anti-Pattern | Fix |
|---|---|
| Testing implementation details | Test inputs and outputs, not internal structure |
| Flaky tests | Use deterministic assertions, isolate test state |
| No test isolation | Each test sets up and tears down its own state |
| Mocking everything | Prefer real implementations > fakes > stubs > mocks |

## Verification

- [ ] Every new behavior has a corresponding test
- [ ] All tests pass: `pytest fast_api_services/tests/` and `npm run test` (inside `frontend/`)
- [ ] Django tests pass: `pytest core_service/`
- [ ] Bug fixes include a reproduction test that failed before the fix
- [ ] Test names describe the behavior being verified
- [ ] No tests were skipped or disabled
