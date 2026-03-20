import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from orga.model import OrganizationProfile

# Import app and the global pipeline instance
# We need to ensure python path allows this.
# Assuming running with PYTHONPATH=.
from examples.extractor_service.main import app, pipeline

class TestExtractorService:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_pipeline_run(self, mocker):
        # Patch the 'run_from_url' method of the GLOBAL pipeline instance imported from main
        mock_run = AsyncMock()
        mocker.patch.object(pipeline, "run_from_url", side_effect=mock_run)
        return mock_run

    def test_extract_endpoint_success(self, client, mock_pipeline_run):
        """
        Verify POST /extract returns 200 and profile data.
        """
        # Setup mock return
        mock_profile = OrganizationProfile(name="Test Org")
        mock_pipeline_run.return_value = mock_profile

        response = client.post("/extract", json={"url": "https://example.com"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Org"
        assert data["schema_version"] == "0.1.0"
        
        # Verify it was called
        # Pydantic HttpUrl normalizes domains with trailing slash
        mock_pipeline_run.assert_called_once_with("https://example.com/")

    def test_extract_endpoint_validation_error(self, client):
        """
        Verify validation error for missing URL.
        """
        response = client.post("/extract", json={})
        assert response.status_code == 422
