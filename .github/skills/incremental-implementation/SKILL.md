---
name: incremental-implementation
description: Delivers changes incrementally. Use when implementing any feature or change that touches more than one file. Use when you're about to write a large amount of code at once, or when a task feels too big to land in one step.
---

# Incremental Implementation

## Overview

Build in thin vertical slices — implement one piece, test it, verify it, then expand. Each increment should leave the system in a working, testable state.

## When to Use

- Implementing any multi-file change
- Building a new feature from a task breakdown
- Refactoring existing code
- Any time you're tempted to write more than ~100 lines before testing

**When NOT to use:** Single-file, single-function changes where the scope is already minimal.

## The Increment Cycle

```
Implement → Test → Verify → Commit → Next slice
    ↑                                     |
    └─────────────────────────────────────┘
```

For each slice:
1. **Implement** the smallest complete piece of functionality
2. **Test** — run `go test ./...` (or write a test if none exists)
3. **Verify** — confirm the slice works (tests pass, build succeeds)
4. **Commit** — save progress with a descriptive message
5. **Move to the next slice**

## Slicing Strategies

### Vertical Slices (Preferred)

Build one complete path through the stack:

```
Slice 1: Add GetTicketItemById DB query (sqlc SQL + regenerate)
    → go test ./... passes

Slice 2: Add service layer + interface
    → go test ./internal/service/... passes

Slice 3: Add controller + route
    → go build ./... succeeds, manual test via REST

Slice 4: Add unit tests for service
    → go test ./... green, coverage improves
```

### Contract-First Slicing

When defining new features:
```
Slice 0: Define interface in service/interfaces.go
Slice 1: Implement service + unit tests
Slice 2: Implement controller + route
Slice 3: Integration test
```

### Risk-First Slicing

Tackle the riskiest piece first:
```
Slice 1: Prove Redis DECR works for inventory (highest risk for flash sale)
Slice 2: Build Kafka producer on top of proven DECR
Slice 3: Add consumer and order persistence
```

## Implementation Rules

### Rule 0: Simplicity First

Before writing any code, ask: "What is the simplest thing that could work?"

```
✗ Abstract repository factory for two similar Django views
✓ Two straightforward ViewSet methods

✗ Generic Lua script runner for one Redis pattern
✓ Inline eval() call with _HSET_IF_NEWER_SCRIPT constant

✗ Config-driven component factory for three similar React pages
✓ Three straightforward page components
```

### Rule 0.5: Scope Discipline

Touch only what the task requires. If you notice something worth improving outside your scope, note it — don't fix it:

```
NOTICED BUT NOT TOUCHING:
- stream_consumer.py has duplicated error handling (separate task)
- useLivePositions and useWebSocket could be merged (separate refactor)
→ Want me to create tasks for these?
```

### Rule 1: One Thing at a Time

Each commit changes one logical thing. Don't mix:
- Feature + refactor
- Bug fix + formatting
- New behavior + dependency update

### Rule 2: Keep It Working

After each increment:
```bash
pytest fast_api_services/tests/   # FastAPI unit tests must pass
pytest core_service/               # Django tests must pass
npm run test                       # React tests (inside frontend/)
tsc --noEmit                       # TypeScript must compile clean (inside frontend/)
```

### Rule 3: Rollback-Friendly

- Additive changes (new files, new functions) are easy to revert
- Avoid deleting and replacing in the same commit — separate them
- Database schema changes need corresponding rollback migrations

## Working with This Project

When implementing a new Django endpoint:

```
Step 1: Add serializer in core_service/<app>/serializers.py
Step 2: Write unit test (RED — failing)
Step 3: Implement view in core_service/<app>/views.py (GREEN)
Step 4: Register URL in core_service/<app>/urls.py
Step 5: pytest core_service/ + manual test via REST
Step 6: Commit
```

When implementing a new FastAPI endpoint:

```
Step 1: Add schema to fast_api_services/schemas/<domain>.py
Step 2: Write pytest test (RED — failing, uses fakeredis)
Step 3: Implement router in fast_api_services/routers/<domain>.py (GREEN)
Step 4: Register in fast_api_services/main.py
Step 5: pytest fast_api_services/tests/
Step 6: Commit
```

When implementing a new React feature:

```
Step 1: Add API call in frontend/src/api/<domain>.js
Step 2: Implement component/page in frontend/src/pages/<Page>.jsx
Step 3: npm run test (Vitest)
Step 4: Verify in browser (port 3000)
Step 5: Commit
```

## Increment Checklist

After each increment, verify:

- [ ] The change does one thing and does it completely
- [ ] All existing tests still pass: `pytest fast_api_services/tests/` and/or `npm run test` (inside `frontend/`)
- [ ] Django tests pass: `pytest core_service/`
- [ ] TypeScript compiles: `tsc --noEmit` (inside `frontend/`)
- [ ] The new functionality works as expected
- [ ] The change is committed with a descriptive message

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll test it all at the end" | Bugs compound. A bug in Slice 1 makes Slices 2-5 wrong. |
| "It's faster to do it all at once" | Feels faster until something breaks and you can't find which of 500 changed lines caused it. |
| "These changes are too small to commit separately" | Small commits are free. Large commits hide bugs and make rollbacks painful. |
| "This refactor is small enough to include" | Refactors mixed with features make both harder to review. |

## Red Flags

- More than 100 lines written without running tests
- Multiple unrelated changes in a single increment
- "Let me just quickly add this too" scope expansion
- Skipping the test/verify step to move faster
- Build or tests broken between increments
- Touching files outside the task scope "while I'm here"
- Creating new utility files for one-time operations

## Verification

- [ ] Each increment was individually tested and committed
- [ ] Full test suite passes: `pytest fast_api_services/tests/` and `npm run test` (inside `frontend/`)
- [ ] Django tests pass: `pytest core_service/`
- [ ] TypeScript is clean: `tsc --noEmit` (inside `frontend/`)
- [ ] The feature works end-to-end as specified
- [ ] No uncommitted changes remain
