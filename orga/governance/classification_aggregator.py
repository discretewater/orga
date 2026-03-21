from collections import defaultdict
from urllib.parse import urlparse

from orga.parse.fields.classifier import ClassificationResult


class ClassificationAggregator:
    """
    M7.1 Core Component: Institution-Level Classification Aggregator.
    Responsible for consolidating page-level classification results into a coherent
    institution profile using page weights, signal suppression, and thresholding.
    """

    # Page Weights configuration
    PAGE_WEIGHTS = {
        "high": 1.0,
        "medium": 0.6,
        "low": 0.2
    }

    # Category Suppression Rules
    # If key is Primary (high confidence), suppress values in list if they are Secondary (lower confidence)
    SUPPRESSION_RULES = {
        "Hospital": ["University", "Association", "NonProfit", "InternationalOrg"],
        "University": ["Hospital", "NonProfit", "Association"], 
        "Government": ["Association", "NonProfit", "InternationalOrg"],
        "InternationalOrg": ["Hospital", "University", "Association"],
        # Association and NonProfit are often legitimate secondary traits, so we suppress less aggressively
        "Association": [], 
        "NonProfit": [] 
    }

    # Minimum score to be considered a Primary candidate after aggregation
    PRIMARY_THRESHOLD = 3.0 

    def aggregate(self, results: list[tuple[str, ClassificationResult]]) -> list[str]:
        """
        Aggregates classification results from multiple pages.
        Args:
            results: List of (url, result) tuples.
        Returns:
            Final list of categories (ordered by confidence).
        """
        if not results:
            return []

        # 1. Weighted Scoring
        category_scores = defaultdict(float)
        
        for url, result in results:
            weight = self._get_page_weight(url)
            
            # Extract candidates and scores from debug info if available
            # We need the RAW scores, not just the filtered categories.
            # Currently ClassificationResult puts candidates in debug_info["final_candidates"]
            # Structure: {"Category": {"score": float, ...}}
            
            candidates = result.debug_info.get("final_candidates", {})
            if not candidates:
                # If tier 1 failed, maybe check tier 2 candidates?
                # For now, let's assume valid candidates are in final_candidates
                pass
                
            for cat, details in candidates.items():
                raw_score = details.get("score", 0.0)
                weighted_score = raw_score * weight
                category_scores[cat] += weighted_score

        # 2. Ranking and Selection
        sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        
        if not sorted_cats:
            return []

        # 3. Suppression Logic
        final_categories = []
        primary_cat, primary_score = sorted_cats[0]
        
        # Must meet global threshold to be Primary
        if primary_score < self.PRIMARY_THRESHOLD:
            # If even top score is low, maybe return nothing or handle conservatively
            # For now, we return empty to avoid "Low Confidence" output being noise
            return []

        final_categories.append(primary_cat)
        
        # Check secondary candidates
        for cat, score in sorted_cats[1:]:
            # Rule 1: Suppression Matrix
            if cat in self.SUPPRESSION_RULES.get(primary_cat, []):
                # If score gap is huge, suppress. 
                # E.g. Hospital=50, University=5 -> Suppress
                # E.g. Hospital=50, University=40 -> Keep (Teaching Hospital)
                ratio = score / primary_score
                if ratio < 0.6: # If secondary is less than 60% of primary strength, suppress it
                    continue
            
            # Rule 2: Absolute Threshold
            if score < self.PRIMARY_THRESHOLD * 0.5:
                continue
                
            final_categories.append(cat)
            
        return final_categories[:2] # Cap at 2 categories max

    def _get_page_weight(self, url: str) -> float:
        """
        Determines page weight based on URL patterns.
        """
        try:
            parsed = urlparse(url.lower())
            path = parsed.path
            
            # High Value
            if any(x in path for x in ["about", "contact", "mission", "who-we-are", "organization", "overview"]):
                return self.PAGE_WEIGHTS["high"]
            
            # Low Value (Noise)
            if any(x in path for x in ["news", "event", "article", "blog", "press", "media", "member", "donate", "campaign"]):
                return self.PAGE_WEIGHTS["low"]
                
            # Root page is High Value
            if path in ["", "/", "/index.html", "/index.aspx", "/home"]:
                return self.PAGE_WEIGHTS["high"]
                
            # Default Medium
            return self.PAGE_WEIGHTS["medium"]
        except:
            return self.PAGE_WEIGHTS["medium"]
