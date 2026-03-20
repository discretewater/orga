import pytest
from orga.model import Document, Address
from orga.parse.fields.address_scorer import AddressScorer

class TestAddressScoring:
    """
    Tests for the AddressScorer mechanism.
    Verifies that candidates are scored based on structural and positional signals.
    """

    @pytest.fixture
    def scorer(self):
        return AddressScorer()

    def test_score_high_quality_address(self, scorer):
        """
        Scenario: A perfect address with street, postal code, in a footer.
        Expected: High score.
        """
        raw = "123 Main St, London SW1A 1AA"
        context = {"zone": "footer"}
        
        score, breakdown = scorer.calculate_score(raw, context)
        
        # Base(1) + Postal(2) + Street(1) + Zone(1) = 5.0
        assert score >= 4.0
        assert breakdown["has_postal"] > 0
        assert breakdown["has_street"] > 0
        assert breakdown["zone_bonus"] > 0

    def test_score_low_quality_text(self, scorer):
        """
        Scenario: A sentence that looks slightly like an address but is noise.
        Expected: Low or negative score due to penalties.
        """
        raw = "We are located near the Main St subway station check it out."
        context = {"zone": "body"}
        
        score, breakdown = scorer.calculate_score(raw, context)
        
        # Base(1) + Street(1) - Length/Verb penalty?
        # Should be significantly lower than the high quality one.
        assert score < 3.0
        # If we implement verb/length penalty
        if "penalty_length" in breakdown:
            assert breakdown["penalty_length"] < 0

    def test_score_navigation_noise(self, scorer):
        """
        Scenario: Navigation links mashed together.
        Expected: Low score due to nav keywords penalty.
        """
        raw = "Home About Contact Us Map Directions"
        context = {"zone": "header"}
        
        score, breakdown = scorer.calculate_score(raw, context)
        
        # Base(1) - NavPenalty
        assert score < 1.5
        assert breakdown.get("penalty_nav", 0) < 0

    def test_score_partial_address(self, scorer):
        """
        Scenario: Street only, no postal code.
        Expected: Medium score (acceptable but lower than full).
        """
        raw = "10 Downing Street"
        context = {"zone": "body"}
        
        score, breakdown = scorer.calculate_score(raw, context)
        
        # Base(1) + Street(1) = 2.0. No postal bonus.
        assert 1.5 <= score < 4.0
        assert breakdown.get("has_postal", 0) == 0

    def test_score_normalization_impact(self, scorer):
        """
        Scenario: Ensure scoring works on raw strings (robustness).
        """
        raw = "  123   Main   St.  "
        context = {}
        score, _ = scorer.calculate_score(raw, context)
        assert score >= 2.0 # Base + Street
