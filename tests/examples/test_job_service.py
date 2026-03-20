import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from orga.model import OrganizationProfile

# Import app from job service
from examples.job_service.main import app, job_store, pipeline

class TestJobService:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_pipeline_run(self, mocker):
        mock_run = AsyncMock()
        # Mock the pipeline run_from_url globally
        mocker.patch.object(pipeline, "run_from_url", side_effect=mock_run)
        return mock_run

    def test_submit_job(self, client):
        """
        Verify POST /jobs returns job_id.
        """
        response = client.post("/jobs", json={"urls": ["https://example.com"]})
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_get_job_status(self, client, mock_pipeline_run):
        """
        Verify GET /jobs/{id} returns status and eventually results.
        """
        # Setup mock result BEFORE triggering the job via POST
        mock_profile = OrganizationProfile(name="Site 1")
        mock_pipeline_run.return_value = mock_profile

        # 1. Submit
        response = client.post("/jobs", json={"urls": ["https://site1.com"]})
        job_id = response.json()["job_id"]
        
        # 2. Check initial status (might be pending or processing immediately)
        
        # 3. Check status
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        # It should eventually be completed
        assert status_data["id"] == job_id
        assert status_data["status"] in ["pending", "processing", "completed"]

    def test_job_store_persistence(self, client):
        # Manually inject a job to test GET
        from datetime import datetime
        job_id = "test-job-123"
        job_store[job_id] = {
            "id": job_id,
            "status": "completed",
            "submitted_at": datetime.utcnow(),
            "results": [{"name": "Stored Result"}],
            "errors": []
        }
        
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        # Since response model doesn't validate "results" content strictly beyond list of dicts,
        # but we need to check if our data came back.
        # "results" is List[Dict[str, Any]].
        results = response.json()["results"]
        assert len(results) > 0
        assert results[0]["name"] == "Stored Result"
