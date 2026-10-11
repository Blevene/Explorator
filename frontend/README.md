# Explorator Frontend

React 19 + TypeScript + Vite frontend for Explorator. See the [root README](../README.md) for what the project is and a tour of the user-facing flow.

## Stack

- **React 19**
- **TypeScript 5** (strict mode)
- **Vite 8** for dev server, HMR, and production builds
- **Tailwind CSS v4** (utility classes via `@tailwindcss/vite`)
- **Zustand 5** for client-side state — one store per concern (session, candidate, arrangement, audio, comparisonAudio, capabilities, export, patternLibrary, patternFilters, genreResearch)
- **Tone.js 15** for browser-side synthesis
- **sonner** for toast notifications
- **Vitest 4** + `@testing-library/react` + `jsdom` for component/store tests

## Aesthetic

Dark "studio monitor" UI — see [`docs/DESIGN.md`](../docs/DESIGN.md) for the full design language (color tokens, typography, interaction patterns).

## Common commands

The dev proxy forwards `/v1` to `$VITE_API_TARGET`, which defaults to `http://localhost:8100` (the E2E backend); point it at `http://localhost:8000` when running `make backend` (`make frontend` from the repo root does this for you).

```bash
npm install               # Install dependencies
VITE_API_TARGET=http://localhost:8000 npm run dev   # Vite dev server on :5173, /v1 proxied to make backend
npm run build             # Production build → dist/  (also runs `tsc -b`)
npm run preview           # Serve the production build (used by E2E)
npm run lint              # ESLint
npm run test:unit         # vitest run (no watch)
npx tsc -b                # Type-check (project references; what npm run build runs)
```

## Project layout

```
src/
├── api/                  # Fetch wrappers + types (mirror backend Pydantic schemas)
├── components/           # React components — leaves are presentational, parents wire to stores
├── hooks/                # Reusable hooks — useGenerationFlow, useRealizationFlow, useMutationFlow, streamSSE
├── lib/                  # toast wrapper, miscellaneous utilities
├── services/             # Cross-cutting services — audio engines, MIDI utils, token-usage event types (sse.ts), services/api.ts
├── stores/               # Zustand stores; one per concern
├── utils/                # designTokens.ts (CSS-var helpers, CANVAS_COLORS); the tokens themselves live in index.css
├── views/                # Page-level views (Dashboard, SessionWorkspace, PatternLibraryBrowser); GenreManagement lives in components/
└── setupTests.ts         # @testing-library/jest-dom + RTL cleanup hook
```

## Conventions

- **No central API client class** — each `src/api/<feature>.ts` exports plain `async` functions. Errors throw on `!res.ok`.
- **Stores are flat** — actions sit alongside state on a single Zustand `create<State>(set, get => ({...}))` call. No middleware unless we add a real reason.
- **Optimistic UI with rollback** — for any user action that hits the backend (delete pattern, toggle curation, submit feedback), flip local state first, call API, reconcile on success, revert + toast on failure. Pattern is consistent across `patternLibraryStore.toggleCuration`, `arrangementStore.toggleCuration`, etc.
- **Toasts via the wrapper** — import from `lib/toast`, never directly from `sonner`. Single-file swap if we ever change libraries.
- **Type mirrors are mandatory** — when a backend Pydantic schema changes, update the matching TS interface in `api/types.ts` or `services/api.ts` in the same commit. Tests will catch the divergence; docstring at the top of `api/types.ts` notes the convention.

## Testing

Run `npm run test:unit` — covers component rendering, store actions, optimistic-rollback edge cases, and a few integration-style tests with mocked fetch. Tests live next to source under `__tests__/` directories.

E2E tests live in `../e2e/` (a separate npm package — install once with `cd ../e2e && npm install && npx playwright install --with-deps chromium`). Run from the repo root: `make e2e-parallel` (no Neo4j needed), or `make neo4j-up && make e2e` for both lanes. The E2E setup rebuilds `dist/` itself. See the root README § Test.
