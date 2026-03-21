from orga.discover import HeuristicDiscoveryStrategy
from orga.model import Document


class TestHeuristicDiscoveryStrategy:
    """
    Test heuristic page discovery strategy.
    """

    def test_discover_basic_links(self):
        """
        Test discovering basic "Contact Us" and "About Us" links from HTML content.
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
        
        # Should include internal links
        assert "https://example.com/about-us" in links
        assert "https://example.com/contact" in links
        # Should not include external links
        assert "https://other.com/external" not in links

    def test_discover_max_pages_limit(self):
        """
        Test the limit on the number of discovered pages.
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
        # Set max pages to 2
        strategy = HeuristicDiscoveryStrategy(max_pages=2)
        
        links = strategy.discover(doc)
        assert len(links) <= 2

    def test_discover_domain_restriction(self):
        """
        Test domain restriction to ensure only links from the same site are discovered.
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
        # By default, subdomains are usually considered different sites unless configured otherwise
        assert "https://sub.example.com/page" not in links

    def test_discover_priority_keywords(self):
        """
        Test keyword priority, more valuable pages (like contact) should be discovered first.
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
        # Limit to only 1 page
        strategy = HeuristicDiscoveryStrategy(max_pages=1)
        
        links = strategy.discover(doc)
        # Ideally, contact should be more likely to be selected than random
        assert "https://example.com/contact-us" in links

    def test_discover_deduplication(self):
        """
        Test duplicate link deduplication.
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
