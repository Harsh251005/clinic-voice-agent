# ClinicDesk (dashboard)

The clinic staff dashboard: Next.js (App Router), Tailwind, shadcn/ui. **It
is only screens.** Every rule, sign-in and access check lives in the Python
API (`../backend/api/dashboard/`), which this app reaches at `/api/*`.

## Run

```bash
# 1. the API, from backend/
uv run python -m api            # serves /api on 127.0.0.1:8080

# 2. the dashboard, from frontend/
npm install
npm run dev                     # http://localhost:3000
```

`/api/*` is forwarded to `API_ORIGIN` (default `http://127.0.0.1:8080`,
see `next.config.ts`), so the browser only ever talks to one origin and the
session cookie is first-party. Sign-in uses Google. For local work without
it, set `DASHBOARD_LOGIN=off` in `backend/.env` (everyone is an admin, and
a *Test mode* note shows).

Google's redirect URI must be `DASHBOARD_URL/api/auth/callback`, i.e.
`http://localhost:3000/api/auth/callback` locally.

## Commands

```bash
npm run api:types   # after changing the API: regenerate src/lib/api/{openapi.json,schema.d.ts}
npm run typecheck   # route types + tsc
npm run lint
npm run build
```

`backend/tests/test_openapi.py` fails if `openapi.json` is stale, so an API
change can't silently break a screen: regenerate and commit both files.

## Layout

```
src/app/                         routes
  page.tsx                       "/": sign in, or go to a clinic
  clinics/[clinicId]/layout.tsx  the signed-in frame (AppShell)
  clinics/[clinicId]/today        home: the day at a glance
  clinics/[clinicId]/appointments, setup
  new-clinic/                    admins only
  admin/                         the operator's admin panel (admins only): health, calls, errors, clinics
src/components/app/              app pieces: shell, gates (sign-in, no access), brand
src/components/admin/            the admin panel's shell (slate ink + amber, never teal) and shared bits
src/components/calls/            a call's transcript as a conversation
src/components/today/            the Today page's panels
src/components/ui/               shadcn/ui components (ours to edit)
src/lib/api/                     typed API client, generated schema
src/lib/queries.ts               data hooks (TanStack Query)
src/lib/admin.ts                 admin panel hooks and the words for outcomes, end reasons, timings
src/lib/dates.ts                 clinic-local dates; 12-hour times for everything staff read
src/lib/clinic-day.ts            open now?, who's in today, setup checklist
src/lib/product.ts               the product name
```

- Dark mode follows the operating system (`globals.css`), like the patient
  call page. Teal on cool slate, with a teal-ink sidebar; `--success` and
  `--warning` colours always come with an icon and a word.
- Words staff read are plain clinic words, never setting names: *time per
  patient*, *pause bookings*, *leave & holidays*, *common questions*,
  *receptionist link*. Times are 12-hour (`time12`, `weekText`).
- On phones the sidebar becomes a top bar and a bottom tab bar.
- Next.js 16 differs from older versions (async `params`, `proxy` instead
  of `middleware`). Read `node_modules/next/dist/docs/` before changing
  framework-level code (see `AGENTS.md`).
