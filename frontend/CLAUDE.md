@AGENTS.md

# Dashboard (`frontend/`)

Commands (see `README.md`): `npm run dev` (needs `uv run python -m api`
running in `backend/`), `npm run api:types` after any API change,
`npm run typecheck`, `npm run lint`, `npm run build`.

Next.js 16 (App Router), Tailwind, shadcn/ui (Radix base). **Screens only**:
it calls `/api/*` (forwarded to FastAPI by `next.config.ts` in dev, by Caddy
in production) through the typed client in `src/lib/api/` (types generated
from FastAPI's OpenAPI, `npm run api:types`; `backend/tests/test_openapi.py`
fails when stale). Data hooks in `src/lib/queries.ts`; changes go through
`useClinicChange` (toast + refresh). Clinic times are naive clinic-local
strings; never convert them through the browser's timezone
(`src/lib/dates.ts`). Next 16 differs from older versions: read
`node_modules/next/dist/docs/` first (`AGENTS.md`). The dev server serves
scripts only to `localhost` (`allowedDevOrigins` for anything else, e.g. a
tunnel). E2E: `npm run test:e2e` (Playwright on installed Chrome, fresh DB via
`e2e/start-api.sh`, sign-in off). Visual checks without the extension:
`google-chrome --headless=new --screenshot=out.png --window-size=… URL`.
