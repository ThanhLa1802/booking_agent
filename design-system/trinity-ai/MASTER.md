# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Trinity AI
**Generated:** 2026-10-02 23:06:49
**Category:** Luxury/Premium Brand

---

## Global Rules

### Color Palette

Light mode:

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary (brass) | `#7A5C33` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#4A4A48` | `--color-secondary` |
| Background (ivory) | `#FAF8F4` | `--color-background` |
| Paper / Card | `#FFFFFF` | `--color-card` |
| Foreground | `#1C1917` | `--color-foreground` |
| Muted Foreground | `#57534E` | `--color-muted-foreground` |
| Border / Divider | `#E7E1D8` | `--color-border` |
| Success | `#2F6B4F` | `--color-success` |
| Warning | `#9A6A1E` | `--color-warning` |
| Destructive | `#B3261E` | `--color-destructive` |
| Info | `#3E6B8A` | `--color-info` |

Dark mode:

| Role | Hex |
|------|-----|
| Primary (brass) | `#C9A96A` |
| On Primary | `#14110D` |
| Background | `#14110D` |
| Paper / Card | `#1C1916` |
| Foreground | `#F5F1EA` |
| Muted Foreground | `#A8A29A` |
| Border / Divider | `#2E2925` |
| Success | `#7FB79A` |
| Warning | `#D8B26A` |
| Destructive | `#E08B85` |
| Info | `#8FB2CC` |

**Color Notes:** Warm ivory + single brass accent — a classical music institution.
Implemented in `frontend/src/theme.js` via `getTheme('light' | 'dark')`.

### Typography

- **Heading Font:** Playfair Display
- **Body Font:** Inter
- **Mood:** elegant, luxury, sophisticated, timeless, premium, editorial
- **Google Fonts:** [Playfair Display + Inter](https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&display=swap');
```

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #A16207;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #1C1917;
  border: 2px solid #1C1917;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #FAFAF9;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #1C1917;
  outline: none;
  box-shadow: 0 0 0 3px #1C191720;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Editorial Classical (refined minimalism)

**Keywords:** print-inspired hierarchy, serif display type, hairline rules, generous whitespace, single brass accent, restrained motion, ivory paper

**Best For:** Education, cultural institutions, premium service products, music/classical brands

**Key Effects:** 150–250ms ease transitions, subtle border-colour shifts on hover, serif display headings, uppercase tracked overlines, no heavy shadows or gradients

### Typography Rules

- Display headings (`h1`–`h5`): **Playfair Display** (serif), weight 500, tight tracking.
- UI / body / labels: **Inter** (sans).
- Section labels use `overline` (uppercase, 0.14em tracking) in brass.

### Page Pattern (app)

**Pattern Name:** Editorial app shell

- Fixed top AppBar with wordmark + primary nav + theme toggle.
- Page opens with overline → serif title → one-line subtitle → hairline divider.
- Content in bordered, low-elevation cards/panels; data in airy tables.
- One primary action per view (brass filled button); secondary actions outlined.
- Empty / loading states are quiet and centred.

Implemented in: `frontend/src/theme.js`, `frontend/src/index.css`,
shared components (`Navbar`, `AuthLayout`, `ChatBubble`, `ConfirmBanner`).

---

## Anti-Patterns (Do NOT Use)

- ❌ Cheap visuals
- ❌ Fast animations

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
