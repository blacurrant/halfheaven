# halfheaven — frontend (halfheaven) + backend (halfhell)

Split architecture — **prod quality**:

```
halfheaven/   frontend  Next.js 14+   name: halfheaven  (root is Next.js app, BFF to halfhell)
halfhell/     backend   FastAPI + Python pipeline  name: halfhell
  app/        -> FastAPI service that owns fingerprint, pipeline, scoring, chat
  halfheaven/ -> pipeline package (was halfheaven/packages/pipeline, now vendored in halfhell)
```

## Why split

- `halfheaven` was a monorepo where Next.js api routes spawned `python -m halfheaven.cli` directly. That couples Node and Python, breaks horizontal scaling, and has no auth.
- Now `halfhell` is a standalone HTTP service with **API-key auth**, **CORS**, **rate-limit**, **request-id**, **health probes**, and `halfheaven` is a thin BFF that proxies with the key server-side.

Browser never sees `HALFHELL_API_KEY`.

## Running locally (both services)

### 1. Generate shared API key

```bash
openssl rand -hex 32  # copy output
```

Put same key in **both** places:

- `halfhell/.env` → `HALFHELL_API_KEY=<key>` (+ `GROQ_API_KEY=…`)
- `halfheaven/.env.local` → `HALFHELL_API_KEY=<key>` and `HALFHELL_API_URL=http://localhost:8000`

`cp halfhell/.env.example halfhell/.env` and `cp halfheaven/.env.example halfheaven/.env.local` then edit.

### 2. Backend

```bash
cd halfhell
python -m venv .venv && source .venv/bin/activate
pip install -e .
# or: pip install fastapi uvicorn pydantic pydantic-settings python-multipart httpx requests opencv-python-headless scenedetect pillow
uvicorn app.main:app --reload --port 8000
# health:
curl http://localhost:8000/health
curl -H "X-API-Key: $HALFHELL_API_KEY" http://localhost:8000/v1/styles | jq
```

Docs when `HALFHELL_ENV=development` (default exposes `/docs`): `http://localhost:8000/docs`

### 3. Frontend

```bash
cd halfheaven
npm install
npm run dev  # -> http://localhost:3000
# studio: http://localhost:3000/studio
# landing: http://localhost:3000/
```

Frontend `npm run build` type-checks against halfhell client (`src/lib/halfhell.ts:1`).

## API contract

All `/v1/*` require auth: `X-API-Key: <key>` or `Authorization: Bearer <key>`.
Responses use envelope `{"error":{"code","message"}}` and `X-Request-Id`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | no | liveness |
| GET | `/ready` | no | readiness (work dir + groq) |
| POST | `/v1/fingerprint` | key | upload `reference` video → `{id}` |
| GET | `/v1/fingerprint/{id}` | key | poll reading |
| POST | `/v1/jobs` | key | multipart `target` (+ `fingerprint_id` or `styleId`) → `{id}` |
| GET | `/v1/jobs` | key | list |
| GET | `/v1/jobs/{id}` | key | status + tail |
| GET/POST | `/v1/jobs/{id}/captions` | key | edit captions + recut |
| POST | `/v1/jobs/{id}/look` | key | `{preset}` → recut |
| POST | `/v1/jobs/{id}/music` | key | `track` file or `remove=1` |
| GET | `/v1/jobs/{id}/media?v=before\|after` | key | stream mp4 (Range) |
| GET | `/v1/jobs/{id}/thumbs` | key | sprite sheet |
| GET | `/v1/jobs/{id}/timeline` | key | shots/captions |
| POST | `/v1/chat` | key | `{message, profile}` → `{reply, overrides, changed}` |
| POST | `/v1/score` | key | `{jobId}` → score card |
| GET | `/v1/looks` | key | looks catalogue |
| GET | `/v1/styles` | key | preset styles |
| POST | `/v1/waitlist` | key | waitlist |
| GET | `/v1/demo` | key | seeded demo |

Frontend BFF at `src/app/api/*` proxies to these with `HALFHELL_API_KEY` server-side, preserving the browser contract (`POST /api/jobs` etc) so no studio page change was needed beyond sending `fingerprint_id` alongside `referencePath`.

## Security / prod checklist

- **No secrets in repo** — `.env` gitignored, `.env.example` is the contract.
- **Key rotation**: set `HALFHELL_API_KEYS=old,new` comma list on backend, roll frontend to `new`, then drop `old`.
- **CORS allow-list**: `HALFHELL_CORS_ORIGINS=http://localhost:3000,https://yourdomain.com`
- **Rate limit**: `HALFHELL_RATE_LIMIT=60/minute` (in-memory per-key/IP; replace with Redis for multi-instance).
- **File guards**: `HALFHELL_MAX_UPLOAD_MB=500`, mime checks, path-traversal rejection on `referencePath`.
- **Docs gated**: `HALFHELL_EXPOSE_DOCS=0` in production → `/docs` 404.
- **Logs**: `HALFHELL_LOG_LEVEL=info`, `X-Request-Id` on every response, structured `rid=… method=… status=… dur_ms=…`.

## Docker (full stack)

```bash
# from halfhell/
cp .env.example .env  # fill GROQ_API_KEY + HALFHELL_API_KEY
docker compose up --build
# or: docker build -t halfhell . && docker run -p 8000:8000 --env-file .env halfhell
```

`halfhell/Dockerfile` includes `ffmpeg` + `libgl` for opencv.

## Pipeline package

`halfhell/halfheaven` is the pipeline (was `halfheaven/packages/pipeline/halfheaven`, now removed from frontend). Python backend directory `packages/` has been removed from `halfheaven` — frontend is pure Next.js, backend owns the pipeline.

## ENV reference

| Var | Where | Default | Notes |
|---|---|---|---|
| `HALFHELL_API_URL` | frontend | `http://localhost:8000` | backend URL (build-time for Next.js) |
| `HALFHELL_API_KEY` | both | — | shared secret (hex 32) |
| `HALFHELL_API_KEYS` | backend | — | comma list for rotation |
| `GROQ_API_KEY` | backend | — | required for transcribe/chat |
| `GROQ_MODEL_ASR` etc | backend | pinned defaults | halfhell verifies at boot |
| `HALFHELL_ENV` | backend | `production` | `development` exposes docs |
| `HALFHELL_CORS_ORIGINS` | backend | `http://localhost:3000` | allow-list |
| `HALFHELL_WORK_ROOT` | backend | `./.halfhell-work` | per-job dirs |
| `HALFHELL_MAX_UPLOAD_MB` | backend | `500` | guard |
| `HALFHELL_RATE_LIMIT` | backend | `60/minute` | `500/hour` etc |

## Troubleshooting

- `401 Invalid API key` → frontend `HALFHELL_API_KEY` ≠ backend `HALFHELL_API_KEY`. Check both `.env.local` files.
- `requests.exceptions.HTTPError: 401 Unauthorized for url: https://api.groq.com/openai/v1/models` → `GROQ_API_KEY` invalid/expired on **backend only** (`halfhell/.env`). Generate new at `console.groq.com/keys` (`gsk_...`), set `GROQ_API_KEY=gsk_...` in `halfhell/.env`, restart `uvicorn app.main:app`. Frontend does not need `GROQ_API_KEY`. Test: `curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models | head`.
- `500` on fingerprint/jobs → check `GROQ_API_KEY` set on backend, `ffmpeg`/`ffprobe` on PATH, `opencv` installed.
- `413 File too large` → raise `HALFHELL_MAX_UPLOAD_MB` on backend.
- Frontend build `halfhell` type errors → run `npm run build` in `halfheaven` to surface.

## Setup both (copy-paste)

```bash
# 1. keys
openssl rand -hex 32  # -> HALFHELL_API_KEY
# get GROQ key: https://console.groq.com/keys -> gsk_...

# 2. backend
cd /run/media/se00n00/P/halfhell
cp .env.example .env  # fill HALFHELL_API_KEY + GROQ_API_KEY=gsk_...
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
# verify: curl http://localhost:8000/health
#         curl -H "X-API-Key: $HALFHELL_API_KEY" http://localhost:8000/v1/styles

# 3. frontend (new terminal)
cd /run/media/se00n00/P/halfheaven
cp .env.example .env.local  # fill HALFHELL_API_URL=http://localhost:8000 + same HALFHELL_API_KEY
npm install
npm run dev  # http://localhost:3000
```

