---
name: deploy
description: Deploy frontend (Vercel) and/or backend (Koyeb) to production with pre-deploy quality gates
argument-hint: [frontend|backend|both]
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, WebFetch
---

# Deploy to Production

Deploy FloodSafe services with pre-deploy verification gates.

## Pre-Deploy Quality Gates (ALL must pass)

Run these checks sequentially. If any fail, STOP and report the failure:

1. **TypeScript type check:**
   ```bash
   cd apps/frontend && npx tsc --noEmit
   ```

2. **Frontend build:**
   ```bash
   cd apps/frontend && npm run build
   ```

3. **Frontend lint:**
   ```bash
   cd apps/frontend && npm run lint
   ```

4. **Backend tests (quick):**
   ```bash
   cd apps/backend && python -m pytest -m "not db_required" -q
   ```

If any gate fails, report the error and do NOT proceed to deployment.

## Deployment

Check `$ARGUMENTS` for target. If not specified, ask the user: frontend, backend, or both?

### Frontend (Vercel)
```bash
cd apps/frontend && npx vercel --prod
```

### Backend (Koyeb)
```bash
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

## Post-Deploy Verification

After deployment completes, run health checks:

1. **Frontend:** Fetch `https://frontend-lime-psi-83.vercel.app` and verify it loads
2. **Backend:** `curl https://floodsafe-backend-floodsafe-dda84554.koyeb.app/health` — expect `{"status": "healthy"}`

Report results with:
- ✅/❌ for each gate
- ✅/❌ for each deployment
- ✅/❌ for each health check
- Production URLs for quick access
