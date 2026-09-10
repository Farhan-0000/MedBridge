"""
Integration Tests for Main Application Lifespan, CORS, and Routes (TASK-30, Module M-19).

Verifies:
1. Application startup and shutdown lifespan execution.
2. CORS headers enforcement using Settings.CORS_ORIGINS.
3. Mounted API routes under /api and /health.
"""
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import pytest

from medbridge.config import Settings
from medbridge.main import app, create_app


@pytest.fixture
def custom_settings() -> Settings:
    """Settings configured with specific CORS origins for testing."""
    return Settings(
        GROQ_API_KEY="test_key",
        POSTGRES_PASSWORD="test_password",
        CORS_ORIGINS=["http://localhost:8501", "https://app.medbridge.internal"],
    )


class TestMainAppLifespan:
    """Verify application lifespan startup and shutdown hooks."""

    @patch("medbridge.main.init_db", new_callable=AsyncMock)
    @patch("medbridge.main.close_db", new_callable=AsyncMock)
    @patch("medbridge.main.EmbeddingClient")
    def test_lifespan_startup_and_shutdown(
        self,
        mock_embedder_cls,
        mock_close_db,
        mock_init_db,
        custom_settings: Settings,
    ) -> None:
        """Verify startup initializes DB and embedder; shutdown closes DB."""
        mock_embedder = mock_embedder_cls.return_value
        mock_embedder._get_dense_model.return_value = "dense_warmed"
        mock_embedder._get_sparse_model.return_value = "sparse_warmed"

        test_app = create_app(custom_settings)

        # Entering TestClient context triggers lifespan startup
        with TestClient(test_app) as client:
            mock_init_db.assert_awaited_once()
            mock_embedder._get_dense_model.assert_called_once()
            mock_embedder._get_sparse_model.assert_called_once()

            # Verify health probe responds
            resp = client.get("/health")
            assert resp.status_code in (200, 503)

        # Exiting TestClient context triggers lifespan shutdown
        mock_close_db.assert_awaited_once()


class TestMainAppCORS:
    """Verify Cross-Origin Resource Sharing (CORS) enforcement."""

    def test_cors_allowed_origin_preflight(self, custom_settings: Settings) -> None:
        """Preflight OPTIONS request from allowed origin returns CORS headers."""
        test_app = create_app(custom_settings)
        client = TestClient(test_app)

        headers = {
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        response = client.options("/api/sessions", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8501"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_allowed_origin_get_request(self, custom_settings: Settings) -> None:
        """GET request from allowed origin includes access-control-allow-origin header."""
        test_app = create_app(custom_settings)
        client = TestClient(test_app)

        headers = {"Origin": "https://app.medbridge.internal"}
        response = client.get("/health", headers=headers)
        assert response.headers.get("access-control-allow-origin") == "https://app.medbridge.internal"

    def test_cors_disallowed_origin_rejected(self, custom_settings: Settings) -> None:
        """Requests from disallowed origins do not receive allow-origin header."""
        test_app = create_app(custom_settings)
        client = TestClient(test_app)

        headers = {
            "Origin": "http://unauthorized-attacker.com",
            "Access-Control-Request-Method": "POST",
        }
        response = client.options("/api/sessions", headers=headers)
        # Starlette CORS does not return allow-origin for disallowed origins
        assert "access-control-allow-origin" not in response.headers


class TestMainAppRoutesMounted:
    """Verify all expected routes are mounted under /api and /health."""

    def test_health_routes_accessible(self) -> None:
        """Both /health and /api/health should resolve."""
        client = TestClient(app)
        resp_root = client.get("/health")
        assert resp_root.status_code in (200, 503)

        resp_api = client.get("/api/health")
        assert resp_api.status_code in (200, 503)

    def test_sessions_router_mounted_under_api(self) -> None:
        """Sessions routes must be mounted with /api prefix."""
        client = TestClient(app)
        # Requesting without /api should return 404
        resp_bare = client.post("/sessions")
        assert resp_bare.status_code == 404

        # Requesting with /api should hit the handler (even if DB error or validation)
        resp_api = client.get("/api/sessions/invalid-uuid/history")
        assert resp_api.status_code == 422
