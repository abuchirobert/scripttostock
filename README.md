# ScriptToStock

AI-powered stock B-roll finder for CapCut creators. Paste a script, get a ZIP of perfectly-timed 1080p B-rolls from Pexels (selected by Claude), ready for your CapCut timeline.

**Private, invite-only:** users are created by the admin and prepay for credit. API keys are owned by the admin — users never see or enter keys.

## Architecture

- `script_to_stock.py` — Flask app: auth, user app, generation planning, admin API
- `pages.py` — login + admin dashboard HTML
- `db.py` — MongoDB layer (users, credits, usage log, settings)
- `api/index.py` — Vercel entrypoint

**Serverless-friendly by design:** the server only runs the Claude script parse + Pexels *searches* (~15–30s, small JSON). The user's browser downloads media directly from the Pexels CDN and builds the ZIP client-side (JSZip) — no timeouts, no heavy bandwidth through the server. A `/api/proxy-media` fallback (pexels.com-only) covers rare CORS failures.

## Billing

Each generation charges the user: `actual Claude API cost × markup` (markup set in admin dashboard, default 5×). When balance hits $0 the tool stops working for them. Balance and usage history show on the user's dashboard.

## Setup

1. Create a free MongoDB Atlas cluster → get the connection string
2. Set env vars on Vercel (see `.env.example`): `MONGODB_URI`, `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`
3. Deploy: `vercel --prod`
4. Log in at `/login` with admin credentials → set Claude + Pexels API keys in the dashboard → create users with initial credit ($5 minimum by policy)

## Local development

```bash
pip install -r requirements.txt
export MONGODB_URI=... SECRET_KEY=... ADMIN_PASSWORD=...
python script_to_stock.py   # → http://localhost:8080
```
