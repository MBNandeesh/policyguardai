# Deploying PolicyGuard AI — Public URL (Render + Vercel)

This guide gets you a public link that works on **any laptop or mobile**, from anywhere,
using the free tiers of Render (backend) and Vercel (frontend).

## Architecture

```
Any device → Vercel (Next.js frontend) → Render (FastAPI backend) → /tmp disk storage
```

- Backend: FastAPI on Render free tier → `https://<name>.onrender.com`
- Frontend: Next.js on Vercel free tier → `https://<name>.vercel.app`

---

## Prerequisites

1. Your project must be on **GitHub** (Render and Vercel deploy from a Git repo).
   - If it isn't pushed yet, create a repo at https://github.com/new and push this project.
2. Free accounts:
   - https://dashboard.render.com (sign up with GitHub)
   - https://vercel.com (sign up with GitHub)

---

## Step 1 — Deploy the backend to Render

1. Go to https://dashboard.render.com → **New +** → **Blueprint**.
2. Select your GitHub repo. Render reads the `render.yaml` in the project root automatically.
3. Click **Apply** / **Create Services**. Wait ~5–10 minutes for the first build
   (it installs Python packages and Tesseract OCR).
4. When it shows **Live**, note your backend URL, e.g.
   `https://policyguard-backend-xxxx.onrender.com`
5. Test it in a browser: open `https://<your-backend-url>/api/v1/health`
   — you should see a JSON response.

### Alternative: manual setup (if you prefer not to use the Blueprint)

- **New +** → **Web Service** → pick the repo
- Runtime: **Python 3**, Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables:
  - `PYTHON_VERSION` = `3.12`
  - `CORS_ORIGINS` = `*`
  - `STORAGE_PATH` = `/tmp/storage`
  - `APP_ENV` = `production`

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

That's it — no installation needed on the other devices.

---

## Optional — Restrict CORS later

By default the backend allows all origins (`CORS_ORIGINS=*`). Once you know your
frontend URL, tighten it in Render → your service → **Environment**:

```
CORS_ORIGINS=https://your-frontend.vercel.app
```

## Updating the app

Every `git push` to GitHub automatically redeploys both services.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend loads but shows API errors | Check `BACKEND_API_URL` on Vercel exactly matches the Render URL (no trailing slash, no `/api/v1`) |
| Backend asleep / very slow first load | Free tier sleeps after 15 min idle; ping `/api/v1/health` or upgrade plan |
| Upload/OCR fails after working before | Free tier has an ephemeral `/tmp` disk — files don't persist across restarts |
| Build fails on Render | Check the build logs; confirm `PYTHON_VERSION=3.12` |
