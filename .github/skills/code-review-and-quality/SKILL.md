---
name: code-review-and-quality
description: Conducts multi-axis code review. Use before merging any change. Use when reviewing code written by yourself, another agent, or a human. Use when you need to assess code quality across multiple dimensions before it enters the main branch.
---

# Code Review and Quality

## Overview

Multi-dimensional code review with quality gates. Every change gets reviewed before merge — no exceptions. Review covers five axes: correctness, readability, architecture, security, and performance.

**The approval standard:** Approve a change when it definitely improves overall code health, even if it isn't perfect.

## When to Use

- Before merging any PR or change
- After completing a feature implementation
- When reviewing code produced by an agent
- After any bug fix (review both the fix and the regression test)

## The Five-Axis Review

### 1. Correctness

- Does it match the spec or task requirements?
- Are edge cases handled (nil, empty, boundary values)?
- Are error paths handled (not just the happy path)?
- Are there race conditions or state inconsistencies?
- Do tests actually test the right things?

### 2. Readability & Simplicity

- Are names descriptive and consistent with project conventions?
- Is the control flow straightforward (no deep nesting)?
- Could this be done in fewer lines?
- Are abstractions earning their complexity?
- No dead code artifacts (unused variables, commented-out blocks)?

### 3. Architecture

- Does it follow existing patterns or introduce a new one? If new, is it justified?
- Does it maintain clean module boundaries?
- Are dependencies flowing in the right direction (no circular imports)?
- Is the abstraction level appropriate (not over-engineered, not too coupled)?

### 4. Security

See `security-and-hardening` skill. Key checks:
- Is user input validated at boundaries?
- Are secrets kept out of code and logs?
- Is auth/authz checked?
- Are external inputs treated as untrusted?

### 5. Performance

See `performance-optimization` skill. Key checks:
- Any N+1 query patterns?
- Any unbounded loops or unconstrained data fetching?
- Any missing pagination on list endpoints?
- Any heavy operations in hot paths?

## Review Process

### Step 1: Understand the Context
- What is this change trying to accomplish?
- What spec or task does it implement?

### Step 2: Review the Tests First
- Do tests exist for the change?
- Do they test behavior (not implementation details)?
- Are edge cases covered?

### Step 3: Review the Implementation
Walk through the code with the five axes in mind.

### Step 4: Categorize Findings

| Prefix | Meaning | Author Action |
|--------|---------|---------------|
| *(no prefix)* | Required change | Must address before merge |
| **Critical:** | Blocks merge | Security vulnerability, data loss, broken functionality |
| **Nit:** | Minor, optional | Author may ignore |
| **Consider:** | Suggestion | Worth considering but not required |

### Step 5: Verify the Build Gate

For this project, every change must pass:
```bash
# FastAPI
pytest fast_api_services/tests/

# Django
pytest core_service/

# React
npm run test        # inside frontend/
tsc --noEmit        # inside frontend/
```

## Change Sizing

```
~100 lines changed   → Good. Reviewable in one sitting.
~300 lines changed   → Acceptable if it's a single logical change.
~1000 lines changed  → Too large. Split it.
```

**Separate refactoring from feature work.** Never mix formatting changes with behavior changes.

## Dead Code Hygiene

After any refactoring, identify orphaned code and ask before deleting:
```
DEAD CODE IDENTIFIED:
- formatLegacyDate() — replaced by formatDate()
→ Safe to remove these?
```

## The Review Checklist

```markdown
### Correctness
- [ ] Change matches spec/task requirements
- [ ] Edge cases handled (nil pointer, empty slice, boundary values)
- [ ] Error paths handled
- [ ] Tests cover the change

### Readability
- [ ] Names are clear and consistent
- [ ] No unnecessary complexity
- [ ] No dead code

### Architecture
- [ ] Follows existing patterns
- [ ] No circular imports
- [ ] Appropriate abstraction level

### Security
- [ ] No secrets in code
- [ ] Input validated at boundaries
- [ ] Auth checks in place

### Performance
- [ ] No N+1 patterns
- [ ] Pagination on list endpoints

### Verification
- [ ] `pytest fast_api_services/tests/` passes
- [ ] `pytest core_service/` passes
- [ ] `tsc --noEmit` passes (frontend/)
- [ ] `npm run test` passes (frontend/)
```

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It works, that's good enough" | Working code that's insecure or architecturally wrong creates debt. |
| "AI-generated code is probably fine" | AI code needs more scrutiny, not less. |
| "The tests pass, so it's good" | Tests are necessary but not sufficient. |

## Red Flags

- PRs merged without any review
- "LGTM" without evidence of actual review
- Security-sensitive changes without security-focused review
- No regression tests with bug fix PRs
- Accepting "I'll fix it later" — it never happens

## Verification

- [ ] All Critical issues are resolved
- [ ] Django tests pass: `pytest core_service/`
- [ ] FastAPI tests pass: `pytest fast_api_services/tests/`
- [ ] React tests pass: `npm run test` (inside `frontend/`)
- [ ] TypeScript compiles: `tsc --noEmit` (inside `frontend/`)
