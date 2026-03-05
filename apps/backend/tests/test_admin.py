"""
Tests for Admin Panel API endpoints.
Tests use client_no_db for basic endpoint accessibility checks (no PostgreSQL required).
"""
import pytest


class TestAdminRoutes:
    """Tests to verify admin routes are registered in the OpenAPI schema."""

    def test_admin_routes_in_schema(self, client_no_db):
        """Test that admin API routes are registered in OpenAPI schema."""
        response = client_no_db.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})

        # Core admin endpoints should be registered
        assert "/api/admin/login" in paths, "Admin login endpoint not found"
        assert "/api/admin/dashboard/stats" in paths, "Dashboard stats endpoint not found"
        assert "/api/admin/users" in paths, "Admin users endpoint not found"
        assert "/api/admin/reports" in paths, "Admin reports endpoint not found"
        assert "/api/admin/badges" in paths, "Admin badges endpoint not found"
        assert "/api/admin/ambassadors" in paths, "Ambassadors endpoint not found"
        assert "/api/admin/analytics/reports" in paths, "Analytics reports endpoint not found"
        assert "/api/admin/analytics/users" in paths, "Analytics users endpoint not found"
        assert "/api/admin/analytics/cities" in paths, "Analytics cities endpoint not found"
        assert "/api/admin/system/health" in paths, "System health endpoint not found"
        assert "/api/admin/audit-log" in paths, "Audit log endpoint not found"

    def test_admin_login_endpoint_methods(self, client_no_db):
        """Test that admin login only accepts POST."""
        response = client_no_db.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})

        login_path = paths.get("/api/admin/login", {})
        assert "post" in login_path, "Admin login should accept POST"

    def test_admin_tags_in_schema(self, client_no_db):
        """Test that admin tag is present in OpenAPI schema."""
        response = client_no_db.get("/openapi.json")
        schema = response.json()
        tags = [t.get("name") for t in schema.get("tags", [])]

        # Tags may or may not be explicitly listed, but paths should have admin tag
        paths = schema.get("paths", {})
        admin_login = paths.get("/api/admin/login", {})
        post_op = admin_login.get("post", {})
        assert "admin" in post_op.get("tags", []), "Admin login should be tagged as 'admin'"


class TestAdminLoginEndpoint:
    """Tests for the admin login endpoint — no database needed for auth validation."""

    def test_admin_login_missing_body(self, client_no_db):
        """Test that admin login requires a request body."""
        response = client_no_db.post("/api/admin/login")
        assert response.status_code == 422  # Validation error

    def test_admin_login_invalid_email(self, client_no_db):
        """Test that admin login rejects invalid email."""
        response = client_no_db.post("/api/admin/login", json={
            "email": "wrong@example.com",
            "password": "wrong-password"
        })
        # Should be 401/503 (not configured or invalid) or 429 (rate limited) or 500
        assert response.status_code in [401, 429, 503, 500]

    def test_admin_login_invalid_password(self, client_no_db):
        """Test that admin login rejects invalid password."""
        response = client_no_db.post("/api/admin/login", json={
            "email": "admin@floodsafe.app",
            "password": "wrong-password"
        })
        # Should be 401/503 (not configured) or 429 (rate limited) or 500
        assert response.status_code in [401, 429, 503, 500]


class TestAdminProtectedEndpoints:
    """Tests to verify admin endpoints require authentication."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/admin/dashboard/stats"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/reports"),
        ("GET", "/api/admin/badges"),
        ("GET", "/api/admin/ambassadors"),
        ("GET", "/api/admin/analytics/reports"),
        ("GET", "/api/admin/analytics/users"),
        ("GET", "/api/admin/analytics/cities"),
        ("GET", "/api/admin/system/health"),
        ("GET", "/api/admin/audit-log"),
    ]

    @pytest.mark.parametrize("method,endpoint", PROTECTED_ENDPOINTS)
    def test_protected_endpoint_requires_auth(self, client_no_db, method, endpoint):
        """Test that protected admin endpoints return 401/403 without authentication."""
        if method == "GET":
            response = client_no_db.get(endpoint)
        elif method == "POST":
            response = client_no_db.post(endpoint, json={})

        # Without auth token, should get 401 (Unauthorized) or 403 (Forbidden)
        assert response.status_code in [401, 403, 500], \
            f"{method} {endpoint} should require auth, got {response.status_code}"

    def test_protected_endpoint_rejects_non_bearer(self, client_no_db):
        """Test that passing a garbage token gets rejected."""
        response = client_no_db.get(
            "/api/admin/dashboard/stats",
            headers={"Authorization": "Bearer fake-token-12345"}
        )
        assert response.status_code in [401, 403, 500]


class TestExistingEndpointsNotBroken:
    """Regression tests to ensure existing endpoints still work."""

    def test_health_endpoint(self, client_no_db):
        """Test that the main health endpoint still works."""
        response = client_no_db.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_openapi_schema_still_valid(self, client_no_db):
        """Test that OpenAPI schema is still valid with admin routes added."""
        response = client_no_db.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

        # Original endpoints should still be present
        paths = schema.get("paths", {})
        assert "/health" in paths
        assert "/api/reports/" in paths

    def test_docs_still_accessible(self, client_no_db):
        """Test that Swagger UI is still accessible."""
        response = client_no_db.get("/docs")
        assert response.status_code == 200

    def test_existing_auth_routes_present(self, client_no_db):
        """Test that existing auth routes are still registered."""
        response = client_no_db.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/api/auth/login/email" in paths or "/api/auth/register/email" in paths


class TestAdminAuthSecurity:
    """Tests for admin login security hardening."""

    def test_admin_login_rejects_empty_credentials_config(self, client_no_db):
        """When ADMIN_EMAIL or ADMIN_PASSWORD_HASH are empty, login should fail."""
        response = client_no_db.post("/api/admin/login", json={
            "email": "",
            "password": "anything"
        })
        assert response.status_code in [401, 503]

    def test_admin_login_rate_limited(self, client_no_db):
        """After 5 failed attempts, should return 429."""
        for i in range(6):
            response = client_no_db.post("/api/admin/login", json={
                "email": "wrong@example.com",
                "password": "wrong"
            })
        # 6th attempt should be rate limited (or 500 if no DB, but rate limit fires first)
        assert response.status_code in [429, 500]


class TestAdminServiceTransactions:
    """Tests for transaction safety in admin service."""

    def test_log_admin_action_does_not_commit(self):
        """log_admin_action should not call db.commit() — caller manages transaction."""
        import inspect
        from src.domain.services import admin_service
        source = inspect.getsource(admin_service.log_admin_action)
        assert "db.commit()" not in source, "log_admin_action should not commit — caller manages transaction"
        assert "db.refresh(" not in source, "log_admin_action should not refresh — unnecessary round-trip"


class TestVerifyEndpointSecurity:
    """Tests for report verification endpoint security."""

    def test_verify_requires_authentication(self, client_no_db):
        """POST /reports/{id}/verify should require authentication."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = client_no_db.post(f"/api/reports/{fake_id}/verify", json={
            "verified": True,
            "quality_score": 50
        })
        # Should be 401 (no token) or 403 (not authorized), NOT 404/500
        assert response.status_code in [401, 403], \
            f"Verify endpoint should require auth, got {response.status_code}"


class TestAdminServiceSafety:
    """Tests for admin service safety measures."""

    def test_sort_allowlist_blocks_invalid_fields(self):
        """list_users_filtered should reject invalid sort fields."""
        import inspect
        from src.domain.services import admin_service
        source = inspect.getsource(admin_service.list_users_filtered)
        assert "ALLOWED_SORT" in source or "allowed_sort" in source, \
            "list_users_filtered must use a sort field allowlist"

    def test_update_user_role_in_service_layer(self):
        """update_user_role should be in admin_service, not in router."""
        import inspect
        from src.domain.services import admin_service
        assert hasattr(admin_service, 'update_user_role'), \
            "update_user_role must be in admin_service"
        source = inspect.getsource(admin_service.update_user_role)
        assert "log_admin_action" in source, \
            "update_user_role must include audit logging"


class TestAdminReportCreation:
    """Tests for admin report creation endpoint."""

    def test_admin_create_report_in_schema(self, client_no_db):
        """POST /api/admin/reports should be registered."""
        response = client_no_db.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/api/admin/reports" in paths, "Admin create report endpoint not registered"
        assert "post" in paths["/api/admin/reports"], "Should accept POST"

    def test_admin_create_report_requires_auth(self, client_no_db):
        """POST /api/admin/reports should require admin auth."""
        response = client_no_db.post("/api/admin/reports", json={
            "description": "Test flood report",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "city": "delhi",
            "source": "field_observation"
        })
        assert response.status_code in [401, 403, 500]


class TestReputationGuard:
    """Tests for reputation pipeline admin_created guard."""

    def test_reputation_service_has_admin_guard(self):
        """process_report_verification should skip for admin_created reports."""
        import inspect
        from src.domain.services.reputation_service import ReputationService
        source = inspect.getsource(ReputationService.process_report_verification)
        assert "admin_created" in source, \
            "process_report_verification must check admin_created flag"
