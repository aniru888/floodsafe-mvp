# FloodSafe Profile Features Documentation

## Overview

The FloodSafe MVP now includes a comprehensive profile management system with notification preferences and watch areas functionality. This document outlines all the new features, database schema changes, API endpoints, and testing procedures.

---

## Features Implemented

### 1. **Enhanced User Profile**
- **Profile Information**
  - Username (editable)
  - Email (editable)
  - Phone number (optional)
  - Profile photo URL (for future avatar uploads)
  - Language preference (English/Hindi)
  - Member since date
  - Role badge

- **Gamification Dashboard**
  - Points & Level display
  - Progress bar to next level
  - Reports statistics (submitted/verified/pending)
  - Badges collection
  - Visual progress indicators

### 2. **Notification Preferences**
Allows users to control how they receive flood alerts:
- **Push Notifications** (default: enabled)
- **SMS Alerts** (default: enabled)
- **WhatsApp Updates** (default: disabled)
- **Email Notifications** (default: enabled)

### 3. **Alert Type Filtering**
Users can choose which alert severity levels to receive:
- 🟡 Yellow Watch alerts
- 🟠 Orange Advisory
- 🔴 Red Warning
- ⚫ Emergency alerts

All enabled by default, stored as JSON in database.

### 4. **Watch Areas**
Users can save specific locations to monitor for flood alerts:
- Name the location (e.g., "My Home", "Office")
- Geolocation stored as PostGIS POINT
- Configurable radius (100m to 10km)
- CRUD operations via API
- Future: Automatic alerts when flood events occur in watch areas

### 5. **Language Support**
- English (default)
- हिन्दी (Hindi)
- Easily extensible for more languages

---

## Database Schema Changes

### Updated `users` Table

```sql
-- New columns added:
ALTER TABLE users ADD COLUMN phone VARCHAR;
ALTER TABLE users ADD COLUMN profile_photo_url VARCHAR;
ALTER TABLE users ADD COLUMN language VARCHAR DEFAULT 'english';
ALTER TABLE users ADD COLUMN notification_push BOOLEAN DEFAULT true;
ALTER TABLE users ADD COLUMN notification_sms BOOLEAN DEFAULT true;
ALTER TABLE users ADD COLUMN notification_whatsapp BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN notification_email BOOLEAN DEFAULT true;
ALTER TABLE users ADD COLUMN alert_preferences VARCHAR DEFAULT '{"watch":true,"advisory":true,"warning":true,"emergency":true}';
```

### New `watch_areas` Table

```sql
CREATE TABLE watch_areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    radius FLOAT DEFAULT 1000.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_watch_areas_user_id ON watch_areas(user_id);
```

---

## API Endpoints

### User Endpoints

#### Update User Profile
```http
PATCH /api/users/{user_id}
Content-Type: application/json

{
  "username": "new_username",
  "email": "new_email@example.com",
  "phone": "+91-9876543210",
  "language": "hindi",
  "notification_push": true,
  "notification_sms": false,
  "notification_whatsapp": true,
  "notification_email": true,
  "alert_preferences": "{\"watch\":true,\"advisory\":true,\"warning\":false,\"emergency\":true}"
}
```

**Response:**
```json
{
  "id": "uuid",
  "username": "new_username",
  "email": "new_email@example.com",
  "phone": "+91-9876543210",
  "language": "hindi",
  "points": 100,
  "level": 2,
  "notification_push": true,
  "notification_sms": false,
  "notification_whatsapp": true,
  "notification_email": true,
  "alert_preferences": {
    "watch": true,
    "advisory": true,
    "warning": false,
    "emergency": true
  }
}
```

### Watch Area Endpoints

#### Create Watch Area
```http
POST /api/watch-areas/
Content-Type: application/json

{
  "user_id": "uuid",
  "name": "My Home - Koramangala",
  "latitude": 12.935,
  "longitude": 77.625,
  "radius": 1000.0
}
```

#### Get User's Watch Areas
```http
GET /api/watch-areas/user/{user_id}
```

#### Get Specific Watch Area
```http
GET /api/watch-areas/{watch_area_id}
```

#### Delete Watch Area
```http
DELETE /api/watch-areas/{watch_area_id}
```

---

## Frontend Implementation

### ProfileScreen Component

**Location:** `apps/frontend/src/components/screens/ProfileScreen.tsx`

**Features:**
- Real-time data fetching with TanStack Query
- Optimistic UI updates
- Edit profile dialog
- Toggle switches for notifications
- Radio buttons for language selection
- Checkboxes for alert type preferences
- Watch areas display
- Responsive design (mobile & desktop)

**Key Technologies:**
- React Query for data fetching & caching
- Radix UI components (accessible)
- Tailwind CSS for styling
- shadcn/ui component library

### Edit Profile Dialog

Allows users to update:
- Username
- Email
- Phone number

Changes are validated and saved via API with error handling.

---

## Testing

### Migration Script

Run the database migration to add new fields and tables:

```bash
python apps/backend/src/scripts/migrate_profile_features.py
```

This script:
- Adds all new columns to `users` table
- Creates `watch_areas` table
- Creates necessary indexes
- Uses `IF NOT EXISTS` for safe re-runs

### Verification Script

Test all profile features end-to-end:

```bash
python apps/backend/src/scripts/verify_profile.py
```

This script verifies:
- ✓ User creation with new fields
- ✓ Profile updates
- ✓ Notification preference changes
- ✓ Language switching
- ✓ Watch area CRUD operations
- ✓ PostGIS location storage
- ✓ JSON field parsing
- ✓ Data integrity

### Manual Testing

1. **Start the application:**
   ```bash
   docker compose up -d
   ```

2. **Seed the database:**
   ```bash
   docker compose exec backend python src/scripts/seed_db.py
   ```

3. **Run migration:**
   ```bash
   docker compose exec backend python src/scripts/migrate_profile_features.py
   ```

4. **Access the frontend:**
   - Navigate to http://localhost:5175
   - Click on Profile tab (bottom nav on mobile, sidebar on desktop)

5. **Test features:**
   - View profile information
   - Edit profile (username, email, phone)
   - Toggle notification preferences
   - Change language setting
   - View watch areas (if any)

---

## Future Enhancements

### Planned Features

1. **Profile Photo Upload**
   - AWS S3/Google Cloud Storage integration
   - Image cropping & optimization
   - Avatar preview

2. **Watch Area Alerts**
   - Real-time monitoring of flood events
   - Automatic notifications when flood occurs in watch area
   - Distance-based alert prioritization

3. **Notification Delivery**
   - Twilio integration for SMS
   - WhatsApp Business API integration
   - Push notifications via Firebase/OneSignal
   - Email via SendGrid/Mailgun

4. **Advanced Preferences**
   - Quiet hours (no notifications during sleep)
   - Alert frequency limits (max N per hour)
   - Custom alert sounds
   - Notification grouping

5. **Account Security**
   - Password management
   - Two-factor authentication
   - Login history
   - Device management

6. **Privacy Controls**
   - Profile visibility settings
   - Data export (GDPR compliance)
   - Account deletion

---

## Technical Notes

### JSON Fields
- `alert_preferences` is stored as VARCHAR containing JSON string
- Automatically parsed to dict/object in API responses via Pydantic validators
- Default value ensures all alert types are enabled

### PostGIS Integration
- Watch area locations use SRID 4326 (WGS 84)
- Hybrid properties extract lat/lng from geometry
- Supports spatial queries for future distance-based features

### CORS Configuration
Frontend can access backend from multiple ports during development:
- localhost:5175 (Vite dev server)
- localhost:3000 (alternative React port)
- localhost:8000 (API documentation)

### Data Validation
- Username: 3-50 characters
- Email: RFC 5322 pattern validation
- Phone: Optional, no specific format enforced
- Latitude: -90 to 90
- Longitude: -180 to 180
- Watch area radius: 100m to 10km

---

## API Documentation

Interactive API documentation available at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

All new endpoints are automatically documented with:
- Request/response schemas
- Example values
- Error codes
- Try-it-out functionality

---

## Troubleshooting

### Migration Issues

**Problem:** "Column already exists" error
**Solution:** The migration uses `IF NOT EXISTS`, so it's safe to re-run. If using PostgreSQL < 9.6, manually check if columns exist first.

**Problem:** Watch areas table not created
**Solution:** Ensure PostGIS extension is enabled:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Frontend Issues

**Problem:** Profile shows "No User Found"
**Solution:** Run the seed script to create demo users:
```bash
docker compose exec backend python src/scripts/seed_db.py
```

**Problem:** Notification toggles don't save
**Solution:** Check browser console for API errors. Ensure backend is running and CORS is configured.

**Problem:** Watch areas not displaying
**Solution:** No watch areas exist initially. This is expected. Watch area creation UI can be added in future.

---

## Contributing

When adding new profile features:

1. Update domain models (`domain/models.py`)
2. Update infrastructure models (`infrastructure/models.py`)
3. Create/update API endpoints (`api/`)
4. Update frontend types and components
5. Add migration script for schema changes
6. Create verification tests
7. Update this documentation

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/aniru888/floodsafe-mvp/issues
- Email: support@floodsafe.ai

---

**Last Updated:** November 20, 2024
**Version:** 1.0.0 (MVP)
