import pytest

from orga.model import Document
from orga.parse.fields.classifier import (
    LayeredCategoryClassifier,
)


@pytest.fixture
def sample_taxonomy():
    return {
        "Healthcare": {
            "rules": {"title": ["hospital", "clinic"], "h1": ["patient"]},
            "bayes_features": {"medical": 0.9, "health": 0.7, "doctor": 0.8}
        },
        "Engineering": {
            "rules": {"title": ["engineering", "architect"], "h1": ["design"]},
            "bayes_features": {"building": 0.8, "hvac": 0.9, "construction": 0.7}
        }
    }

class TestLayeredCategoryClassifierAdvanced:
    """
    Tests for advanced Tier 2 logic: Margin checks and Minimum Score thresholds.
    """

    def test_tier2_margin_success(self, sample_taxonomy):
        """
        Scenario: Top-1 is weak (Tier 2) but significantly better than Top-2.
        Result: Should return Top-1 because Margin condition is met.
        """
        # "building" (0.8) vs nothing else. Top1=0.8, Top2=0.0. Gap=0.8 > Margin(0.1)
        content = "<html><body>building</body></html>"
        doc = Document(url="https://test.com", content=content)
        
        # Configure with low min_score to allow this weak signal
        classifier = LayeredCategoryClassifier(
            taxonomy=sample_taxonomy, 
            thresholds={"tier2_min_score": 0.5, "tier2_margin": 0.1}
        )
        
        result = classifier.classify(doc)
        assert result.categories == ["Engineering"]
        assert any("Tier 2 match found via Margin check" in msg for msg in result.debug_info["decision_path"])

    def test_tier2_margin_fail_ambiguity(self, sample_taxonomy):
        """
        Scenario: Top-1 and Top-2 are both weak and very close.
        Result: Should return Empty because it's ambiguous.
        """
        # "medical" (0.9) vs "hvac" (0.9). Gap=0.0 < Margin(0.1)
        content = "<html><body>medical hvac</body></html>"
        doc = Document(url="https://test.com", content=content)
        
        classifier = LayeredCategoryClassifier(
            taxonomy=sample_taxonomy, 
            thresholds={"tier2_min_score": 0.5, "tier2_margin": 0.2} # Strict margin
        )
        
        result = classifier.classify(doc)
        assert result.categories == []
        assert "Ambiguous result" in str(result.debug_info["decision_path"])

    def test_tier2_min_score_fail(self, sample_taxonomy):
        """
        Scenario: Top-1 exists but is too weak (below min_score).
        Result: Should return Empty.
        """
        # "health" (0.7) vs nothing.
        content = "<html><body>health</body></html>"
        doc = Document(url="https://test.com", content=content)
        
        # High min_score required
        classifier = LayeredCategoryClassifier(
            taxonomy=sample_taxonomy, 
            thresholds={"tier2_min_score": 5.0} 
        )
        
        result = classifier.classify(doc)
        assert result.categories == []
        assert "below min_score" in str(result.debug_info["decision_path"])

    def test_tier1_bypass_margin(self, sample_taxonomy):
        """
        Scenario: Tier 1 (Rules) finds a match.
        Result: Should ignore Tier 2 margin logic and return immediately.
        """
        content = "<html><title>Hospital</title><body>hvac</body></html>"
        doc = Document(url="https://test.com", content=content)
        
        classifier = LayeredCategoryClassifier(taxonomy=sample_taxonomy)
        result = classifier.classify(doc)
        
        assert result.categories == ["Healthcare"]
        assert "Tier 1 (Rules) match found" in result.debug_info["decision_path"][0]
