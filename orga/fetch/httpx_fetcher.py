import asyncio

import httpx
import tenacity
from aiolimiter import AsyncLimiter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from orga.model import Document, OrgaConfig, SourceKind, Warning, WarningSeverity
from orga.registry import registry


class FetchError(Exception):
    """Custom exception for fetch operations."""
    pass

class HttpxFetcher:
    """
    Default fetch strategy using HTTPX.
    Implements retries, timeout control, concurrency limits, and rate limiting.
    """
    
    def __init__(self, config: OrgaConfig):
        self.config = config.fetch
        
        # Initialize concurrency control per fetcher instance
        # We avoid static caching based on id(config) to prevent test flakiness due to memory address reuse
        self._semaphore = asyncio.Semaphore(self.config.concurrency)
        # Default rate limit: 10 requests per second (conservative default)
        self._limiter = AsyncLimiter(10, 1)

    async def fetch(self, url: str) -> Document:
        """
        Fetch a single URL asynchronously with concurrency and rate limit control.
        """
        headers = {"User-Agent": self.config.user_agent}
        
        # Apply rate limiting and concurrency control
        async with self._limiter:
            async with self._semaphore:
                try:
                    return await self._fetch_with_retry(url, headers)
                except tenacity.RetryError as e:
                    last_exception = e.last_attempt.exception()
                    message = f"Connection timed out (Max retries reached): {last_exception!s}"
                    return self._create_error_document(url, "FETCH_TIMEOUT", message, WarningSeverity.ERROR)
                except httpx.TimeoutException:
                     return self._create_error_document(url, "FETCH_TIMEOUT", "Connection timed out", WarningSeverity.ERROR)
                except Exception as e:
                     return self._create_error_document(url, "FETCH_ERROR", str(e), WarningSeverity.ERROR)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.HTTPStatusError))
    )
    async def _fetch_with_retry(self, url: str, headers: dict[str, str]) -> Document:
        # Note: AsyncClient is instantiated inside the retry block to ensure fresh connection pool if needed,
        # but for high performance we might want to share one client. 
        # Design Doc 7.2 suggests default fetcher should be a 'convenience layer'.
        async with httpx.AsyncClient(timeout=self.config.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            
            # Retry on 5xx errors
            if response.status_code >= 500:
                response.raise_for_status()
            
            # Handle 404 gracefully without retry
            if response.status_code == 404:
                return self._create_document_from_response(response, warnings=[
                    Warning(code="HTTP_404", message="Page not found", severity=WarningSeverity.WARNING)
                ])
            
            # Check for non-HTML content
            content_type = response.headers.get("content-type", "").lower()
            warnings = []
            if "text/html" not in content_type:
                 warnings.append(Warning(
                     code="NON_HTML_CONTENT", 
                     message=f"Content-Type is {content_type}, expected text/html", 
                     severity=WarningSeverity.WARNING
                 ))

            return self._create_document_from_response(response, warnings=warnings)

    def _create_document_from_response(self, response: httpx.Response, warnings: list[Warning] = None) -> Document:
        return Document(
            url=str(response.url),
            content=response.text,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            status_code=response.status_code,
            headers_summary={k: v for k, v in response.headers.items() if k.lower() in ["content-type", "server", "date"]},
            fetch_warnings=warnings or [],
            source_kind=SourceKind.HTTP_FETCH
        )

    def _create_error_document(self, url: str, code: str, message: str, severity: WarningSeverity) -> Document:
        return Document(
            url=url,
            content="[FETCH FAILED]", 
            status_code=0,
            fetch_warnings=[
                Warning(code=code, message=message, severity=severity, source_url=url)
            ],
            source_kind=SourceKind.HTTP_FETCH
        )

# Register strategy
registry.register("fetcher", "httpx", HttpxFetcher)
