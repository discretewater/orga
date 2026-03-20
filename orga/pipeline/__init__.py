from typing import List, Optional
import asyncio

from orga.model import Document, DocumentBundle, OrganizationProfile, OrgaConfig, Warning, WarningSeverity, Confidence
from orga.registry import registry

# Ensure strategies are registered by importing their modules
import orga.fetch.httpx_fetcher
import orga.discover
import orga.parse.fields.parsers
import orga.parse.fields.classifier
# Use absolute import to ensure registration
from orga.merge.processor import ProfilePostProcessor

class OrgaPipeline:
    """
    ORGA Core Pipeline.
    Orchestrates Fetch -> Discover -> Parse -> Merge -> Governance.
    Now fully dynamic and registry-driven.
    """
    
    # Input Quality Gate Patterns
    BLOCK_PATTERNS = [
        "Just a moment...", "Access Denied", "Challenge Validation", 
        "Verify you are human", "Attention Required! | Cloudflare", 
        "Please wait while we verify", "Checking your browser"
    ]
    
    def __init__(self, config: Optional[OrgaConfig] = None):
        self.config = config or OrgaConfig()
        
        # 1. Instantiate Fetcher from registry
        fetcher_cls = registry.get("fetcher", "httpx")
        self.fetcher = fetcher_cls(self.config)
        
        # 2. Instantiate Discoverer from registry
        discoverer_cls = registry.get("discoverer", self.config.discover.strategy)
        self.discoverer = discoverer_cls(
            max_pages=self.config.discover.max_discovered_pages
        )
        
        # 3. Instantiate Parsers from registry
        self.contact_parser = registry.get("parser", "contact")()
        self.address_parser = registry.get("parser", "address")()
        
        # Strategy switching logic (backward compatibility with tests)
        if "regex" not in self.config.parse.strategies:
            if hasattr(self.contact_parser, "_extract_emails"):
                self.contact_parser._extract_emails = lambda doc: []
            if hasattr(self.contact_parser, "_extract_phones"):
                self.contact_parser._extract_phones = lambda doc: []
        
        # 4. Instantiate Classifier from registry
        classifier_cls = registry.get("category_classifier", self.config.parse.category_strategy)
        self.classifier = classifier_cls(
            taxonomy=self.config.taxonomy,
            weights=self.config.weights.model_dump(),
            thresholds=self.config.parse.classification_thresholds.model_dump()
        )
        
        # 5. Instantiate Aggregator (M7.1)
        from orga.governance.classification_aggregator import ClassificationAggregator
        self.classification_aggregator = ClassificationAggregator()
        
        # 5. Instantiate Merger from registry
        merger_cls = registry.get("merger", self.config.merge.strategy)
        self.merger = merger_cls()

    async def run(self, documents: List[Document]) -> OrganizationProfile:
        """
        Process a list of documents and generate an Organization Profile.
        """
        profile = OrganizationProfile()
        
        # Input Quality Gate
        if not documents:
            return profile
            
        # Temp storage for classification results to be aggregated later
        page_classifications: List[Tuple[str, Any]] = []
            
        # Check entry document (usually the first one)
        entry_doc = documents[0]
        if self._is_blocked_page(entry_doc):
            profile.warnings.append(Warning(
                code="PAGE_BLOCKED",
                message=f"Access blocked/challenged for {entry_doc.url}",
                severity=WarningSeverity.ERROR
            ))
            return profile # Abort extraction
            
        if entry_doc.status_code == 403 or entry_doc.status_code == 401:
             profile.warnings.append(Warning(
                code="PAGE_ACCESS_DENIED",
                message=f"Access denied ({entry_doc.status_code}) for {entry_doc.url}",
                severity=WarningSeverity.ERROR
            ))
             # We might still try to extract from others, but usually this is fatal for the main profile
             # For now, let's continue but with a heavy warning, unless content is empty
             if not entry_doc.content or len(entry_doc.content) < 500:
                 return profile

        for doc in documents:
            # Extract contacts
            contacts = self.contact_parser.parse(doc)
            for c in contacts:
                if c.kind == "email":
                    profile.emails.append(c)
                elif c.kind == "phone":
                    profile.phones.append(c)
                elif c.kind == "social":
                    profile.social_links.append(c)
                profile.evidence.extend(c.evidence)
            
            # Extract addresses
            # AddressParser now returns List[Location] with evidence included
            locations = self.address_parser.parse(doc)
            profile.locations.extend(locations)
            for loc in locations:
                profile.evidence.extend(loc.evidence)
            
            # Extract categories (Updated to handle ClassificationResult)
            classification_result = self.classifier.classify(doc)
            page_classifications.append((doc.url, classification_result))
            
            # Populate debug info
            if classification_result.debug_info:
                if profile.debug_info is None:
                    profile.debug_info = {}
                # Merge or append debug info. Since we process multiple docs,
                # we might want to key it by doc url or merge candidates.
                # For MVP, we'll store the latest or a list.
                if "classification_debug" not in profile.debug_info:
                    profile.debug_info["classification_debug"] = []
                profile.debug_info["classification_debug"].append({
                    "url": doc.url,
                    "info": classification_result.debug_info
                })
                    
            # Extract Name (Heuristic: Title)
            if not profile.name:
                from selectolax.parser import HTMLParser
                tree = HTMLParser(doc.content)
                title = tree.css_first("title")
                if title:
                    profile.name = title.text(strip=True)

            profile.warnings.extend(doc.fetch_warnings)

        # Finalize Classification (Institution Level Aggregation)
        # Replaces old simple list extension
        final_categories = self.classification_aggregator.aggregate(page_classifications)
        profile.categories = final_categories
        
        # Infer org_type from primary category if available
        if final_categories:
            profile.org_type = final_categories[0]

        # Apply initial governance (placeholder warnings before merging)
        self._apply_initial_governance(profile)
        
        # Run Merger (Post-processing: Dedupe, Filter, Evidence Isolation)
        profile = self.merger.process(profile)

        return profile

    def _is_blocked_page(self, doc: Document) -> bool:
        try:
            # Defensive Programming: Handle any potential NoneType in fetch result
            if not doc or not doc.content: 
                return False
            
            # Force conversion to string and lower safely
            content_str = str(doc.content or "")
            content_sample = content_str[:2000].lower()
            
            # Check Title safely
            from selectolax.parser import HTMLParser
            tree = HTMLParser(doc.content)
            title = tree.css_first("title")
            
            # Extract title text, handle None, force string
            raw_title = title.text(strip=True) if title else ""
            title_text = str(raw_title or "").lower()
            
            for pattern in self.BLOCK_PATTERNS:
                p_lower = pattern.lower()
                if p_lower in title_text or p_lower in content_sample:
                    return True
            return False
            
        except Exception as e:
            # SAFETY NET: Never crash the pipeline for a blockage check
            print(f"[SYSTEM WARNING] _is_blocked_page check failed safely: {e}")
            return False

    def _apply_initial_governance(self, profile: OrganizationProfile):
        # Basic logical consistency checks before final scoring
        pass

    async def run_bundle(self, bundle: DocumentBundle) -> OrganizationProfile:
        return await self.run(bundle.documents)

    async def run_from_url(self, url: str) -> OrganizationProfile:
        """
        Run pipeline starting from a URL (Entry page).
        Fetcher handles internal concurrency limits.
        """
        entry_doc = await self.fetcher.fetch(url)
        
        # Pre-check entry doc before discovery
        if self._is_blocked_page(entry_doc) or entry_doc.status_code in [403, 401]:
             # Just run on this doc to trigger warnings and exit
             return await self.run([entry_doc])

        sub_urls = self.discoverer.discover(entry_doc)
        
        tasks = [self.fetcher.fetch(u) for u in sub_urls]
        discovered_docs = await asyncio.gather(*tasks)
        
        documents = [entry_doc] + list(discovered_docs)
        return await self.run(documents)
