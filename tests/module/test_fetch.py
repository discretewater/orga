from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from orga.fetch import HttpxFetcher
from orga.model import Document, OrgaConfig


class TestHttpxFetcher:
    """
    Test the behavior of the HttpxFetcher module, including success, retry, timeout, and error handling.
    """

    @pytest.fixture
    def mock_client(self):
        """
        Create a Mock for httpx.AsyncClient.
        """
        with patch("httpx.AsyncClient") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """
        Test successful page fetch and verify the returned Document object structure.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Success</html>"
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.content = b"<html>Success</html>"
        mock_response.url = httpx.URL("https://example.com") # Simulate final URL

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            config = OrgaConfig()
            fetcher = HttpxFetcher(config)
            doc = await fetcher.fetch("https://example.com")
            
            assert isinstance(doc, Document)
            assert doc.status_code == 200
            assert doc.content == "<html>Success</html>"
            assert doc.url == "https://example.com"
            assert doc.content_type == "text/html; charset=utf-8"

    @pytest.mark.asyncio
    async def test_fetch_404_not_found(self):
        """
        Test 404 response, which should return a Document but flag the status code and possibly contain a warning.
        """
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = httpx.URL("https://example.com/404")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            fetcher = HttpxFetcher(OrgaConfig())
            doc = await fetcher.fetch("https://example.com/404")
            
            assert doc.status_code == 404
            assert "Not Found" in doc.content

    @pytest.mark.asyncio
    async def test_fetch_timeout(self):
        """
        Test network timeout (TimeoutException) and verify if it throws a custom FetchError or returns a Document with error info.
        """
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
            fetcher = HttpxFetcher(OrgaConfig())
            doc = await fetcher.fetch("https://timeout.com")
            assert doc.status_code != 200
            # Check if the message contains "timed out" (case-insensitive)
            assert any("timed out" in w.message.lower() for w in doc.fetch_warnings)

    @pytest.mark.asyncio
    async def test_fetch_retry_logic(self):
        """
        Test retry logic.
        Simulate failures for the first two attempts (e.g., 500 error) and success on the third.
        """
        # Configure failed Mock Response
        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.text = "Server Error"
        # Key: headers must behave like a dict
        fail_response.headers = {"content-type": "text/html"}
        # Key: raise_for_status must raise an exception
        def raise_500():
            raise httpx.HTTPStatusError("500 Error", request=MagicMock(), response=fail_response)
        fail_response.raise_for_status.side_effect = raise_500

        # Configure successful Mock Response
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "Finally Success"
        success_response.headers = {"content-type": "text/html"}
        success_response.url = httpx.URL("https://retry.com")
        success_response.raise_for_status.return_value = None # Success doesn't raise exception

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # Simulate: First 500, Second 500, Third 200
            mock_get.side_effect = [fail_response, fail_response, success_response]
            
            config = OrgaConfig() 
            # Override retry wait time to speed up tests
            # But tenacity's wait is a decorator parameter, hard to change dynamically without refactoring fetcher.
            # Given the test environment, we'll tolerate a few seconds of delay.
            fetcher = HttpxFetcher(config)
            
            doc = await fetcher.fetch("https://retry.com")
            
            assert doc.status_code == 200
            assert doc.content == "Finally Success"
            assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_non_html_content_warning(self):
        """
        Test fetching non-HTML content (like PDF), which should produce a Warning and not be processed as normal HTML.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"%PDF-1.4..."
        mock_response.text = "%PDF-1.4..." 
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.url = httpx.URL("https://example.com/file.pdf")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            fetcher = HttpxFetcher(OrgaConfig())
            doc = await fetcher.fetch("https://example.com/file.pdf")
            
            assert doc.content_type == "application/pdf"
            assert any(w.code == "NON_HTML_CONTENT" for w in doc.fetch_warnings)
