# Offline, Push, WhatsApp & SMS — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship 4 capabilities incrementally: WhatsApp report visibility fixes, FCM push notifications for saved routes, Capacitor Android wrapper, and offline SMS compose for SOS.

**Architecture:** Phase 0 fixes 6 lines of backend/frontend code to make WhatsApp reports fully visible. Phase 1 validates Capacitor native wrapper + FCM push delivery. Phase 2 builds route monitoring cron + SMS compose. Phase 3 polishes WhatsApp LINK discoverability. Each phase has a deploy gate.

**Tech Stack:** FastAPI (Python), React 18 + TypeScript, Firebase Admin SDK (push), Capacitor 6 (Android), PostGIS (spatial queries), Workbox (PWA).

**Design Doc:** `docs/plans/2026-02-22-offline-push-whatsapp-mesh-viability-design.md`

---

## Conventions

**Quality gates (run before EVERY deploy):**
```bash
cd apps/frontend && npx tsc --noEmit    # TypeScript
cd apps/frontend && npm run build        # Vite build
cd apps/backend && pytest                # Backend tests
```

**Deployment (git push does NOT auto-deploy):**
```bash
# Frontend
cd apps/frontend && npx vercel --prod

# Backend
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
# Wait 30-60s for cold start, then verify:
curl https://floodsafe-backend-floodsafe-dda84554.koyeb.app/health
```

**Sensitive files (READ before modifying):**
- `apps/backend/src/infrastructure/models.py`
- `apps/backend/src/core/config.py`
- `apps/frontend/src/lib/firebase.ts`
- `apps/frontend/src/contexts/AuthContext.tsx`

**Production URLs:**
- Frontend: `https://frontend-lime-psi-83.vercel.app`
- Backend: `https://floodsafe-backend-floodsafe-dda84554.koyeb.app`
- Dev port: **5175** (NOT 5173)

---

## Phase 0: WhatsApp Report Visibility Fixes

> **Why first:** 6 lines of code, 30 minutes, immediate user-visible improvement. WhatsApp reports already exist in the DB but photos are invisible and ML classification is stripped.

---

### Task 1: Fix `media_url` on Twilio webhook reports

**Files:**
- Modify: `apps/backend/src/api/webhook.py:284` (inside `create_sos_report`, line 226-291)

**Context:** `create_sos_report()` receives `media_url` as a parameter (line 232) and stores it inside `media_metadata` JSON (line 275), but never passes it to the `Report()` constructor as a column value. Frontend expects `Report.media_url` for photo rendering.

**Step 1: Write the failing test**

Create test in `apps/backend/tests/test_whatsapp/test_report_creation.py`:

```python
"""Tests for WhatsApp report creation — media_url and media_metadata."""
import pytest
from unittest.mock import MagicMock, patch
from src.api.webhook import create_sos_report


class TestCreateSosReport:
    """Test create_sos_report correctly populates Report fields."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        return db

    @pytest.fixture
    def mock_classification(self):
        """Mock ML flood classification result."""
        cls = MagicMock()
        cls.is_flood = True
        cls.confidence = 0.87
        cls.classification = "flood"
        cls.needs_review = False
        return cls

    def test_report_has_media_url_when_photo_provided(self, mock_db, mock_classification):
        """media_url column should be set when a photo URL is provided."""
        report = create_sos_report(
            db=mock_db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            media_url="https://api.twilio.com/media/test.jpg",
            classification=mock_classification,
        )
        assert report.media_url == "https://api.twilio.com/media/test.jpg"

    def test_report_media_url_none_when_no_photo(self, mock_db):
        """media_url should be None when no photo is provided."""
        report = create_sos_report(
            db=mock_db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
        )
        assert report.media_url is None

    def test_report_has_media_metadata_with_classification(self, mock_db, mock_classification):
        """media_metadata should contain ML classification when available."""
        report = create_sos_report(
            db=mock_db,
            latitude=28.6139,
            longitude=77.2090,
            phone="+919876543210",
            media_url="https://api.twilio.com/media/test.jpg",
            classification=mock_classification,
        )
        assert report.media_metadata is not None
        assert report.media_metadata["ml_classification"] == "flood"
        assert report.media_metadata["ml_confidence"] == 0.87
```

**Step 2: Run test to verify it fails**

```bash
cd apps/backend && pytest tests/test_whatsapp/test_report_creation.py -v
```
Expected: `test_report_has_media_url_when_photo_provided` FAILS — `report.media_url` is `None` because the parameter is missing from Report() constructor.

**Step 3: Apply the fix**

In `apps/backend/src/api/webhook.py`, inside `create_sos_report()`, add `media_url=media_url` to the Report constructor (after line 284):

```python
# Line 277-286, BEFORE:
    report = Report(
        location=f"POINT({longitude} {latitude})",
        description=description,
        verified=verified,
        location_verified=True,
        water_depth="impassable" if (classification and classification.is_flood) else "unknown",
        user_id=user.id if user else None,
        phone_number=phone,
        media_metadata=media_metadata
    )

# AFTER — add media_url on line 285:
    report = Report(
        location=f"POINT({longitude} {latitude})",
        description=description,
        verified=verified,
        location_verified=True,
        water_depth="impassable" if (classification and classification.is_flood) else "unknown",
        user_id=user.id if user else None,
        phone_number=phone,
        media_url=media_url,
        media_metadata=media_metadata
    )
```

**Step 4: Run test to verify it passes**

```bash
cd apps/backend && pytest tests/test_whatsapp/test_report_creation.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add apps/backend/src/api/webhook.py apps/backend/tests/test_whatsapp/test_report_creation.py
git commit -m "fix: set media_url on WhatsApp reports (Twilio path)"
```

---

### Task 2: Fix Meta webhook — add `media_metadata` to Report

**Files:**
- Modify: `apps/backend/src/api/whatsapp_meta.py:510-516` (inside `_create_report_with_photo`, line 475-570)

**Context:** Meta webhook receives photo as raw bytes (not a URL), runs ML classification, but discards the classification result — it's never stored on the Report. Unlike Twilio, there's no persistent `media_url` (Meta download URLs are temporary). The fix is to build `media_metadata` from classification results, matching the Twilio pattern.

**Step 1: Write the failing test**

Add to `apps/backend/tests/test_whatsapp/test_report_creation.py`:

```python
class TestMetaReportCreation:
    """Test Meta WhatsApp report creation stores classification."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        return db

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.data = {"pending_lat": 28.6139, "pending_lng": 77.2090}
        session.state = "awaiting_photo"
        return session

    @patch("src.api.whatsapp_meta.meta_send_buttons", new_callable=AsyncMock)
    @patch("src.api.whatsapp_meta.get_readable_location", return_value="Test Location")
    @patch("src.api.whatsapp_meta.classify_flood_image")
    async def test_meta_report_has_media_metadata(
        self, mock_classify, mock_location, mock_send, mock_db, mock_session
    ):
        """Meta reports should store ML classification in media_metadata."""
        mock_cls = MagicMock()
        mock_cls.is_flood = True
        mock_cls.confidence = 0.92
        mock_cls.classification = "flood"
        mock_cls.needs_review = False
        mock_classify.return_value = mock_cls

        from src.api.whatsapp_meta import _create_report_with_photo
        await _create_report_with_photo(
            mock_db, mock_session, "+919876543210", None,
            28.6139, 77.2090, b"fake_photo_bytes", "en"
        )

        # The Report() was created via db.add — check the first call's argument
        report = mock_db.add.call_args[0][0]
        assert report.media_metadata is not None
        assert report.media_metadata["ml_classification"] == "flood"
```

**Step 2: Run test to verify it fails**

```bash
cd apps/backend && pytest tests/test_whatsapp/test_report_creation.py::TestMetaReportCreation -v
```
Expected: FAIL — `report.media_metadata` is None.

**Step 3: Apply the fix**

In `apps/backend/src/api/whatsapp_meta.py`, inside `_create_report_with_photo()`, build `media_metadata` from classification and pass it to Report():

```python
# Line 509-516, BEFORE:
    report = Report(
        location=f"POINT({longitude} {latitude})",
        description=description,
        verified=verified,
        location_verified=True,
        water_depth="impassable" if (classification and classification.is_flood) else "unknown",
        user_id=user.id if user else None,
        phone_number=phone,
    )

# AFTER — build media_metadata and add it:
    # Build media metadata from classification (same pattern as Twilio webhook)
    media_metadata = None
    if classification:
        media_metadata = {
            "ml_classification": classification.classification,
            "ml_confidence": classification.confidence,
            "is_flood": classification.is_flood,
            "needs_review": classification.needs_review,
        }

    report = Report(
        location=f"POINT({longitude} {latitude})",
        description=description,
        verified=verified,
        location_verified=True,
        water_depth="impassable" if (classification and classification.is_flood) else "unknown",
        user_id=user.id if user else None,
        phone_number=phone,
        media_metadata=media_metadata,
    )
```

> **Note:** No `media_url` fix here — Meta provides raw bytes, not a persistent URL. To display Meta photos in-app, a future task should upload `photo_bytes` to Supabase Storage and store that URL as `media_url`. For now, `media_metadata` captures the ML results.

**Step 4: Run tests**

```bash
cd apps/backend && pytest tests/test_whatsapp/test_report_creation.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add apps/backend/src/api/whatsapp_meta.py apps/backend/tests/test_whatsapp/test_report_creation.py
git commit -m "fix: store ML classification in media_metadata for Meta WhatsApp reports"
```

---

### Task 3: Add ML fields to frontend validator

**Files:**
- Modify: `apps/frontend/src/lib/api/validators.ts:153-172` (inside `validateReport`)

**Context:** `validateReport()` (line 141-173) returns 14 optional fields but silently drops 4 ML fields (`ml_classification`, `ml_confidence`, `ml_is_flood`, `ml_needs_review`) that the backend sends and the `Report` interface (hooks.ts:44-47) already declares. This means ML classification badges never render for ANY report.

**Step 1: Understand the pattern**

The validator uses this pattern for optional fields:
```typescript
water_depth: isString(data.water_depth) ? data.water_depth : undefined,
```

ML fields follow the same pattern. The types are defined in `hooks.ts:44-47`:
```typescript
ml_classification?: string;
ml_confidence?: number;
ml_is_flood?: boolean;
ml_needs_review?: boolean;
```

**Step 2: Apply the fix**

In `apps/frontend/src/lib/api/validators.ts`, add 4 lines to the return object of `validateReport()`, after the `user_vote` line (line 171):

```typescript
// Line 171, BEFORE (last line of return object):
        user_vote: data.user_vote === 'upvote' || data.user_vote === 'downvote' ? data.user_vote : undefined,
    };

// AFTER — add ML fields before the closing brace:
        user_vote: data.user_vote === 'upvote' || data.user_vote === 'downvote' ? data.user_vote : undefined,
        ml_classification: isString(data.ml_classification) ? data.ml_classification : undefined,
        ml_confidence: isNumber(data.ml_confidence) ? data.ml_confidence : undefined,
        ml_is_flood: isBoolean(data.ml_is_flood) ? data.ml_is_flood : undefined,
        ml_needs_review: isBoolean(data.ml_needs_review) ? data.ml_needs_review : undefined,
    };
```

**Step 3: Verify types**

```bash
cd apps/frontend && npx tsc --noEmit
```
Expected: PASS (fields already declared in Report interface).

**Step 4: Commit**

```bash
git add apps/frontend/src/lib/api/validators.ts
git commit -m "fix: include ML classification fields in report validator"
```

---

### Task 4: Quality gates + deploy + verify Phase 0

**Step 1: Run all quality gates**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
cd apps/backend && pytest
```
Expected: All pass.

**Step 2: Deploy both platforms**

```bash
# Frontend (validator fix)
cd apps/frontend && npx vercel --prod

# Backend (webhook fixes)
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

**Step 3: Verify Koyeb is up**

```bash
# Wait 30-60s for cold start
curl https://floodsafe-backend-floodsafe-dda84554.koyeb.app/health
```
Expected: 200 OK with status info.

**Step 4: E2E verification (manual)**

Use Twilio sandbox or Meta webhook to send a photo + location via WhatsApp:
1. Open `https://frontend-lime-psi-83.vercel.app`
2. Go to Community Feed tab
3. Verify WhatsApp report appears within 30 seconds
4. Verify photo renders (if Twilio path — media_url now set)
5. Verify ML classification badge visible (if ML ran successfully)

**Step 5: Commit deploy verification**

```bash
git add -A && git commit -m "chore: Phase 0 complete — WhatsApp report visibility fixes deployed"
```

---

## Phase 1A: Capacitor Android PoC

> **Why:** Validates the native wrapper before building push notifications on top of it. This is a go/no-go gate — if Capacitor fails, we pivot to PWA-only push.

---

### Task 5: Initialize Capacitor in frontend project

**Files:**
- Modify: `apps/frontend/package.json` (new dependencies)
- Create: `apps/frontend/capacitor.config.ts`
- Create: `apps/frontend/android/` (auto-generated)

**Step 1: Install Capacitor**

```bash
cd apps/frontend
npm install @capacitor/core @capacitor/cli
```

**Step 2: Initialize Capacitor**

```bash
cd apps/frontend
npx cap init FloodSafe com.floodsafe.app --web-dir dist
```

This creates `capacitor.config.ts`. Edit it to:

```typescript
import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.floodsafe.app',
  appName: 'FloodSafe',
  webDir: 'dist',
  server: {
    androidScheme: 'http',  // Capacitor 6+ defaults to https; keep http for WebView compat
  },
};

export default config;
```

**Step 3: Add Android platform**

```bash
cd apps/frontend
npx cap add android
```

This creates the `android/` directory. Add `android/` to `.gitignore` (it's generated, large, and platform-specific):

```bash
echo "apps/frontend/android/" >> .gitignore
```

**Step 4: Verify build + sync**

```bash
cd apps/frontend && npm run build && npx cap sync
```
Expected: Vite build succeeds, Capacitor copies `dist/` into Android project.

**Step 5: Commit**

```bash
git add apps/frontend/capacitor.config.ts apps/frontend/package.json apps/frontend/package-lock.json .gitignore
git commit -m "feat: initialize Capacitor for Android wrapper"
```

---

### Task 6: Add CORS origin for Capacitor WebView

**Files:**
- Modify: `apps/backend/src/core/config.py:19-23` (CORS origins list)

**Context:** Capacitor Android WebView uses origin `http://localhost` (no port). This is different from `http://localhost:5175` and will fail CORS without this change. READ config.py first.

**Step 1: Add origin to defaults**

In `apps/backend/src/core/config.py`, line 19-23:

```python
# BEFORE:
BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = [
    "http://localhost:5175",
    "http://localhost:8000",
    "https://frontend-lime-psi-83.vercel.app",
]

# AFTER:
BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = [
    "http://localhost:5175",
    "http://localhost:8000",
    "http://localhost",
    "https://frontend-lime-psi-83.vercel.app",
]
```

**Step 2: Update Koyeb env var**

The production Koyeb backend also needs this origin. Update via Koyeb dashboard or CLI — add `http://localhost` to the `BACKEND_CORS_ORIGINS` comma-separated env var.

**Step 3: Run backend tests**

```bash
cd apps/backend && pytest
```
Expected: PASS

**Step 4: Deploy backend**

```bash
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

**Step 5: Commit**

```bash
git add apps/backend/src/core/config.py
git commit -m "feat: add Capacitor WebView CORS origin (http://localhost)"
```

---

### Task 7: Build and run on Android emulator

**Prerequisites:** Android Studio + SDK installed (1-2 hours if first time).

**Step 1: Open in Android Studio**

```bash
cd apps/frontend && npx cap open android
```

**Step 2: Run on emulator**

- Select API 30+ emulator (Android 11+)
- Click Run
- Wait for Gradle build (slow first time, 5-10 min)

**Step 3: Verify checklist**

- [ ] App loads without white screen
- [ ] MapLibre renders (WebGL works in WebView)
- [ ] Map is interactive (pan, zoom, tap markers)
- [ ] API calls succeed (check Chrome DevTools > WebView for CORS errors)
- [ ] Email login works (doesn't use popup)
- [ ] Google login — EXPECT FAILURE (document the error for later fix)
- [ ] Service worker registers (`chrome://inspect` > WebView)
- [ ] Airplane mode: offline indicator shows
- [ ] SOS queues to IndexedDB when offline

**Kill criteria:**
- MapLibre doesn't render → STOP (native map SDK = project rewrite)
- Service worker doesn't register → STOP (core offline features break)
- Gradle build fails → likely fixable (path/asset config)

**Step 4: Document results**

Create `docs/plans/capacitor-poc-results.md` with pass/fail for each item.

**Step 5: Commit**

```bash
git add docs/plans/capacitor-poc-results.md
git commit -m "docs: Capacitor Android PoC results"
```

---

## Phase 1B: FCM Push Notifications PoC

> **Why:** FCM is free and unlimited. This validates end-to-end push delivery before building route monitoring on top of it.

---

### Task 8: Create Firebase service account + Koyeb env var

**Step 1: Generate service account key**

1. Firebase Console → Project Settings → Service Accounts
2. Click "Generate new private key" → downloads JSON file
3. **NEVER commit this file**

**Step 2: Base64-encode and add to Koyeb**

```bash
# Encode the JSON file
cat firebase-service-account.json | base64 -w 0 > firebase-b64.txt

# Add to Koyeb as env var FIREBASE_SERVICE_ACCOUNT_B64
# Via Koyeb dashboard: Service > Settings > Environment Variables
# OR via CLI
```

**Step 3: Generate VAPID key for web push**

1. Firebase Console → Project Settings → Cloud Messaging → Web Push certificates
2. Click "Generate key pair"
3. Copy the public key
4. Add to frontend `.env` as `VITE_FIREBASE_VAPID_KEY=<key>`
5. Add to Vercel environment variables too

**Step 4: Delete the local service account JSON (security)**

```bash
rm firebase-service-account.json firebase-b64.txt
```

No commit needed — this is infrastructure setup only.

---

### Task 9: Backend push notification service

**Files:**
- Create: `apps/backend/src/domain/services/push_notification_service.py`
- Modify: `apps/backend/requirements.txt` (add `firebase-admin`)
- Modify: `apps/backend/src/infrastructure/models.py` (add `fcm_token` to User)

**READ `models.py` FIRST before modifying.**

**Step 1: Add firebase-admin dependency**

Add to `apps/backend/requirements.txt`:
```
# Push Notifications (FCM)
firebase-admin>=6.0.0
```

Install: `pip install firebase-admin`

**Step 2: Add `fcm_token` column to User model**

In `apps/backend/src/infrastructure/models.py`, add to User class:

```python
# After existing User fields (around line 50):
fcm_token = Column(String, nullable=True)  # Firebase Cloud Messaging device token
fcm_token_updated_at = Column(DateTime, nullable=True)
```

**Step 3: Create migration script**

Create `apps/backend/scripts/migrate_add_fcm_token.py`:

```python
"""Add fcm_token column to users table."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from src.core.config import settings

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token_updated_at TIMESTAMP;
    """))
    conn.commit()
    print("Migration complete: added fcm_token columns to users")
```

**Step 4: Create push notification service**

Create `apps/backend/src/domain/services/push_notification_service.py`:

```python
"""FCM Push Notification Service.

Sends push notifications via Firebase Cloud Messaging.
Handles both web (VAPID) and native (Capacitor) tokens.
"""
import os
import json
import base64
import logging
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK (once at module load)
_firebase_app = None


def _get_firebase_app():
    """Lazy-init Firebase Admin SDK from base64-encoded service account."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    b64_creds = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64")
    if not b64_creds:
        logger.warning("FIREBASE_SERVICE_ACCOUNT_B64 not set — push notifications disabled")
        return None

    try:
        creds_dict = json.loads(base64.b64decode(b64_creds))
        cred = credentials.Certificate(creds_dict)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized for push notifications")
        return _firebase_app
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return None


async def send_push_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
    click_url: Optional[str] = None,
) -> bool:
    """Send a push notification to a single device.

    Args:
        fcm_token: FCM device registration token
        title: Notification title
        body: Notification body text
        data: Optional data payload (key-value strings)
        click_url: Optional URL to open on notification click

    Returns:
        True if sent successfully, False otherwise
    """
    app = _get_firebase_app()
    if app is None:
        logger.warning("Firebase not initialized — skipping push notification")
        return False

    try:
        notification = messaging.Notification(title=title, body=body)

        web_push = None
        if click_url:
            web_push = messaging.WebpushConfig(
                fcm_options=messaging.WebpushFCMOptions(link=click_url)
            )

        message = messaging.Message(
            notification=notification,
            data=data or {},
            token=fcm_token,
            webpush=web_push,
        )

        response = messaging.send(message)
        logger.info(f"Push sent successfully: {response}")
        return True

    except messaging.UnregisteredError:
        logger.warning(f"FCM token expired/unregistered: {fcm_token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return False
```

**Step 5: Run backend tests**

```bash
cd apps/backend && pytest
```
Expected: PASS (new service has no side effects on existing tests).

**Step 6: Commit**

```bash
git add apps/backend/src/domain/services/push_notification_service.py \
       apps/backend/requirements.txt \
       apps/backend/src/infrastructure/models.py \
       apps/backend/scripts/migrate_add_fcm_token.py
git commit -m "feat: add FCM push notification service + fcm_token on User model"
```

---

### Task 10: FCM token storage endpoint

**Files:**
- Create: `apps/backend/src/api/push.py`
- Modify: `apps/backend/src/main.py` (register router)

**Step 1: Create push router**

Create `apps/backend/src/api/push.py`:

```python
"""Push notification endpoints — FCM token registration."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..infrastructure.database import get_db
from ..api.auth import get_current_user
from ..infrastructure.models import User

router = APIRouter(prefix="/push", tags=["push"])


class FCMTokenRequest(BaseModel):
    token: str


@router.post("/register-token")
async def register_fcm_token(
    request: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store or update FCM device token for the authenticated user."""
    current_user.fcm_token = request.token
    current_user.fcm_token_updated_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "message": "FCM token registered"}


@router.delete("/register-token")
async def unregister_fcm_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove FCM token (e.g., on logout)."""
    current_user.fcm_token = None
    current_user.fcm_token_updated_at = None
    db.commit()
    return {"status": "ok", "message": "FCM token removed"}
```

**Step 2: Register router in main.py**

In `apps/backend/src/main.py`, add:
```python
from .api.push import router as push_router
app.include_router(push_router, prefix="/api")
```

**Step 3: Run tests**

```bash
cd apps/backend && pytest
```

**Step 4: Commit**

```bash
git add apps/backend/src/api/push.py apps/backend/src/main.py
git commit -m "feat: add POST /api/push/register-token endpoint for FCM"
```

---

### Task 11: Frontend messaging initialization

**Files:**
- Modify: `apps/frontend/src/lib/firebase.ts` (add messaging init)
- Create: `apps/frontend/src/hooks/usePushNotifications.ts`

**READ `firebase.ts` FIRST before modifying.**

**Step 1: Add messaging exports to firebase.ts**

Add to `apps/frontend/src/lib/firebase.ts`:

```typescript
import { getMessaging, getToken, onMessage, type Messaging } from 'firebase/messaging';

let messagingInstance: Messaging | null = null;

/**
 * Get Firebase Cloud Messaging instance.
 * Returns null if browser doesn't support notifications or firebase isn't initialized.
 */
export function getFirebaseMessaging(): Messaging | null {
    if (messagingInstance) return messagingInstance;

    const app = getFirebaseApp();
    if (!app) return null;

    // Check browser support
    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
        console.warn('Push notifications not supported in this browser');
        return null;
    }

    try {
        messagingInstance = getMessaging(app);
        return messagingInstance;
    } catch (error) {
        console.error('Failed to initialize Firebase Messaging:', error);
        return null;
    }
}

export { getToken, onMessage };
```

**Step 2: Create push notifications hook**

Create `apps/frontend/src/hooks/usePushNotifications.ts`:

```typescript
import { useCallback, useEffect, useState } from 'react';
import { Capacitor } from '@capacitor/core';
import { getFirebaseMessaging, getToken, onMessage } from '../lib/firebase';
import { fetchJson } from '../lib/api/client';

const VAPID_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY;

export function usePushNotifications() {
    const [permission, setPermission] = useState<NotificationPermission>(
        'Notification' in window ? Notification.permission : 'denied'
    );
    const [token, setToken] = useState<string | null>(null);

    const registerToken = useCallback(async (fcmToken: string) => {
        try {
            await fetchJson('/push/register-token', {
                method: 'POST',
                body: JSON.stringify({ token: fcmToken }),
            });
            setToken(fcmToken);
        } catch (error) {
            console.error('Failed to register FCM token:', error);
        }
    }, []);

    const requestPermission = useCallback(async () => {
        if (Capacitor.isNativePlatform()) {
            // Native path — use Capacitor push plugin (Task for Phase 1A)
            console.log('Native push: use @capacitor/push-notifications');
            return;
        }

        // Web path — Firebase Messaging
        const messaging = getFirebaseMessaging();
        if (!messaging) return;

        try {
            const perm = await Notification.requestPermission();
            setPermission(perm);

            if (perm === 'granted' && VAPID_KEY) {
                const fcmToken = await getToken(messaging, { vapidKey: VAPID_KEY });
                if (fcmToken) {
                    await registerToken(fcmToken);
                }
            }
        } catch (error) {
            console.error('Failed to get push permission:', error);
        }
    }, [registerToken]);

    // Listen for foreground messages
    useEffect(() => {
        if (Capacitor.isNativePlatform()) return;

        const messaging = getFirebaseMessaging();
        if (!messaging) return;

        const unsubscribe = onMessage(messaging, (payload) => {
            // Show in-app notification for foreground messages
            console.log('Foreground push received:', payload);
            if (payload.notification) {
                // Could show a toast/alert here
                new Notification(
                    payload.notification.title || 'FloodSafe Alert',
                    { body: payload.notification.body }
                );
            }
        });

        return () => unsubscribe();
    }, []);

    // Re-register token on every app open (Firebase recommendation)
    useEffect(() => {
        if (permission === 'granted' && VAPID_KEY && !Capacitor.isNativePlatform()) {
            const messaging = getFirebaseMessaging();
            if (messaging) {
                getToken(messaging, { vapidKey: VAPID_KEY })
                    .then((t) => { if (t) registerToken(t); })
                    .catch(console.error);
            }
        }
    }, [permission, registerToken]);

    return { permission, token, requestPermission };
}
```

**Step 3: Type check**

```bash
cd apps/frontend && npx tsc --noEmit
```

> **Note:** If `@capacitor/core` import fails type check, it's because Capacitor isn't installed yet (depends on Phase 1A completing first). Use conditional import or type stub if needed.

**Step 4: Commit**

```bash
git add apps/frontend/src/lib/firebase.ts apps/frontend/src/hooks/usePushNotifications.ts
git commit -m "feat: add FCM messaging init + usePushNotifications hook"
```

---

### Task 12: Firebase messaging service worker

**Files:**
- Create: `apps/frontend/public/firebase-messaging-sw.js`
- Modify: `apps/frontend/vite.config.ts` (exclude from Workbox)

**Step 1: Create messaging service worker**

Create `apps/frontend/public/firebase-messaging-sw.js`:

```javascript
/* Firebase Cloud Messaging background handler.
 * This runs in a separate SW scope from Workbox.
 * It handles push notifications when the app tab is closed/background. */
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');

firebase.initializeApp({
    apiKey: self.__FIREBASE_CONFIG__?.apiKey || '',
    authDomain: self.__FIREBASE_CONFIG__?.authDomain || '',
    projectId: self.__FIREBASE_CONFIG__?.projectId || '',
    storageBucket: self.__FIREBASE_CONFIG__?.storageBucket || '',
    messagingSenderId: self.__FIREBASE_CONFIG__?.messagingSenderId || '',
    appId: self.__FIREBASE_CONFIG__?.appId || '',
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
    const title = payload.notification?.title || 'FloodSafe Alert';
    const options = {
        body: payload.notification?.body || 'You have a new flood alert',
        icon: '/icons/icon-192x192.png',
        badge: '/icons/icon-72x72.png',
        data: payload.data || {},
        tag: 'floodsafe-alert',  // Replaces previous notification with same tag
    };

    self.registration.showNotification(title, options);
});

// Handle notification click — open the app
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const url = event.notification.data?.click_url || '/';
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Focus existing window if open
                for (const client of clientList) {
                    if (client.url.includes('floodsafe') && 'focus' in client) {
                        return client.focus();
                    }
                }
                // Otherwise open new window
                return self.clients.openWindow(url);
            })
    );
});
```

> **Note:** The `self.__FIREBASE_CONFIG__` values need to be injected at build time or hardcoded. For the PoC, hardcode the config values from `firebase.ts`. For production, use a build-time injection.

**Step 2: Exclude from Workbox precaching**

In `apps/frontend/vite.config.ts`, find the Workbox/PWA config and add `firebase-messaging-sw.js` to the exclusion list. Look for `workbox.navigateFallbackDenylist` or `globIgnores`:

```typescript
// In the VitePWA plugin config, add:
workbox: {
    // ... existing config ...
    globIgnores: [
        '**/firebase-messaging-sw.js',  // Handled by Firebase, not Workbox
        // ... existing ignores ...
    ],
}
```

**Step 3: Build and verify**

```bash
cd apps/frontend && npm run build
# Verify firebase-messaging-sw.js is in dist/
ls dist/firebase-messaging-sw.js
```

**Step 4: Commit**

```bash
git add apps/frontend/public/firebase-messaging-sw.js apps/frontend/vite.config.ts
git commit -m "feat: add Firebase messaging service worker for background push"
```

---

### Task 13: Deploy + E2E push test

**Step 1: Run quality gates**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build
cd apps/backend && pytest
```

**Step 2: Run database migration**

```bash
cd apps/backend && python scripts/migrate_add_fcm_token.py
```

**Step 3: Deploy both platforms**

```bash
cd apps/frontend && npx vercel --prod
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

**Step 4: E2E verification**

1. Open `https://frontend-lime-psi-83.vercel.app` in Chrome
2. Log in → should see notification permission prompt (or trigger via settings)
3. Grant permission → check Network tab for `POST /api/push/register-token`
4. Verify response is `{"status": "ok"}`
5. Send test push from backend Python shell:

```python
# SSH into Koyeb or run locally against production DB
from src.domain.services.push_notification_service import send_push_notification
import asyncio

result = asyncio.run(send_push_notification(
    fcm_token="<token from DB>",
    title="FloodSafe Test",
    body="Push notification is working!",
    click_url="https://frontend-lime-psi-83.vercel.app"
))
print(f"Push sent: {result}")
```

6. Verify notification appears (even with tab closed)
7. Click notification → opens FloodSafe

**Kill criteria:**
- FCM `getToken` fails → check VAPID key
- Push doesn't show when tab closed → `firebase-messaging-sw.js` not registering
- Backend can't init Firebase → check `FIREBASE_SERVICE_ACCOUNT_B64` encoding

**Step 5: Commit results**

```bash
git commit --allow-empty -m "chore: Phase 1B complete — FCM push PoC verified"
```

---

## Phase 2A: Route-Based Push Monitoring

> **Why:** This is the core value proposition — proactive flood alerts on saved routes. Uses PostGIS spatial queries (already available) + cached FHI scores (already computed hourly).

---

### Task 14: Route monitor service

**Files:**
- Create: `apps/backend/src/domain/services/route_monitor_service.py`
- Modify: `apps/backend/src/infrastructure/models.py` (add notification tracking to SavedRoute)

**READ `models.py` FIRST before modifying.**

**Step 1: Add notification tracking to SavedRoute**

In `apps/backend/src/infrastructure/models.py`, add to SavedRoute class:

```python
# Notification cooldown fields
last_notified_at = Column(DateTime, nullable=True)
last_notified_severity = Column(String, nullable=True)  # "low", "medium", "high", "critical"
```

**Step 2: Create migration**

Create `apps/backend/scripts/migrate_add_route_notification.py`:

```python
"""Add notification tracking columns to saved_routes table."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import create_engine, text
from src.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE saved_routes ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMP;
        ALTER TABLE saved_routes ADD COLUMN IF NOT EXISTS last_notified_severity VARCHAR;
    """))
    conn.commit()
    print("Migration complete: added notification tracking to saved_routes")
```

**Step 3: Create route monitor service**

Create `apps/backend/src/domain/services/route_monitor_service.py`:

```python
"""Route Monitor Service.

Checks saved routes against current hotspot FHI scores.
Sends push notifications when a route's risk level transitions upward.
Uses PostGIS for spatial proximity (300m buffer around route waypoints).
"""
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..services.push_notification_service import send_push_notification
from ...infrastructure.models import User, SavedRoute

logger = logging.getLogger(__name__)

# Cooldown: don't re-notify for same severity within 6 hours
NOTIFICATION_COOLDOWN_HOURS = 6

# Proximity: hotspot must be within 300m of route waypoint
PROXIMITY_METERS = 300

# Minimum FHI severity to trigger notification
MIN_NOTIFY_SEVERITY = "high"  # "high" or "critical"

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


async def check_routes_and_notify(db: Session) -> dict:
    """Check all saved routes for HIGH+ hotspots and send push notifications.

    Returns summary dict with counts.
    """
    # Get all users with FCM tokens and saved routes
    users_with_routes = (
        db.query(User)
        .filter(User.fcm_token.isnot(None))
        .filter(User.saved_routes.any())
        .all()
    )

    checked = 0
    notified = 0
    skipped_cooldown = 0

    for user in users_with_routes:
        for route in user.saved_routes:
            checked += 1
            result = await _check_single_route(db, user, route)
            if result == "notified":
                notified += 1
            elif result == "cooldown":
                skipped_cooldown += 1

    return {
        "users_checked": len(users_with_routes),
        "routes_checked": checked,
        "notifications_sent": notified,
        "skipped_cooldown": skipped_cooldown,
    }


async def _check_single_route(
    db: Session, user: User, route: SavedRoute
) -> str:
    """Check one route for nearby HIGH+ hotspots.

    Returns: "notified", "cooldown", "safe", or "no_token"
    """
    if not user.fcm_token:
        return "no_token"

    # Find highest severity hotspot within 300m of route endpoints
    origin = route.origin  # JSON with lat/lng
    destination = route.destination  # JSON with lat/lng

    if not origin or not destination:
        return "safe"

    max_severity = await _get_max_nearby_severity(
        db, origin.get("lat"), origin.get("lng"),
        destination.get("lat"), destination.get("lng"),
        user.city_preference or "delhi",
    )

    if not max_severity or SEVERITY_ORDER.get(max_severity, 0) < SEVERITY_ORDER[MIN_NOTIFY_SEVERITY]:
        return "safe"

    # Check cooldown
    if route.last_notified_at and route.last_notified_severity:
        hours_since = (datetime.utcnow() - route.last_notified_at).total_seconds() / 3600
        if hours_since < NOTIFICATION_COOLDOWN_HOURS:
            # Only re-notify if severity INCREASED
            if SEVERITY_ORDER.get(max_severity, 0) <= SEVERITY_ORDER.get(route.last_notified_severity, 0):
                return "cooldown"

    # Send push notification
    route_name = route.name or f"{origin.get('address', 'Origin')} → {destination.get('address', 'Dest')}"
    success = await send_push_notification(
        fcm_token=user.fcm_token,
        title=f"Flood Alert: {max_severity.upper()} risk on your route",
        body=f"Route '{route_name}' passes through a {max_severity}-risk area. Consider an alternate route.",
        data={"route_id": str(route.id), "severity": max_severity},
        click_url=f"https://frontend-lime-psi-83.vercel.app/",
    )

    if success:
        route.last_notified_at = datetime.utcnow()
        route.last_notified_severity = max_severity
        db.commit()
        return "notified"

    return "safe"


async def _get_max_nearby_severity(
    db: Session,
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    city: str,
) -> str | None:
    """Find the highest FHI severity among hotspots within 300m of route endpoints.

    Uses the cached hotspot scores from the ML service (already computed hourly).
    Falls back to PostGIS spatial query against hotspots table.
    """
    result = db.execute(text("""
        SELECT MAX(
            CASE
                WHEN fhi_score >= 0.75 THEN 'critical'
                WHEN fhi_score >= 0.5 THEN 'high'
                WHEN fhi_score >= 0.25 THEN 'medium'
                ELSE 'low'
            END
        ) as max_severity
        FROM hotspots
        WHERE city = :city
        AND fhi_score >= 0.5
        AND (
            ST_DWithin(
                location::geography,
                ST_SetSRID(ST_MakePoint(:origin_lng, :origin_lat), 4326)::geography,
                :radius
            )
            OR ST_DWithin(
                location::geography,
                ST_SetSRID(ST_MakePoint(:dest_lng, :dest_lat), 4326)::geography,
                :radius
            )
        )
    """), {
        "city": city,
        "origin_lat": origin_lat, "origin_lng": origin_lng,
        "dest_lat": dest_lat, "dest_lng": dest_lng,
        "radius": PROXIMITY_METERS,
    })

    row = result.fetchone()
    return row[0] if row and row[0] else None
```

> **Note:** This queries the `hotspots` table directly. The `fhi_score` column must exist and be updated by the FHI calculator. Verify this column exists in `models.py` before proceeding.

**Step 4: Run tests**

```bash
cd apps/backend && pytest
```

**Step 5: Commit**

```bash
git add apps/backend/src/domain/services/route_monitor_service.py \
       apps/backend/src/infrastructure/models.py \
       apps/backend/scripts/migrate_add_route_notification.py
git commit -m "feat: route monitor service with PostGIS proximity + cooldown"
```

---

### Task 15: Cron endpoint for route checking

**Files:**
- Create: `apps/backend/src/api/cron.py`
- Modify: `apps/backend/src/main.py` (register router)

**Step 1: Create cron router**

Create `apps/backend/src/api/cron.py`:

```python
"""Cron endpoints — triggered by external cron service (cron-job.org).

These endpoints are called periodically and should NOT require authentication.
They are idempotent and safe to retry.
"""
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..infrastructure.database import get_db
from ..domain.services.route_monitor_service import check_routes_and_notify

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cron", tags=["cron"])

# Simple shared secret to prevent unauthorized cron triggers
CRON_SECRET = os.environ.get("CRON_SECRET", "")


@router.get("/check-routes")
async def cron_check_routes(
    db: Session = Depends(get_db),
    x_cron_secret: str = Header(default="", alias="X-Cron-Secret"),
):
    """Check saved routes for flood risk and send push notifications.

    Called every 15 minutes by external cron service.
    Protected by X-Cron-Secret header.
    """
    if CRON_SECRET and x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    result = await check_routes_and_notify(db)
    logger.info(f"Route check complete: {result}")
    return result
```

**Step 2: Register router in main.py**

Add to `apps/backend/src/main.py`:
```python
from .api.cron import router as cron_router
app.include_router(cron_router, prefix="/api")
```

**Step 3: Set CRON_SECRET env var on Koyeb**

Generate a random secret and add as `CRON_SECRET` env var on Koyeb.

**Step 4: Run tests + commit**

```bash
cd apps/backend && pytest
git add apps/backend/src/api/cron.py apps/backend/src/main.py
git commit -m "feat: add GET /api/cron/check-routes endpoint for external cron"
```

---

### Task 16: Set up external cron + deploy

**Step 1: Run migrations on production DB**

```bash
cd apps/backend
python scripts/migrate_add_fcm_token.py
python scripts/migrate_add_route_notification.py
```

**Step 2: Deploy backend**

```bash
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

**Step 3: Set up cron-job.org**

1. Sign up at https://cron-job.org (free tier)
2. Create new cron job:
   - URL: `https://floodsafe-backend-floodsafe-dda84554.koyeb.app/api/cron/check-routes`
   - Schedule: Every 15 minutes
   - Timeout: 30 seconds (accommodates Koyeb cold start)
   - Headers: `X-Cron-Secret: <your-secret>`
   - Method: GET

**Step 4: Verify cron fires**

Wait 15 minutes, then check Koyeb logs:
```bash
./koyeb-cli-extracted/koyeb.exe services logs floodsafe-backend/backend
```
Look for: `Route check complete: {users_checked: X, ...}`

**Step 5: Commit**

```bash
git commit --allow-empty -m "chore: Phase 2A complete — route monitoring cron deployed"
```

---

## Phase 2B: SMS Compose for Offline SOS

> **Why:** When internet is down during a flood, SMS is the only channel that works. This adds a "pre-composed emergency SMS" that opens the native SMS app with pre-filled recipients and message.
>
> **Prerequisite:** Phase 1A (Capacitor) must be complete — SMS compose requires native plugin.

---

### Task 17: Install Capacitor SMS plugin

**Step 1: Install**

```bash
cd apps/frontend
npm install @byteowls/capacitor-sms
npx cap sync
```

**Step 2: Verify Android permissions**

Check `apps/frontend/android/app/src/main/AndroidManifest.xml` includes:
```xml
<uses-permission android:name="android.permission.SEND_SMS" />
```

If not present, add it manually.

**Step 3: Commit**

```bash
git add apps/frontend/package.json apps/frontend/package-lock.json
git commit -m "feat: add Capacitor SMS plugin for offline SOS"
```

---

### Task 18: Add SMS compose fallback to SOS queue

**Files:**
- Modify: `apps/frontend/src/hooks/useSOSQueue.ts`

**READ `useSOSQueue.ts` FIRST before modifying.**

**Step 1: Add SMS compose function**

Add to `apps/frontend/src/hooks/useSOSQueue.ts`:

```typescript
import { Capacitor } from '@capacitor/core';

/**
 * Open native SMS compose with pre-filled emergency message.
 * Only works on Capacitor (native) — no-op on web.
 * User must manually tap Send (Play Store policy prohibits auto-send).
 */
async function composeSMSFallback(
    recipients: string[],
    location: { latitude: number; longitude: number },
    userName?: string,
): Promise<boolean> {
    if (!Capacitor.isNativePlatform()) {
        console.log('SMS compose only available on native platform');
        return false;
    }

    try {
        const { SmsManager } = await import('@byteowls/capacitor-sms');

        const lat = location.latitude.toFixed(6);
        const lng = location.longitude.toFixed(6);
        const name = userName || 'A FloodSafe user';
        const time = new Date().toLocaleTimeString();

        const message = [
            `SOS FLOOD EMERGENCY from ${name}`,
            `Location: ${lat}, ${lng}`,
            `Time: ${time}`,
            `Map: https://maps.google.com/?q=${lat},${lng}`,
            `Sent via FloodSafe`,
        ].join('\n');

        await SmsManager.send({
            numbers: recipients,
            text: message,
        });

        return true;
    } catch (error) {
        console.error('SMS compose failed:', error);
        return false;
    }
}
```

**Step 2: Integrate into SOS flow**

In the existing `queueSOS` function, add SMS fallback when offline:

```typescript
// After queuing to IndexedDB (existing code), add:
if (!navigator.onLine && Capacitor.isNativePlatform()) {
    // Offline + native: offer SMS compose as immediate fallback
    const circleContacts = /* get from cached query data */;
    if (circleContacts?.length > 0) {
        await composeSMSFallback(
            circleContacts.map((c: { phone: string }) => c.phone),
            location,
            userName,
        );
    }
}
```

> **Note:** The exact integration point depends on the current `queueSOS` implementation. READ the file, find where items are added to the queue, and add the SMS fallback after that point.

**Step 3: Type check + build**

```bash
cd apps/frontend && npx tsc --noEmit && npm run build && npx cap sync
```

**Step 4: Test on emulator**

1. Enable Airplane mode on emulator
2. Tap SOS button
3. Verify native SMS compose opens with pre-filled message
4. Verify recipients are populated from safety circle
5. Verify SOS also queued to IndexedDB (dual path)

**Step 5: Commit**

```bash
git add apps/frontend/src/hooks/useSOSQueue.ts
git commit -m "feat: add SMS compose fallback for offline SOS (Capacitor)"
```

---

### Task 19: Cache safety circle contacts for offline access

**Files:**
- Modify: `apps/frontend/src/hooks/useSOSQueue.ts` or relevant circle hook

**Context:** SMS compose needs phone numbers when offline. Safety circle contacts are currently fetched from API only. They need to be cached in IndexedDB or TanStack Query's persisted cache so they're available offline.

**Step 1: Ensure safety circle query has staleTime**

In the safety circle hook (find via `useQuery` with key `["my-circles"]`), ensure:
```typescript
staleTime: 1000 * 60 * 30,  // 30 minutes — contacts don't change often
gcTime: 1000 * 60 * 60 * 24, // 24 hours — keep in cache for offline
```

**Step 2: Add IndexedDB fallback for offline**

Store a copy of safety circle contacts in the same IndexedDB used by the SOS queue (`floodsafe-sos`). Update on every successful API fetch.

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: cache safety circle contacts for offline SMS compose"
```

---

## Phase 3: WhatsApp Polish

> **Why:** WhatsApp inbound sync works, but users don't know about the LINK command. Small UX improvements to increase adoption.

---

### Task 20: Auto-prompt LINK after anonymous reports

**Files:**
- Modify: `apps/backend/src/api/webhook.py` (Twilio webhook)
- Modify: `apps/backend/src/api/whatsapp_meta.py` (Meta webhook)

**Context:** When a WhatsApp user submits a report without being linked to an account (`user_id=None`), the bot should suggest linking. Currently, LINK is only mentioned in STATUS response.

**Step 1: Add LINK prompt to Twilio report confirmation**

After a successful `create_sos_report` where `user is None`, append to the response:

```python
if user is None:
    response += "\n\nTip: Send LINK to connect your WhatsApp to your FloodSafe account for personalized alerts."
```

**Step 2: Add LINK prompt to Meta report confirmation**

Same pattern in `_create_report_with_photo` and `_finalize_without_photo`.

**Step 3: Run tests + commit**

```bash
cd apps/backend && pytest
git add apps/backend/src/api/webhook.py apps/backend/src/api/whatsapp_meta.py
git commit -m "feat: auto-prompt LINK command after anonymous WhatsApp reports"
```

---

### Task 21: Improve welcome message with LINK info

**Files:**
- Modify: WhatsApp message templates (find via `TemplateKey.WELCOME`)

**Step 1: Find welcome template**

Search for `TemplateKey.WELCOME` or `WELCOME` in WhatsApp message templates.

**Step 2: Add LINK to the welcome message**

Append to the welcome message:
```
Already have a FloodSafe account? Send LINK to connect.
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: mention LINK command in WhatsApp welcome message"
```

---

## Phase 2A Deploy Gate

After completing Phase 2A + 2B:

**Quality gates:**
```bash
cd apps/frontend && npx tsc --noEmit && npm run build
cd apps/backend && pytest
```

**Deploy:**
```bash
cd apps/frontend && npx vercel --prod
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
```

---

## Phase 3 Deploy Gate

After completing Phase 3:

```bash
cd apps/backend && pytest
./koyeb-cli-extracted/koyeb.exe services redeploy floodsafe-backend/backend
# Frontend not changed in Phase 3
```

---

## Decision Gates (from design doc)

```
After Phase 1:
  Q: Did Capacitor + FCM PoCs pass?
  → YES: Continue to Phase 2
  → NO (Capacitor failed): Pivot to PWA-only push (skip SMS compose)
  → NO (FCM failed): Debug Firebase config (likely fixable)

After Phase 3:
  Q: Has Meta Business Verification been approved?
  → YES: Proceed to WhatsApp outbound sync (separate plan)
  → NO: Accept inbound-only sync as final state
```

---

## Summary

| Phase | Tasks | Effort | Dependencies |
|-------|-------|--------|-------------|
| **0: WA Fixes** | 1-4 | 30 min | None |
| **1A: Capacitor** | 5-7 | 5-7 hrs | Android Studio |
| **1B: FCM Push** | 8-13 | 3-4 hrs | Firebase service account |
| **2A: Route Monitor** | 14-16 | 2 days | Phase 1B |
| **2B: SMS Compose** | 17-19 | 1 day | Phase 1A |
| **3: WA Polish** | 20-21 | 0.5 day | Phase 0 |

**Total: ~2-3 weeks of focused work.**
