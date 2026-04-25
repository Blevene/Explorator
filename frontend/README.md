# Explorator Frontend

React 19 + TypeScript + Vite frontend for Explorator. See the [root README](../README.md) for what the project is and a tour of the user-facing flow.

## Stack

- **React 19** with the experimental React Compiler enabled
- **TypeScript 5** (strict mode)
- **Vite 7** for dev server, HMR, and production builds
- **Tailwind CSS v4** (utility classes via `@tailwindcss/vite`)
- **Zustand 5** for client-side state — one store per concern (session, candidate, arrangement, audio, comparison, patternLibrary, patternFilters, genreResearch)
- **Tone.js 15** for browser-side synthesis
- **sonner** for toast notifications
- **Vitest 4** + `@testing-library/react` + `jsdom` for component/store tests

## Aesthetic

Dark "studio monitor" UI — see [`docs/DESIGN.md`](../docs/DESIGN.md) for the full design language (color tokens, typography, interaction patterns).

## Common commands

```bash
npm install               # Install dependencies
npm run dev               # Vite dev server (default :5173, proxies /v1 to backend on :8000)
npm run build             # Production build → dist/  (also runs `tsc -b`)
npm run preview           # Serve the production build (used by E2E)
npm run lint              # ESLint
npm run test:unit         # vitest run (no watch)
npx tsc --noEmit          # Type-check without emitting JS
```

## Project layout

```
src/
├── api/                  # Fetch wrappers + types (mirror backend Pydantic schemas)
├── components/           # React components — leaves are presentational, parents wire to stores
├── hooks/                # Reusable hooks — useGenerationFlow, useRealizationFlow, useSSEConsumer
├── lib/                  # toast wrapper, miscellaneous utilities
├── services/             # Cross-cutting services — audio engines, MIDI utils, services/api.ts
├── stores/               # Zustand stores; one per concern
├── styles/               # Global CSS + design-token definitions
├── views/                # Page-level views (Dashboard, SessionWorkspace, PatternLibraryBrowser, GenreManagement)
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

E2E tests live in `../e2e/`. Run from the repo root with `make e2e`.
