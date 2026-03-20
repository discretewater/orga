import pytest
import httpx
from unittest.mock import MagicMock, patch, AsyncMock
from orga.fetch import HttpxFetcher
from orga.model import Document, OrgaConfig

class TestHttpxFetcher:
    """
    测试 HttpxFetcher 模块的行为，包括成功、重试、超时及错误处理。
    """

    @pytest.fixture
    def mock_client(self):
        """
        创建一个 Mock 的 httpx.AsyncClient。
        """
        with patch("httpx.AsyncClient") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """
        测试成功抓取页面，并验证返回的 Document 对象结构。
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Success</html>"
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.content = b"<html>Success</html>"
        mock_response.url = httpx.URL("https://example.com") # 模拟最终 URL

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
        测试 404 响应，应返回 Document 但标记状态码，并可能包含 warning。
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
        测试网络超时（TimeoutException），验证是否抛出自定义 FetchError 或返回带有错误信息的 Document。
        """
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
            fetcher = HttpxFetcher(OrgaConfig())
            doc = await fetcher.fetch("https://timeout.com")
            assert doc.status_code != 200
            # 检查消息中是否包含 timed out (忽略大小写)
            assert any("timed out" in w.message.lower() for w in doc.fetch_warnings)

    @pytest.mark.asyncio
    async def test_fetch_retry_logic(self):
        """
        测试重试逻辑（Retry）。
        模拟前两次失败（如 500 错误），第三次成功。
        """
        # 配置失败的 Mock Response
        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.text = "Server Error"
        # 关键：headers 必须是 dict 行为
        fail_response.headers = {"content-type": "text/html"}
        # 关键：raise_for_status 必须抛出异常
        def raise_500():
            raise httpx.HTTPStatusError("500 Error", request=MagicMock(), response=fail_response)
        fail_response.raise_for_status.side_effect = raise_500

        # 配置成功的 Mock Response
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "Finally Success"
        success_response.headers = {"content-type": "text/html"}
        success_response.url = httpx.URL("https://retry.com")
        success_response.raise_for_status.return_value = None # 成功不抛异常

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # 模拟：第一次 500，第二次 500，第三次 200
            mock_get.side_effect = [fail_response, fail_response, success_response]
            
            config = OrgaConfig() 
            # 覆盖 retry 等待时间以加速测试
            # 但 tenacity 的 wait 是装饰器参数，这里较难动态修改，除非重构 fetcher。
            # 鉴于测试环境，暂且忍受几秒延迟。
            fetcher = HttpxFetcher(config)
            
            doc = await fetcher.fetch("https://retry.com")
            
            assert doc.status_code == 200
            assert doc.content == "Finally Success"
            assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_non_html_content_warning(self):
        """
        测试获取到非 HTML 内容（如 PDF），应产生 Warning 且不应作为普通 HTML 处理。
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
