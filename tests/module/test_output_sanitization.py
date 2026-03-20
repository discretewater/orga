import pytest
from orga.model import OrganizationProfile, Location, Address, Evidence
from orga.merge.processor import ProfilePostProcessor

class TestOutputSanitization:
    """
    Tests for the "Conservative Sanitization Layer" (M6.1).
    Ensures that obvious noise (ISO standards, UI text) is stripped before final output.
    """

    @pytest.fixture
    def processor(self):
        return ProfilePostProcessor()

    def test_reject_cibse_iso_pollution(self, processor):
        """
        Regression Test for CIBSE:
        Raw: ",, tel +44 (0) 20 8772 3649 or visit the, Certification website, Management Systems certification, : ISO 9001, 14001, 45001, 50001 – email"
        Postal Code: "14001" (False positive)
        
        Expected: This location should be REJECTED or heavily downgraded.
        """
        bad_address = Address(
            raw=",, tel +44 (0) 20 8772 3649 or visit the, Certification website, Management Systems certification, : ISO 9001, 14001, 45001, 50001 – email",
            postal_code="14001"
        )
        profile = OrganizationProfile(
            locations=[Location(address=bad_address, confidence=0.4)]
        )
        
        cleaned_profile = processor.process(profile)
        
        # Should be removed entirely due to "ISO" and "website" keywords
        assert len(cleaned_profile.locations) == 0

    def test_reject_ui_prefix_pollution(self, processor):
        """
        Regression Test for Farm & Food Care:
        Raw: "In the News, Contact us, 660 Speedvale Avenue W, Unit 302, Guelph, ON, N1K 1E5"
        
        Expected: The "In the News, Contact us," prefix should ideally be stripped, 
        OR if that's too hard for rule-based, the location might be kept but we test for future cleaning.
        For M6.1 conservative gate, we might accept it if it contains valid structure, 
        BUT we should definitely reject pure noise like "Contact Us".
        """
        # Case A: Pure Noise
        noise_addr = Address(raw="Contact us | In the News | Home")
        
        # Case B: Polluted Real Address
        # We might not be able to fix the prefix perfectly without NLP, 
        # but we must ensure we don't reject valid addresses just because of mild pollution.
        real_addr = Address(
            raw="In the News, Contact us, 660 Speedvale Avenue W, Unit 302, Guelph, ON, N1K 1E5",
            postal_code="N1K 1E5",
            street="660 Speedvale Avenue W"
        )
        
        profile = OrganizationProfile(
            locations=[
                Location(address=noise_addr, confidence=0.2),
                Location(address=real_addr, confidence=0.8)
            ]
        )
        
        cleaned = processor.process(profile)
        
        # Pure noise should be gone
        assert not any("Home" in l.address.raw for l in cleaned.locations)
        
        # Real address (even with pollution) should survive if it has strong signals (Postal)
        # We are testing "Conservative" rejection - don't kill valid data.
        assert len(cleaned.locations) >= 1
        assert "N1K 1E5" in cleaned.locations[0].address.postal_code

    def test_reject_iso_numbers_as_postal_codes(self, processor):
        """
        Specific check: 14001, 9001 should never be postal codes.
        """
        profile = OrganizationProfile(
            locations=[
                Location(address=Address(raw="ISO 9001 Certified", postal_code="9001"), confidence=0.5),
                Location(address=Address(raw="Standard 14001", postal_code="14001"), confidence=0.5),
                Location(address=Address(raw="123 Real St, 90210", postal_code="90210"), confidence=0.9)
            ]
        )
        
        cleaned = processor.process(profile)
        
        # 9001 and 14001 should be dropped
        codes = [l.address.postal_code for l in cleaned.locations]
        assert "9001" not in codes
        assert "14001" not in codes
        assert "90210" in codes

    def test_reject_keyword_spam(self, processor):
        """
        Reject locations containing 'visit our website', 'email us', 'click here'.
        """
        bad_locs = [
            "Visit our website for more info",
            "Email us at info@test.com",
            "Click here to map",
            "Subscribe to our newsletter"
        ]
        
        profile = OrganizationProfile(
            locations=[Location(address=Address(raw=txt), confidence=0.4) for txt in bad_locs]
        )
        
        cleaned = processor.process(profile)
        assert len(cleaned.locations) == 0
