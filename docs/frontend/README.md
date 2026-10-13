# Frontend (`client/`)

The AILA web client: one React single-page app shared by every bot.

## Stack

React 19 and React Router, built with Vite 7. Styling is Tailwind CSS 3 over the design tokens in
`src/index.css`. Answers render through `react-markdown` (with `remark-gfm`), the Admin Portal's
charts use Recharts, and the matter-notes editor is TipTap. API calls go through axios and `fetch`
(the chat stream). Plain JavaScript (`.jsx`), no TypeScript.

## Building and deploying

The target server has no Node.js, so the client is built on the dev machine and the build is
committed. With Node.js on PATH (the dev machine uses a portable Node.js v22, which
`deployment/install_node.ps1` installs):

```bash
cd client
npm run build            # writes client/dist/
cd ..
git add -f client/dist/  # dist/ is gitignored, so force-add it
```

Commit `client/dist/` with the source change and push; the target picks it up on `git pull`. The
backend serves `client/dist` itself: `/assets` as static files, any other non-API path as
`index.html`, so the app is reached at the bot's own address (e.g. `http://localhost:8000`).

For development, `npm run dev` starts the Vite dev server with hot reload and proxies `/api` to a
backend on `http://localhost:8000`. `npm run lint` runs ESLint.

## Dynamic branding

There is one build for all bots. On load, `hooks/useBotIdentity.js` calls `GET /api/bot-info` and
takes the bot's name, tagline, research mode, release version and build, and optional `logo_emoji`
and `brand_color` from it; it sets the page title, and the favicon from the emoji or, failing that,
from `GET /api/bot/logo`. Both endpoints are public and read the bot's `bot_config.json`.

The research mode decides which filters and labels the app shows: blank is the legislation bot,
`parliamentary_records` the Holyrood bot and `westminster_records` the Westminster bot
(`isParliament`, `isHolyrood` and `isWestminster` in `App.jsx`).

## Where things live

| Path | What it holds |
|---|---|
| `src/main.jsx` | Entry point: mounts `App` inside the router. |
| `src/App.jsx` | Routes (`/`, and `/systemchat`, a bare test page for `/api/system/chat`), the main chat screen, sidebar, filters and the top-level modals. |
| `src/components/` | Chat UI (`ChatMessage`, `Composer`, `Sidebar`, `SourcesRail`, `SuggestedQuestions`, `DeepResearchPlan`) and the modals (About, Release notes, Data sources, Research filters, Settings menu, Matters, feedback). `components/ui/` holds the shared primitives: `Card`, `Modal`, `Spinner`, `InfoTip`, buttons and icons. |
| `src/hooks/` | State moved out of `App.jsx`: `useChat` (the chat flow: messages, send, stop, load), `useChatRuns` (several chats researching at once), `useFilters`, `usePreferences`, `useMatters`, `useModals`, `useBotIdentity`. |
| `src/context/AuthContext.jsx` | Login state, and logout on a 401. |
| `src/pages/` | Full-screen views: `AdminPortal.jsx`, `Settings.jsx`, `SystemChat.jsx`. |
| `src/pages/admin/` | The Admin Portal's tabs and panels: Developer (provider config, feature flags, exports, backup status, Danger Zone, scoped restore), Efficiency, Cost, Cache, Performance, Data Coverage, Session feedback. |
| `src/constants/research.js` | Filter option lists: record types, Holyrood sessions and Westminster Parliaments, jurisdictions, legislation types. |
| `src/services/api.js` | Every call to the backend, including the `/api/chat` SSE stream. |
| `src/utils/` | `exportChat.js` (copy, export and the thinking/suggestions strippers), `csv.js`, `format.js`. |

## Styling rules

Use the design-token classes, never raw Tailwind palette colours; `bg-brand` (primary buttons) and
`bg-accent` (focus and selected states) are not interchangeable. The short rules are in
`client/CLAUDE.md`; the full token and component reference is
[design-system.md](design-system.md).
