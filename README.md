# ScriptToStock — FromScriptToStock branch

AI-powered stock image/video finder for CapCut creators. Paste a script, get a ZIP of perfectly-timed B-rolls from Pexels (selected by Claude) ready to drop onto your CapCut timeline.

This branch (`FromScriptToStock`) is the **serverless-compatible** refactor:
- Fully synchronous (no threads, no in-memory job store, no temp files)
- Single `/api/generate` endpoint returns the ZIP inline
- Stats surfaced via HTTP response headers (`X-Cost-USD`, `X-Scenes`, `X-Videos`, `X-Images`, `X-Duration`)
- Works locally with `python script_to_stock.py`, and ships with configs for Vercel + Netlify

## ⚠️ Timeout reality check

The pipeline (Claude parse → N × Pexels downloads → ZIP) takes **1–4 minutes** on a real script. Serverless platforms impose hard request timeouts:

| Host | Max sync timeout | Works for this app? |
|---|---|---|
| Netlify free | 10s | ❌ Almost always times out |
| Netlify paid | 26s | ❌ Times out on non-trivial scripts |
| Vercel Hobby | 10s (60s with config) | ⚠ Only short scripts |
| **Vercel Pro** | **60s–300s** | ✅ **Works for most scripts** |
| Render / Railway / Fly.io | 30 min+ | ✅ ✅ Ideal — runs like a normal server |

If you want a host that "won't be taken down" AND reliably handles long runs, **Render** or **Railway** are the sweet spot. Vercel Pro is fine too but capped at 300s on Fluid Compute.

## Local development

```bash
pip install -r requirements.txt
python script_to_stock.py
# → http://localhost:8080
```

## Deploy to Vercel

Vercel ships Python Flask apps cleanly via `@vercel/python`. The `vercel.json` routes all traffic to `api/index.py`, which re-exports the Flask `app`.

```bash
npm i -g vercel
vercel login
vercel                       # first time — creates the project, asks a few Qs
vercel --prod                # promote the current preview to production
```

Relevant files:
- `vercel.json` — sets `maxDuration: 60`, routes `/*` → `/api/index`
- `api/index.py` — imports the Flask app so Vercel can auto-detect WSGI
- `requirements.txt` — picked up automatically at the repo root

If your Vercel account is on the free (Hobby) plan, change `maxDuration` in `vercel.json` down to `10` (Vercel will reject `60` on Hobby).

## Deploy to Netlify

Netlify's Python function runtime wraps Flask via `serverless-wsgi`. **This deploy will work for the home page and the API-key test endpoints, but `/api/generate` will almost certainly time out** — Netlify caps synchronous functions at 10s (free) / 26s (paid). Included mostly so you can compare.

```bash
npm i -g netlify-cli
netlify login
netlify init                 # link / create site
netlify deploy --build       # draft deploy
netlify deploy --prod --build
```

Relevant files:
- `netlify.toml` — routes `/*` to `/.netlify/functions/app/`, sets functions dir
- `netlify/functions/app.py` — Lambda handler using `serverless-wsgi`
- `netlify/functions/requirements.txt` — function-local Python deps
- `netlify/functions/script_to_stock.py` — copy of the main module (Netlify bundles each function directory in isolation)
- `public/index.html` — placeholder so Netlify has a `publish` dir

To keep the function's copy of `script_to_stock.py` in sync with the root version, re-run:
```bash
cp script_to_stock.py netlify/functions/script_to_stock.py
```

## Deploy to Render (recommended for long runs)

Not configured in this branch, but trivial: create a new Web Service, connect the repo, set:
- Build: `pip install -r requirements.txt`
- Start: `python script_to_stock.py`
- Env: nothing required (API keys are entered in the UI by the end user)

Render's free tier spins down after inactivity but has no per-request timeout.

## API

### `POST /api/test-claude`
Body: `{ "claude_key": "sk-ant-..." }` → `{ "ok": true }` or `{ "ok": false, "error": "..." }`

### `POST /api/test-pexels`
Body: `{ "pexels_key": "..." }` → same shape as above.

### `POST /api/generate`
Body:
```json
{
  "title": "My Video",
  "script": "full voiceover script text...",
  "claude_key": "sk-ant-...",
  "pexels_key": "...",
  "audio_duration": 185.3
}
```
Response on success: `200` with `Content-Type: application/zip`, `Content-Disposition: attachment; filename="..."`, and stats in headers:
- `X-Cost-USD` — Claude API cost for this run
- `X-Scenes` — number of B-rolls placed
- `X-Videos` / `X-Images` — breakdown
- `X-Duration` — total video duration in seconds

Response on failure: JSON `{ "error": "..." }` with 400/401/500.

## Project layout

```
FromScriptToStock/
├── script_to_stock.py           # Flask app (refactored, synchronous)
├── requirements.txt
├── README.md
├── .gitignore
├── vercel.json                  # Vercel config
├── api/
│   └── index.py                 # Vercel Python entrypoint
├── netlify.toml                 # Netlify config
├── netlify/
│   └── functions/
│       ├── app.py               # Netlify Lambda handler
│       ├── requirements.txt     # Function-local deps
│       └── script_to_stock.py   # Copy of main module for bundling
└── public/
    └── index.html               # Netlify publish dir placeholder
```
