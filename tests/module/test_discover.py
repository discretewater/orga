import pytest
from orga.discover import HeuristicDiscoveryStrategy
from orga.model import Document

class TestHeuristicDiscoveryStrategy:
    """
    测试启发式页面发现策略。
    """

    def test_discover_basic_links(self):
        """
        测试从 HTML 内容中发现基本的“联系我们”和“关于我们”链接。
        """
        content = """
        <html>
            <body>
                <a href="/about-us">About Us</a>
                <a href="https://example.com/contact">Contact</a>
                <a href="https://other.com/external">External</a>
            </body>
        </html>
        """
        doc = Document(url="https://example.com", content=content, status_code=200)
        strategy = HeuristicDiscoveryStrategy()
        
        links = strategy.discover(doc)
        
        # 应包含站内链接
        assert "https://example.com/about-us" in links
        assert "https://example.com/contact" in links
        # 不应包含站外链接
        assert "https://other.com/external" not in links

    def test_discover_max_pages_limit(self):
        """
        测试发现的页面数量限制。
        """
        content = """
        <html>
            <body>
                <a href="/p1">P1</a>
                <a href="/p2">P2</a>
                <a href="/p3">P3</a>
                <a href="/contact">Contact</a>
            </body>
        </html>
        """
        doc = Document(url="https://example.com", content=content, status_code=200)
        # 设置最大页面数为 2
        strategy = HeuristicDiscoveryStrategy(max_pages=2)
        
        links = strategy.discover(doc)
        assert len(links) <= 2

    def test_discover_domain_restriction(self):
        """
        测试域名限制，确保只发现同一站点的链接。
        """
        content = """
        <html>
            <body>
                <a href="https://sub.example.com/page">Subdomain</a>
                <a href="/local">Local</a>
            </body>
        </html>
        """
        doc = Document(url="https://example.com", content=content, status_code=200)
        strategy = HeuristicDiscoveryStrategy()
        
        links = strategy.discover(doc)
        assert "https://example.com/local" in links
        # 默认情况下，子域名通常视为不同站点，除非另有配置
        assert "https://sub.example.com/page" not in links

    def test_discover_priority_keywords(self):
        """
        测试关键词优先级，应优先发现更有价值的页面（如 contact）。
        """
        content = """
        <html>
            <body>
                <a href="/random-page">Random</a>
                <a href="/contact-us">Contact Us</a>
                <a href="/about">About</a>
            </body>
        </html>
        """
        doc = Document(url="https://example.com", content=content, status_code=200)
        # 限制只取 1 个页面
        strategy = HeuristicDiscoveryStrategy(max_pages=1)
        
        links = strategy.discover(doc)
        # 理想情况下，contact 应该比 random 更有可能被选中
        assert "https://example.com/contact-us" in links

    def test_discover_deduplication(self):
        """
        测试重复链接去重。
        """
        content = """
        <html>
            <body>
                <a href="/about">About 1</a>
                <a href="about">About 2</a>
                <a href="https://example.com/about">About 3</a>
            </body>
        </html>
        """
        doc = Document(url="https://example.com", content=content, status_code=200)
        strategy = HeuristicDiscoveryStrategy()
        
        links = strategy.discover(doc)
        assert len(links) == 1
        assert links[0] == "https://example.com/about"
