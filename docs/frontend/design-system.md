# LexChat Design System

A reference for building consistent UI in LexChat. All design tokens are CSS custom properties defined in `index.css` and exposed as Tailwind utilities via `tailwind.config.js`. Use the Tailwind classes — not raw hex values or inline CSS var references — in new code.

---

## Principles

- **One source of truth**: every colour, shadow, and radius comes from a CSS var. Tailwind maps to those vars — not the other way around.
- **Dark mode is free**: token-backed classes switch automatically under `.dark`. Never add `dark:` variants for colours that use a token (e.g. `dark:text-white` is wrong; `text-ink-900` is correct).
- **Legal character**: Inter for UI chrome, Source Serif 4 for legal content, JetBrains Mono for code and system output. The serif/mono choices signal document-grade fidelity.

---

## Colours

### Brand vs Accent

Two blues serve distinct roles and must not be mixed up:

| Role | Token | Tailwind | When to use |
|---|---|---|---|
| Primary action (CTA) | `--brand` | `bg-brand`, `text-brand` | Button backgrounds, primary links, selected nav items |
| Interactive state | `--accent` | `bg-accent`, `text-accent` | Focus rings, active indicators, hover highlights |

**Brand** is the deep authoritative navy (≈ rgb 0, 60, 130) — it carries weight and authority. Use it where a user takes an action.

**Accent** is a lighter mid-blue — it shows that something is selected, focused, or in progress. Use it for `:focus-visible` rings, active sidebar items, loading indicators.

### Full Colour Reference

| CSS var | Tailwind | Use |
|---|---|---|
| `--brand` | `bg-brand` / `text-brand` | Primary CTA buttons |
| `--brand-hover` | `bg-brand-hover` | Button hover state |
| `--brand-soft` | `bg-brand-soft` | Selected sidebar rows, subtle brand tints |
| `--accent` | `bg-accent` / `text-accent` | Focus rings, active indicators |
| `--accent-hover` | `bg-accent-hover` | Accent element hover |
| `--accent-soft` | `bg-accent-soft` | Link / accent hover backgrounds |
| `--accent-ink` | `text-accent-ink` | Readable accent text on light backgrounds |
| `--ink-900` | `text-ink-900` | Primary body text |
| `--ink-800` | `text-ink-800` | Strong body text, headings |
| `--ink-600` | `text-ink-600` | Secondary / muted text |
| `--ink-500` | `text-ink-500` | Placeholder-weight text |
| `--ink-400` | `text-ink-400` | Placeholder text, disabled labels |
| `--ink-300` | `border-ink-300` | Strong borders, dividers |
| `--ink-200` | `border-ink-200` | Default borders |
| `--ink-100` | `bg-ink-100` | Zebra rows, subtle dividers |
| `--ink-50` | `bg-ink-50` | Hover state on white surfaces |
| `--ink-25` | `bg-ink-25` | Barely-there tint |
| `--paper` | `bg-paper` | Card / modal / panel surface |
| `--bg-app` | `bg-bg-app` | App chrome background |
| `--cite` | `text-cite` | Citation links and source references |
| `--cite-soft` | `bg-cite-soft` | Citation chip backgrounds |
| `--success` | `text-success` | Positive status text |
| `--success-soft` | `bg-success-soft` | Positive badge / alert background |
| `--warn` | `text-warn` | Warning status text |
| `--warn-soft` | `bg-warn-soft` | Warning badge / alert background |
| `--danger` | `text-danger` | Error / destructive text |
| `--danger-soft` | `bg-danger-soft` | Error badge / alert background |
| `--legal-gold` | `text-legal-gold` | Brand accent, decorative highlights |

### Rules

- Never use raw Tailwind palette utilities (`text-blue-600`, `bg-zinc-800`, `text-gray-500`) in new code — use the tokens above.
- The `--ink-*` scale inverts in dark mode. `text-ink-900` is near-black in light mode and near-white in dark mode.
- `bg-paper` and `bg-bg-app` switch automatically — no `dark:bg-zinc-800` needed.

---

## Typography

Three font families, each with a distinct purpose:

| Family | CSS var | Tailwind | Purpose |
|---|---|---|---|
| Inter | `--font-ui` | `font-ui` | All UI chrome: labels, buttons, forms, navigation |
| Source Serif 4 | `--font-serif` | `font-serif` | Legal content: chat responses, citations, document headings |
| JetBrains Mono | `--font-mono` | `font-mono` | Code blocks, tool output, system messages |

### Type Scale

| Role | Tailwind classes | Notes |
|---|---|---|
| Display | `font-serif text-display` | 2rem / 700 — legal document headings, hero text |
| Heading 1 | `font-ui text-xl font-semibold` | Page titles, modal titles |
| Heading 2 | `font-ui text-base font-semibold` | Card headers, section headings |
| Heading 3 | `font-ui text-sm font-semibold` | Group labels, subsection headings |
| Body | `font-ui text-sm` | 0.875rem — default prose, form text |
| Body tight | `font-ui text-[0.9375rem]` | 15px — chat messages (slightly larger for readability) |
| Secondary | `font-ui text-xs text-ink-600` | Metadata, timestamps, helper text |
| Label | `font-ui text-label uppercase tracking-wide text-ink-600` | 0.6875rem — column headers, tag text, caps-lock labels |
| Code | `font-mono text-sm` | Code blocks, inline code, system output |
| Citation | `font-serif text-sm italic text-cite` | Quoted legal text |

---

## Spacing

Tailwind's default scale (4px base). Stick to these steps — avoid one-off values like `p-5` or `m-7` unless genuinely required.

| Value | Tailwind | Use |
|---|---|---|
| 4px | `p-1` / `gap-1` | Icon nudges, tight inline gaps |
| 8px | `p-2` / `gap-2` | Compact list items, badge padding |
| 12px | `p-3` / `gap-3` | Form field internal padding |
| 16px | `p-4` / `gap-4` | Card / panel internal padding |
| 24px | `p-6` / `gap-6` | Section spacing, modal padding |
| 32px | `p-8` / `gap-8` | Large section gaps, page margins |

---

## Border Radius

| Token | Value | Tailwind | Use |
|---|---|---|---|
| `--r-sm` | 6px | `rounded-sm` | Inputs, small chips, tags |
| `--r-md` | 8px | `rounded-md` | Buttons, dropdowns, tooltips |
| `--r-lg` | 12px | `rounded-lg` | Cards, panels, popovers |
| `--r-xl` | 16px | `rounded-xl` | Large modals, overlay sheets |
| — | 9999px | `rounded-full` | Circular avatars, filter pills, badges |

---

## Shadows

| Token | Tailwind | Use |
|---|---|---|
| `--shadow-sm` | `shadow-sm` | Subtle lift — focused inputs, tooltips |
| `--shadow-md` | `shadow-md` | Cards, dropdowns, modals |

---

## Component Anatomy

Reference class strings for each primitive. These are not enforced by a shared component — they define what the component *should* look like when implemented.

### Button

```
Primary
  bg-brand text-white font-ui text-sm font-medium rounded-md px-4 py-2
  hover:bg-brand-hover
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1
  disabled:opacity-50 disabled:cursor-not-allowed

Secondary
  bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2
  hover:bg-ink-50
  focus-visible:ring-2 focus-visible:ring-accent

Ghost
  text-accent-ink font-ui text-sm rounded-md px-3 py-1.5
  hover:bg-accent-soft
  focus-visible:ring-2 focus-visible:ring-accent

Danger
  bg-danger text-white font-ui text-sm font-medium rounded-md px-4 py-2
  hover:opacity-90
  focus-visible:ring-2 focus-visible:ring-danger
```

### Input

```
Default
  border border-ink-200 rounded-sm px-3 py-2 font-ui text-sm bg-paper text-ink-900
  placeholder:text-ink-400
  focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent

Error
  border-danger focus:ring-danger-soft

Disabled
  bg-ink-50 text-ink-400 cursor-not-allowed opacity-70
```

### Card

```
bg-paper rounded-lg shadow-md border border-ink-100 p-4
```

### Badge

```
Success  bg-success-soft text-success  rounded-full px-2 py-0.5 font-ui text-label uppercase tracking-wide
Warning  bg-warn-soft    text-warn     rounded-full px-2 py-0.5 font-ui text-label uppercase tracking-wide
Danger   bg-danger-soft  text-danger   rounded-full px-2 py-0.5 font-ui text-label uppercase tracking-wide
Neutral  bg-ink-100      text-ink-600  rounded-full px-2 py-0.5 font-ui text-label uppercase tracking-wide
Cite     bg-cite-soft    text-cite     rounded-full px-2 py-0.5 font-ui text-label uppercase tracking-wide
```

### Modal

```
Overlay   fixed inset-0 bg-ink-950/40 z-50

Content   bg-paper rounded-xl shadow-md p-6 max-w-lg w-full mx-auto
          (rendered inside the overlay, typically centred with flex)
```

### Icon Button (ToolBtn / IBtn pattern)

```
Default   size-[30px] flex items-center justify-center rounded-md
          text-ink-500 hover:bg-ink-100 hover:text-ink-900
          focus-visible:ring-2 focus-visible:ring-accent

Active    bg-accent text-white

Error     bg-danger-soft text-danger
```

### Filter Pill

```
Inactive  border border-ink-200 text-ink-600 rounded-full px-3 py-1 font-ui text-xs
          hover:bg-ink-50

Active    bg-accent text-white border-transparent rounded-full px-3 py-1 font-ui text-xs
```

---

## Dark Mode Rules

1. Colours that come from a CSS token (`text-ink-*`, `bg-paper`, `bg-brand`, etc.) switch automatically — **no `dark:` needed**.
2. Use `dark:` only for properties that have no token equivalent (e.g. `dark:shadow-none`, `dark:divide-ink-700`).
3. Never hardcode `dark:bg-zinc-800` or `dark:text-white` — replace with the token equivalent (`bg-paper`, `text-ink-900`).

---

## Migration Status

The initial token migration across all existing components is **complete** (May 2026). Every button, input, and modal in the app now uses design-system tokens.

Files audited and migrated:
- `client/src/components/LoginModal.jsx`
- `client/src/components/SettingsMenuModal.jsx`
- `client/src/components/HistoryModal.jsx`
- `client/src/components/CommentModal.jsx`
- `client/src/components/ChatMessage.jsx`
- `client/src/components/CreateMatterModal.jsx`
- `client/src/components/MatterNotesModal.jsx`
- `client/src/components/WeeklyFeedbackBanner.jsx`
- `client/src/App.jsx` (IBtn, GhostBtn primitives; send/stop/new-chat buttons; all modal close Xs)
- `client/src/pages/AdminPortal.jsx`
- `client/src/pages/Settings.jsx`

When adding new components, follow the patterns in this document from the start — no migration needed.
