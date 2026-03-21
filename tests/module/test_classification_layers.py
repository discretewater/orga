import pytest

from orga.model import Document
from orga.parse.fields.classifier import (
    BayesianClassifier,
    LayeredCategoryClassifier,
    RuleBasedClassifier,
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

class TestRuleBasedClassifier:
    """
    Tests for Tier 1: Rule-Based Classification.
    """
    def test_strong_title_match(self, sample_taxonomy):
        content = "<html><head><title>Central Hospital Center</title></head><body></body></html>"
        doc = Document(url="https://test.com", content=content)
        classifier = RuleBasedClassifier(taxonomy=sample_taxonomy)
        
        result = classifier.classify(doc)
        categories = result.categories
        assert "Healthcare" in categories
        assert len(categories) == 1

    def test_multiple_rule_matches(self, sample_taxonomy):
        content = "<html><head><title>Engineering & Design Clinic</title></head><body></body></html>"
        doc = Document(url="https://test.com", content=content)
        classifier = RuleBasedClassifier(taxonomy=sample_taxonomy)
        
        result = classifier.classify(doc)
        categories = result.categories
        # Should catch both if thresholds are met
        assert "Engineering" in categories
        assert "Healthcare" in categories

class TestBayesianClassifier:
    """
    Tests for Tier 2: Bayesian Statistical Classification.
    """
    def test_statistical_frequency_match(self, sample_taxonomy):
        # Body text contains many Engineering features but Title doesn't match rules
        content = """
        <html>
            <body>
                <p>We work in building construction and hvac systems. 
                Our construction methods are modern. Building building building.</p>
            </body>
        </html>
        """
        doc = Document(url="https://test.com", content=content)
        classifier = BayesianClassifier(taxonomy=sample_taxonomy)
        
        result = classifier.classify(doc)
        categories = result.categories
        assert "Engineering" in categories
        assert "Healthcare" not in categories

class TestLayeredCategoryClassifier:
    """
    Tests for the Orchestrator (Tier 1 -> Tier 2).
    """
    def test_rule_skips_bayes_on_high_confidence(self, sample_taxonomy, mocker):
        # Mock Bayes to track if it's called
        spy = mocker.spy(BayesianClassifier, 'classify')
        
        content = "<html><head><title>The Great Hospital</title></head><body></body></html>"
        doc = Document(url="https://test.com", content=content)
        
        orchestrator = LayeredCategoryClassifier(taxonomy=sample_taxonomy)
        result = orchestrator.classify(doc)
        categories = result.categories
        
        assert "Healthcare" in categories
        # Bayes should NOT have been called because Title rule was high confidence
        assert spy.call_count == 0

    def test_bayes_fallback_on_weak_rules(self, sample_taxonomy, mocker):
        # No match in Title/H1, but Body matches Bayes features
        content = "<html><body>We provide medical and health services.</body></html>"
        doc = Document(url="https://test.com", content=content)
        
        # Set low min_score to allow weak bayes signal
        orchestrator = LayeredCategoryClassifier(taxonomy=sample_taxonomy, thresholds={"tier2_min_score": 0.1})
        result = orchestrator.classify(doc)
        categories = result.categories
        
        assert "Healthcare" in categories

    def test_conflict_resolution_rule_wins(self, sample_taxonomy):
        # Title says Engineering (Rule), Body says Medical (Bayes)
        content = """
        <html>
            <head><title>Structural Engineering Inc</title></head>
            <body>medical medical medical health health</body>
        </html>
        """
        doc = Document(url="https://test.com", content=content)
        
        orchestrator = LayeredCategoryClassifier(taxonomy=sample_taxonomy)
        result = orchestrator.classify(doc)
        categories = result.categories
        
        # Rule (Engineering) should prevail or be primary
        assert categories[0] == "Engineering"

    def test_conservative_top_1_policy(self, sample_taxonomy):
        # Multiple matches, but policy is Top-1
        content = "<html><head><title>Hospital Engineering Dept</title></head><body></body></html>"
        doc = Document(url="https://test.com", content=content)
        
        orchestrator = LayeredCategoryClassifier(taxonomy=sample_taxonomy, thresholds={"top_k": 1})
        result = orchestrator.classify(doc)
        
        assert len(result.categories) == 1
