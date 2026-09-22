# Deploying PolicyGuard AI — Public URL (Render + Vercel)

This guide gets you a public link that works on **any laptop or mobile**, from anywhere,
using the free tiers of Render (backend) and Vercel (frontend).

## Architecture

```
Any device → Vercel (Next.js frontend) → Render (FastAPI backend, Docker) → /tmp disk storage
```

- Backend: FastAPI on Render (Docker runtime) → `https://<name>.onrender.com`
  - **The Docker runtime is used deliberately**: the backend image installs
    **Tesseract OCR** (see `backend/Dockerfile`), which guarantees scanned-PDF OCR
    works in production. Render's native "Python" runtime does **not** include
    Tesseract, so do not switch runtimes.
- Frontend: Next.js on Vercel free tier → `https://<name>.vercel.app`

---

## Prerequisites

1. Your project must be on **GitHub** (Render and Vercel deploy from a Git repo).
2. Free accounts:
   - https://dashboard.render.com (sign up with GitHub)
   - https://vercel.com (sign up with GitHub)

---

## Step 1 — Deploy the backend to Render (Docker runtime)

1. Go to https://dashboard.render.com → **New +** → **Blueprint**.
2. Select your GitHub repo. Render reads the `render.yaml` in the project root automatically.
   The blueprint uses the **Docker** runtime with `backend/Dockerfile`, so Tesseract
   OCR is installed into the production image automatically.
3. Click **Apply** / **Create Services**. Wait ~5–10 minutes for the first build
   (it builds the Docker image, installs Python packages and Tesseract OCR).
4. When it shows **Live**, note your backend URL, e.g.
   `https://policyguard-backend-xxxx.onrender.com`
5. Test it in a browser: open `https://<your-backend-url>/api/v1/health` — you should
   see a JSON response. Check the `ocr` field reports `available: true`
   (Tesseract found in the container).

### Required environment variables (set in the Render dashboard)

With `APP_ENV=production` the backend **refuses to start** unless these are set:

| Variable | Example | Purpose |
|---|---|---|
| `POLICYGUARD_AUTH_SECRET` | 64-hex chars (`python -c "import secrets; print(secrets.token_hex(32))"`) | Signs officer session tokens. Never commit it. |
| `POLICYGUARD_DEMO_PASSWORD` | strong password | Password for the seeded `officer-001` demo account. |
| `POLICYGUARD_CORS_ORIGINS` | `https://your-frontend.vercel.app` | Comma-separated browser origins allowed by CORS. `*` is refused in production. |
| `APP_ENV` | `production` | Enables the strict production checks above. |
| `STORAGE_PATH` | `/tmp/storage` | JSON file store for uploads, analyses and the audit chain. |

All variables are documented in `.env.example`.

> **Note:** Render's free tier sleeps after ~15 minutes of inactivity. The first request
> after a nap takes ~30–60 seconds to wake up. Keep the tab open or use a ping service
> (e.g. https://cron-job.org) hitting `/api/v1/health` every 10 minutes to keep it awake.

---

## Step 2 — Deploy the frontend to Vercel

1. Go to https://vercel.com/new and import your GitHub repo.
2. Configure the project:
   - **Framework Preset:** Next.js (auto-detected)
   - **Root Directory:** `frontend`
   - **Environment Variables** — add:
     - `BACKEND_API_URL` = `https://<your-backend-url>.onrender.com`
       (use the exact URL from Step 1, **without** a trailing slash and **without** `/api/v1`)
3. Click **Deploy**. Wait ~2–3 minutes.
4. You'll get a public URL like `https://policyguard-frontend.vercel.app`.

The frontend proxies all `/api/v1/*` requests to the backend via `BACKEND_API_URL`
(see `frontend/next.config.js`), so no CORS problems in the browser.

---

## Step 3 — Open it on any device

Share your Vercel URL. On any laptop or phone browser:

```
https://<your-project>.vercel.app
```

Log in on the Login page as `officer-001` with the `POLICYGUARD_DEMO_PASSWORD`
you configured. All protected actions (upload, analysis, decisions, report download)
require this login; the health endpoint stays public.

That's it — no installation needed on the other devices.

---

## Updating the app

Every `git push` to GitHub automatically redeploys both services.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Backend fails to start on Render | Missing required env vars. Set `POLICYGUARD_AUTH_SECRET`, `POLICYGUARD_DEMO_PASSWORD` and `POLICYGUARD_CORS_ORIGINS` (see table above). |
| CORS errors in the browser | `POLICYGUARD_CORS_ORIGINS` on Render must include your exact Vercel origin (scheme + host, no trailing slash). |
| Frontend loads but shows API errors | Check `BACKEND_API_URL` on Vercel exactly matches the Render URL (no trailing slash, no `/api/v1`). |
| Backend asleep / very slow first load | Free tier sleeps after 15 min idle; ping `/api/v1/health` or upgrade plan. |
| Upload/OCR fails after working before | Free tier has an ephemeral `/tmp` disk — files don't persist across restarts. |
| OCR reports unavailable | Confirm the service uses the **Docker** runtime (not "Python 3"); only the Docker image installs Tesseract. |
| Download Report fails | You must be logged in as an officer; the download endpoint requires authentication. |
| Build fails on Render | Check the build logs; the Dockerfile pins Python 3.12. |
