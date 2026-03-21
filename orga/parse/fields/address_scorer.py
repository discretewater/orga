import re
from typing import Any


class AddressScorer:
    """
    Evaluates the quality of an address candidate based on structural and positional signals.
    """
    
    # Shared regex patterns (can be moved to constants later)
    POSTAL_US = r'\b\d{5}(?:-\d{4})?\b'
    POSTAL_UK = r'\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b'
    POSTAL_CA = r'\b[A-Z]\d[A-Z] ?\d[A-Z]\d\b'
    
    STREET_TYPES = r'(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Plaza|Square|Sq|Court|Ct|Circle|Cir|Highway|Hwy|House|Building)'
    
    NAV_KEYWORDS = ["Home", "Menu", "About", "Contact", "Map", "Directions", "Search", "Login", "Sign Up"]
    
    def __init__(self):
        self.postal_regex = re.compile(f'(?:{self.POSTAL_US}|{self.POSTAL_UK}|{self.POSTAL_CA})', re.IGNORECASE)
        self.street_regex = re.compile(r'\d+\s+[\w\s,.-]+' + self.STREET_TYPES, re.IGNORECASE)

    def calculate_score(self, raw_text: str, context: dict[str, Any]) -> tuple[float, dict[str, float]]:
        """
        Calculate score for a raw address candidate.
        Returns (score, breakdown_dict).
        """
        score = 1.0 # Base score
        breakdown = {"base": 1.0}
        
        # 1. Structural Bonuses
        if self.postal_regex.search(raw_text):
            bonus = 2.0
            score += bonus
            breakdown["has_postal"] = bonus
            
        if self.street_regex.search(raw_text):
            bonus = 1.0
            score += bonus
            breakdown["has_street"] = bonus
            
        # 2. Positional Bonuses
        zone = context.get("zone", "").lower()
        if zone in ["footer", ".footer", "#footer", ".contact", "#contact", "address"]:
            bonus = 1.0
            score += bonus
            breakdown["zone_bonus"] = bonus
            
        # 3. Penalties
        # Length Penalty
        if len(raw_text) > 100:
            penalty = -2.0
            score += penalty
            breakdown["penalty_length"] = penalty
            
        # Navigation Noise Penalty
        nav_count = 0
        for kw in self.NAV_KEYWORDS:
            if kw.lower() in raw_text.lower():
                nav_count += 1
        
        if nav_count > 0:
            penalty = -1.0 * min(nav_count, 3) # Cap at -3
            score += penalty
            breakdown["penalty_nav"] = penalty
            
        return max(0.0, score), breakdown
