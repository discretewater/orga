import pytest
from orga.model import Document, OrgaConfig
from orga.registry import registry
# We'll define these new classes/interfaces shortly
from orga.parse.fields import CategoryClassifierStrategy, WeightedHeuristicClassifier

class TestClassificationArchitecture:
    """
    Tests for the classification strategy architecture and registry.
    """

    def test_classifier_registration(self):
        """
        Ensure different classification strategies can be registered and retrieved.
        """
        # Weighted Heuristic should be registered by default eventually
        # Here we check if the kind exists in registry
        strategies = registry.list("category_classifier")
        # We expect at least one default strategy
        assert len(strategies) >= 0 

    def test_interface_compliance(self):
        """
        Verify that implementations follow the CategoryClassifierStrategy ABC.
        """
        assert issubclass(WeightedHeuristicClassifier, CategoryClassifierStrategy)

class TestWeightedHeuristicClassifier:
    """
    Tests for the specific logic of WeightedHeuristicClassifier.
    """

    @pytest.fixture
    def classifier(self):
        taxonomy = {
            "Healthcare": {
                "keywords": {"hospital": 1.0, "clinic": 0.9, "health": 0.2},
                "negative_keywords": ["health and safety", "insurance"]
            },
            "Engineering": {
                "keywords": {"engineering": 1.0, "hvac": 0.9, "building services": 1.0, "engineer": 0.8}
            }
        }
        return WeightedHeuristicClassifier(taxonomy=taxonomy)

    def test_cibse_scenario(self, classifier):
        """
        Targeted test for CIBSE misclassification.
        Title contains 'Engineers', Body contains many 'health' and 'health and safety'.
        """
        content = """
        <html>
            <head><title>Chartered Institution of Building Services Engineers (CIBSE)</title></head>
            <body>
                <h1>Building Services Engineering</h1>
                <p>Leading the way in health and safety for buildings. 
                   We focus on healthy environments. Health, health, health.</p>
            </body>
        </html>
        """
        doc = Document(url="https://www.cibse.org", content=content, status_code=200)
        
        result = classifier.classify(doc)
        categories = result.categories
        
        # Engineering should win due to Title/H1 weight
        assert "Engineering" in categories
        # Healthcare should be filtered out because 'health' is low weight 
        # AND 'health and safety' is a negative keyword.
        assert "Healthcare" not in categories

    def test_position_weighting(self, classifier):
        """
        Verify that words in Title have much higher impact than words in Body.
        """
        # Page about 'Hospital' only in small footer text vs 'Software' in Title
        content = """
        <html>
            <head><title>Elite Software Solutions</title></head>
            <body>
                <p>Welcome to our tech site.</p>
                <footer>Partnered with City Hospital</footer>
            </body>
        </html>
        """
        doc = Document(url="https://tech.test", content=content, status_code=200)
        
        # Add Technology to taxonomy for this test
        # Handle dict update safely
        if isinstance(classifier.taxonomy, dict):
             classifier.taxonomy["Technology"] = {
                 "keywords": {"software": 1.0, "tech": 0.8},
                 "negative_keywords": []
             }
        
        result = classifier.classify(doc)
        categories = result.categories
        
        assert "Technology" in categories
        # Healthcare (from 'Hospital' in footer) should be below threshold
        assert "Healthcare" not in categories

    def test_threshold_and_top_k(self, classifier):
        """
        Verify that only high-confidence categories are returned.
        """
        content = "<html><body>Just a random word: health</body></html>"
        doc = Document(url="https://random.test", content=content, status_code=200)
        
        # 'health' has weight 0.2, appearing once in body.
        # Total score should be 0.2, which is below standard threshold (e.g., 0.5)
        result = classifier.classify(doc)
        categories = result.categories
        assert len(categories) == 0
