from abc import ABC, abstractmethod
from typing import List, Set, Dict
from urllib.parse import urljoin, urlparse
from selectolax.parser import HTMLParser
import re
from orga.model import Document
from orga.registry import registry

class DiscoveryStrategy(ABC):
    """
    Base class for page discovery strategies.
    Used to discover more high-value links from an initial document.
    """
    @abstractmethod
    def discover(self, entry_doc: Document) -> List[str]:
        pass

class HeuristicDiscoveryStrategy(DiscoveryStrategy):
    """
    Heuristic-based page discovery strategy.
    Finds high-value links using keyword matching and domain filtering.
    """
    
    DEFAULT_KEYWORDS = {
        "contact": 10,
        "contact-us": 10,
        "about": 8,
        "about-us": 8,
        "location": 9,
        "locations": 9,
        "store": 7,
        "clinic": 7,
        "team": 5,
        "find-us": 9,
        "support": 6
    }

    def __init__(self, max_pages: int = 5, keywords: Dict[str, int] = None):
        self.max_pages = max_pages
        self.keywords = keywords or self.DEFAULT_KEYWORDS

    def discover(self, entry_doc: Document) -> List[str]:
        if not entry_doc.content:
            return []

        tree = HTMLParser(entry_doc.content)
        entry_url_parsed = urlparse(entry_doc.url)
        entry_domain = entry_url_parsed.netloc
        
        candidates = []
        seen_urls = {entry_doc.url.rstrip('/')}

        for node in tree.css("a[href]"):
            # href might be None if <a href> (boolean attribute style)
            href_val = node.attributes.get("href")
            href = (href_val or "").strip()
            
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            
            abs_url = urljoin(entry_doc.url, href)
            normalized_url = abs_url.rstrip('/')
            
            if normalized_url in seen_urls:
                continue
            
            parsed_candidate = urlparse(abs_url)
            if parsed_candidate.netloc != entry_domain:
                continue
            
            score = self._score_url(abs_url, node.text() or "")
            if score > 0:
                candidates.append((score, abs_url))
                seen_urls.add(normalized_url)

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [url for score, url in candidates[:self.max_pages]]

    def _score_url(self, url: str, link_text: str) -> int:
        score = 0
        path = urlparse(url).path.lower()
        link_text = link_text.lower()
        
        for kw, weight in self.keywords.items():
            if kw in path:
                score += weight
            if kw in link_text:
                score += weight
                
        if score == 0:
            score = 1
            
        return score

# Register strategy
registry.register("discoverer", "heuristic", HeuristicDiscoveryStrategy)
