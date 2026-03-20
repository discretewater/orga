import pytest
from orga.model import (
    OrganizationProfile, Location, Address, Contact, 
    ContactKind, Evidence, Warning, WarningSeverity
)
from orga.governance import ScoringEngine, WarningRegistry

class TestScoringEngine:
    """
    Test suite for the mathematical scoring engine.
    """

    @pytest.fixture
    def engine(self):
        return ScoringEngine()

    def test_field_scoring_weighted_average(self, engine):
        """
        Verify field-level scoring using the LaTeX formula:
        score = sum(w_i * r_i) / sum(w_i)
        """
        # Scenario: Two pieces of evidence
        # 1. JSON-LD (Weight 1.0, Reliability 1.0)
        # 2. Regex (Weight 0.5, Reliability 0.6)
        ev1 = Evidence(source_type="jsonld_address", confidence_score=1.0) # r_i = 1.0
        ev2 = Evidence(source_type="regex_text_validated", confidence_score=0.6) # r_i = 0.6
        
        # Expected: (1.0 * 1.0 + 0.5 * 0.6) / (1.0 + 0.5) = 1.3 / 1.5 = 0.866...
        score = engine.calculate_field_score([ev1, ev2])
        assert pytest.approx(score, 0.01) == 0.87

    def test_profile_scoring_with_penalty(self, engine):
        """
        Verify profile-level scoring with completeness penalty.
        score_profile = (sum(alpha_f * score_f)) * beta_completeness
        """
        profile = OrganizationProfile(
            name="Test Org",
            locations=[Location(address=Address(raw="123 Main St"), confidence=0.9)],
            phones=[], # Missing contact info
            schema_version="0.1.2"
        )
        # Assume alpha_name = 0.4, alpha_location = 0.6, alpha_contact = 0.0 (if missing)
        # Completeness penalty: 0.8 if no contacts
        score = engine.calculate_profile_score(profile)
        
        # Exact numbers depend on implementation, but it should be less than 0.9
        assert 0.0 < score < 0.9

class TestWarningRegistry:
    """
    Test suite for standardized warning code generation.
    """

    @pytest.fixture
    def registry(self):
        return WarningRegistry()

    def test_no_contact_found_trigger(self, registry):
        """
        Verify that NO_CONTACT_FOUND is triggered when all contact fields are empty.
        """
        profile = OrganizationProfile(name="Empty Contacts")
        warnings = registry.scan_for_warnings(profile)
        
        codes = [w.code for w in warnings]
        assert "NO_CONTACT_FOUND" in codes
        # Check severity from design doc
        w = next(warn for warn in warnings if warn.code == "NO_CONTACT_FOUND")
        assert w.severity == WarningSeverity.WARNING

    def test_address_partially_parsed_trigger(self, registry):
        """
        Verify that ADDRESS_PARTIALLY_PARSED is triggered when only raw address is present.
        """
        loc = Location(address=Address(raw="Some Raw Address"))
        profile = OrganizationProfile(locations=[loc])
        
        warnings = registry.scan_for_warnings(profile)
        codes = [w.code for w in warnings]
        assert "ADDRESS_PARTIALLY_PARSED" in codes

    def test_empty_profile_trigger(self, registry):
        """
        Verify that EMPTY_PROFILE is triggered when absolutely nothing is found.
        """
        profile = OrganizationProfile()
        warnings = registry.scan_for_warnings(profile)
        codes = [w.code for w in warnings]
        assert "EMPTY_PROFILE" in codes
