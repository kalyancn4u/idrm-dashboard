# Design System

Slate + Emerald · Light mode · WCAG AAA.

## 1. Principles

1. **Contrast is not negotiable.** Every body-text pair is ≥ 7:1.
2. **Colour carries meaning, never alone.** Severity always pairs colour with a
   text label and a dot.
3. **One primary action per surface.** Green buttons are the action; everything
   else is outline or ghost.
4. **Density with air.** Tables are compact but rows have 0.75rem vertical padding.
5. **Motion is a hint, not a feature.** Transitions are 140–220 ms and respect
   `prefers-reduced-motion`.

## 2. Design tokens

### Colour

| Token | Value | Use |
|---|---|---|
| `--color-bg-page` | `#f8fafc` | page background |
| `--color-bg-surface` | `#ffffff` | cards, tables |
| `--color-bg-surface-elevated` | `#f1f5f9` | table headers, chips |
| `--color-text-heading` | `#0f172a` | h1–h4 |
| `--color-text-body` | `#334155` | paragraphs |
| `--color-text-muted` | `#64748b` | metadata |
| `--color-primary` | `#059669` | emerald — actions, links |
| `--color-primary-hover` | `#047857` | hover |
| `--color-primary-light` | `#d1fae5` | active nav, highlights |
| `--color-primary-dark` | `#065f46` | text on light emerald |

### Severity

| Token | Value | Contrast on white |
|---|---|---|
| `--sev-critical` | `#b91c1c` | 7.6:1 |
| `--sev-high` | `#c2410c` | 7.1:1 |
| `--sev-medium` | `#b45309` | 7.0:1 |
| `--sev-low` | `#047857` | 7.2:1 |

All four pass AAA for normal text.

### Spacing scale

`--space-1` 0.25rem → `--space-16` 4rem, in a 4-px-derived rhythm.

### Type scale

| Token | Size | Weight | Use |
|---|---|---|---|
| `--font-size-4xl` | 2.25rem | 800 | page titles |
| `--font-size-3xl` | 1.875rem | 800 | profile names |
| `--font-size-2xl` | 1.5rem | 700 | finding titles |
| `--font-size-lg` | 1.125rem | 700 | section titles |
| `--font-size-base` | 1rem | 400 | body |
| `--font-size-sm` | 0.875rem | 400/600 | tables, buttons |
| `--font-size-xs` | 0.75rem | 600/700 | labels, badges |

Font: **Inter** (variable), loaded from Google Fonts with `display=swap`.

## 3. Components

### `kpi_card(label, value, meta, tone, icon, href)`

The dashboard metric card. Tones: `emerald`, `slate`, `critical`, `warning`, `info`, `review`.
A 4 px left accent bar carries the tone; the value is 2.25 rem / 800.

### `badge` and severity chips

`.badge` is the base; `.badge-success` / `-warning` / `-error` / `-info` / `-review`
supply the tone. Severity chips additionally carry a `.sev-dot`.

### `alert`

Left border 5 px, tinted background, icon, title, message, optional dismiss button.
Variants: `alert-success`, `alert-warning`, `alert-error`, `alert-info`, `alert-review`.

### `data-table`

Sticky header, uppercase 0.7 rem column labels, hover row tint. Row variants:
`.row-priv` (amber tint), `.row-overdue` (red tint).

### `risk_pill(score)`

A number plus a 46 px bar. Colour band from the score, so the reader gets both
the precise value and the visual band.

### `timeline`

Vertical rule, coloured dots (emerald / amber / red by severity), message plus
actor and timestamp. Optional `<details>` containing a before/after JSON diff.

### `progress(pct)`

9 px track with an emerald→light-emerald gradient. Variants `progress-critical`
and `progress-warning`.

### `state-container`

Empty / loading / error states. Dashed border, large icon, title, description,
optional action.

## 4. Layout

```
.app-shell        grid: 264px sidebar | 1fr
  .app-sidebar    sticky, 100vh, scrollable
  .app-main       flex column
    .app-topbar   sticky, 64px, backdrop-blur
    .app-content  padding 1.5rem, max-width 1440px, centred
    .app-footer   bordered, small text
```

Responsive breakpoints:

| Width | Behaviour |
|---|---|
| ≥ 1025px | sidebar visible, grid 2/3/4 columns available |
| 641–1024px | sidebar becomes an off-canvas drawer, hamburger appears |
| ≤ 640px | KPI grid collapses to 2 columns, filters stack, user name hidden |

## 5. Accessibility checklist

| Requirement | Implementation |
|---|---|
| Contrast ≥ 7:1 for body text | All body/muted pairs verified; see §2 |
| Focus visible | `*:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }` |
| Semantic landmarks | `<aside>`, `<header>`, `<main>`, `<footer>`, `<nav>` |
| Table headers | `<th>` with `scope` implied by `<thead>` |
| Form labels | Every input has a `<label for>` |
| Required fields | `.form-label.required::after` adds `*`; the input also carries `required` |
| Error identification | `.form-error` with the message in text, not colour alone |
| Status messages | `role="status"` on flash alerts |
| Progress bars | `role="progressbar"` with `aria-valuenow/min/max` |
| Icon-only buttons | `aria-label` on every one |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` kills transitions |
| Keyboard shortcuts | `/` focuses the first search input; `Esc` closes the drawer |
| Skip navigation | Sidebar links are the first focusable elements |

## 6. Adding a component

1. Add tokens to `:root` if new colours or sizes are needed.
2. Add the CSS block to `design-system.css` under a `/* ---- NAME ---- */` banner.
3. If it's reusable in templates, add a macro to `components/_macros.html`.
4. Verify contrast with a checker before committing.
5. Test at 320 px, 768 px, 1440 px.

## 7. Do / don't

| Do | Don't |
|---|---|
| Use `--color-primary` for the single primary action | Use green for decorative elements |
| Pair severity colour with a text label | Rely on red alone to signal "critical" |
| Use `--space-*` tokens | Hard-code `margin: 13px` |
| Keep tables to ≤ 9 columns | Let tables scroll horizontally if avoidable |
| Put the KPI value at 2.25 rem / 800 | Use 5 rem display type |

## 8. Next

→ [API Reference](09-api-reference.md)

