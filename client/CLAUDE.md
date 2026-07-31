# Frontend — AILA client

The full token/component reference lives at `docs/frontend/design-system.md`. **Read it before writing any new frontend UI.** Key rules:

- Use design token classes — never raw Tailwind palette values (`text-blue-600`, `bg-zinc-800`, `text-gray-500`, etc.)
- **`bg-brand` ≠ `bg-accent`** — `bg-brand` is for primary CTA button backgrounds; `bg-accent` is for focus rings, active indicators, and selected states only. Mixing these up is the most common mistake.
- `bg-brand-navy` / `hover:bg-brand-navy-dark` are **old non-token classes** that no longer exist — replace with `bg-brand` / `hover:bg-brand-hover`.
- Token-backed classes (`text-ink-*`, `bg-paper`, `bg-brand`, etc.) switch for dark mode automatically — no `dark:` variants needed for colour.
- All button labels, inputs, and UI chrome use `font-ui`; legal content uses `font-serif`.
