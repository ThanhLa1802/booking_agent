---
name: performance-optimization
description: Optimizes application performance. Use when performance requirements exist, when you suspect performance regressions, or when load test results show bottlenecks. Use when profiling reveals issues that need fixing.
---

# Performance Optimization

## Overview

Measure before optimizing. Performance work without measurement is guessing. Profile first, identify the actual bottleneck, fix it, measure again. Optimize only what measurements prove matters.

## When to Use

- Performance requirements exist (response time SLAs, RPS targets)
- Load tests reveal degradation (k6, benchmark results)
- You suspect a change introduced a regression
- Building features that handle large datasets or high traffic

**When NOT to use:** Don't optimize before you have evidence of a problem.

## The Optimization Workflow

```
1. MEASURE  → Establish baseline (k6 load test, query timing)
2. IDENTIFY → Find the actual bottleneck
3. FIX      → Address the specific bottleneck
4. VERIFY   → Measure again, confirm improvement
5. GUARD    → Add test or monitoring to prevent regression
```

## Project-Specific Profiling

```bash
# Django — query profiling (dev only)
pip install django-debug-toolbar
# Add to INSTALLED_APPS + MIDDLEWARE in core_service/core/settings.py

# FastAPI — check endpoint timing
curl -w "@curl-format.txt" -s -o /dev/null http://localhost:8001/products

# Redis — monitor commands in real time
docker exec -it <redis-container> redis-cli MONITOR

# k6 load tests (in k6/ folder)
k6 run k6/smoke.js           # quick sanity check
k6 run k6/load.js            # steady-state load
k6 run k6/flash_sale.js      # spike test (stock exhaustion scenario)
k6 run k6/soak.js            # extended duration test
```

## Common Bottlenecks (This Project)

### N+1 on Cart/Order Reads

```python
# BAD: one DB query per cart item to load product
for item in cart_items:
    product = await db.get(Product, item.product_id)

# GOOD: single JOIN or IN query for all products
result = await db.execute(
    select(Product).where(Product.id.in_([i.product_id for i in cart_items]))
)
```

### Unbounded Product Listing

```python
# BAD: no pagination — returns all products
result = await db.execute(select(Product))

# GOOD: offset/limit pagination on list endpoints
result = await db.execute(select(Product).offset(skip).limit(limit))
```

### Redis Stock Gate — Lua Atomicity

```python
# BAD: race-prone check-then-decrement (two round-trips)
stock = await redis.get(f"stock:{product_id}")
if int(stock) >= qty:
    await redis.decrby(f"stock:{product_id}", qty)

# GOOD: single atomic Lua script (already in services/stock_cache.py)
result = await reserve_stock(redis, product_id, qty)
# returns 1=reserved, 0=out-of-stock, -1=cache miss
```

### Cache Miss Fallback on Checkout

```python
# If reserve_stock() returns -1 (cache miss), fall back to DB
# warm_all_products() runs at startup to pre-fill stock:{id} keys
# Per-request fallback: load from DB then set Redis key before retry
```

### Async Redis in FastAPI

```python
# BAD: sync redis in async FastAPI handler — blocks event loop
import redis
r = redis.Redis(...)  # sync client

# GOOD: async client from connection pool
import redis.asyncio as aioredis
redis: Redis = Depends(get_redis)  # async pool, shared across requests
```

### Elasticsearch Query Efficiency

```python
# BAD: match_all with no filter — scans entire index
{"query": {"match_all": {}}}

# GOOD: multi_match on indexed fields (name, description) with filters
{"query": {"multi_match": {"query": q, "fields": ["name^2", "description"]}}}
```

## k6 Thresholds for This Project

```javascript
// k6/load.js — steady-state thresholds
thresholds: {
    http_req_failed:   ['rate<0.01'],     // < 1% error rate
    http_req_duration: ['p(95)<300'],     // p95 < 300ms for product reads
}

// k6/flash_sale.js — spike / stock exhaustion
thresholds: {
    http_req_failed:   ['rate<0.05'],     // allow up to 5% 409/400 (expected OOS)
    http_req_duration: ['p(95)<500'],     // checkout under spike load
}
```

## Performance Budget

```
GET /products (ES search):    p95 < 100ms  (Elasticsearch)
GET /products/:id:            p95 < 50ms   (PostgreSQL async)
POST /orders/checkout:        p95 < 500ms  (Redis Lua + Django write)
POST /cart/add:               p95 < 100ms  (PostgreSQL async)
```

## Red Flags

- Optimization without profiling data (measure first)
- N+1 query patterns on cart items or order items
- List endpoints without pagination (products, orders, reviews)
- Sync Redis client used in async FastAPI handlers
- `select_related`/`prefetch_related` missing on Django ORM queries with related objects
- DB check-then-decrement for stock (must use Lua atomic script)
- Elasticsearch `match_all` on large product catalogs without filters

## Verification

- [ ] Before and after measurements exist (specific numbers)
- [ ] The specific bottleneck is identified and addressed
- [ ] Existing tests still pass: `pytest fast_api_services/tests/`
- [ ] k6 thresholds pass at target load
