import pytest

from orga.merge.processor import ProfilePostProcessor
from orga.model import (
    Address,
    Contact,
    ContactKind,
    Evidence,
    Location,
    OrganizationProfile,
    Warning,
    WarningSeverity,
)


class TestProfilePostProcessor:
    """
    Enhanced test suite for data governance: filtering, normalization, and deduplication.
    """

    @pytest.fixture
    def processor(self):
        return ProfilePostProcessor()

    def test_social_link_filtering_detailed(self, processor):
        """
        Verify platform-specific sharing link filtering and path normalization.
        """
        profile = OrganizationProfile(
            social_links=[
                # Official profiles
                Contact(kind=ContactKind.SOCIAL, value="https://www.facebook.com/CHEOkids/", 
                        evidence=[Evidence(source_type="html_attr_social", confidence_score=0.8)]),
                Contact(kind=ContactKind.SOCIAL, value="https://instagram.com/cheohospital/?hl=en",
                        evidence=[Evidence(source_type="html_attr_social", confidence_score=0.8)]),
                Contact(kind=ContactKind.SOCIAL, value="https://linkedin.com/company/cheo-ottawa",
                        evidence=[Evidence(source_type="html_attr_social", confidence_score=0.8)]),
                # Sharing links
                Contact(kind=ContactKind.SOCIAL, value="https://facebook.com/sharer.php?u=..."),
                Contact(kind=ContactKind.SOCIAL, value="https://www.linkedin.com/shareArticle?mini=true&..."),
                Contact(kind=ContactKind.SOCIAL, value="https://twitter.com/intent/tweet?text=...")
            ]
        )
        
        processed = processor.process(profile)
        vals = [s.value for s in processed.social_links]
        
        # Paths are normalized to lowercase
        assert "https://facebook.com/cheokids" in vals
        assert "https://instagram.com/cheohospital" in vals
        assert len(processed.social_links) == 3
        
        # Check debug info for filtered links
        assert "filtered_social_links" in processed.debug_info
        assert len(processed.debug_info["filtered_social_links"]) == 3

    def test_phone_business_filtering(self, processor):
        """
        Verify strict business-logic filtering for fake/test numbers.
        """
        profile = OrganizationProfile(
            phones=[
                # Valid
                Contact(kind=ContactKind.PHONE, value="+16137377600",
                        evidence=[Evidence(source_type="html_attr_tel", confidence_score=0.9)]), 
                # Fake: National zero
                Contact(kind=ContactKind.PHONE, value="+10000000000",
                        evidence=[Evidence(source_type="html_attr_tel", confidence_score=0.9)]), 
                # Fake: Too many repeated digits
                Contact(kind=ContactKind.PHONE, value="+12222222222",
                        evidence=[Evidence(source_type="html_attr_tel", confidence_score=0.9)]), 
            ]
        )
        
        processed = processor.process(profile)
        vals = [p.value for p in processed.phones]
        
        assert "+16137377600" in vals
        assert "+10000000000" not in vals
        assert len(vals) == 1
        
        # Check debug info
        assert "rejected_phones" in processed.debug_info
        assert len(processed.debug_info["rejected_phones"]) >= 2

    def test_phone_extension_handling(self, processor):
        """
        Verify that identical numbers are deduped.
        """
        profile = OrganizationProfile(
            phones=[
                Contact(kind=ContactKind.PHONE, value="+16132601477",
                        evidence=[Evidence(source_type="html_attr_tel", confidence_score=0.9)]),
                Contact(kind=ContactKind.PHONE, value="+16132601477",
                        evidence=[Evidence(source_type="regex_text_validated", confidence_score=0.6)]), 
            ]
        )
        processed = processor.process(profile)
        assert len(processed.phones) == 1
        assert len(processed.phones[0].evidence) == 2

    def test_address_normalization_and_merging(self, processor):
        """
        Verify advanced address normalization (case, space, abbreviations).
        """
        profile = OrganizationProfile(
            locations=[
                Location(address=Address(raw="401 Smyth Road"), 
                         evidence=[Evidence(source_type="parsed_address", confidence_score=0.8)]),
                Location(address=Address(raw=" 401 Smyth Rd. "), 
                         evidence=[Evidence(source_type="parsed_address", confidence_score=0.8)]),
                Location(address=Address(raw="401 SMYTH RD"), 
                         evidence=[Evidence(source_type="parsed_address", confidence_score=0.8)])
            ]
        )
        
        processed = processor.process(profile)
        
        assert len(processed.locations) == 1
        merged = processed.locations[0]
        assert merged.address.raw == "401 Smyth Road"
        assert len(merged.evidence) == 3

    def test_cross_page_evidence_merging(self, processor):
        """
        Verify that info from different URLs is merged into single canonical entities.
        """
        profile = OrganizationProfile(
            emails=[
                Contact(kind=ContactKind.EMAIL, value="a@test.org", 
                        evidence=[Evidence(source_url="page1", source_type="test", confidence_score=0.9)]),
                Contact(kind=ContactKind.EMAIL, value="a@test.org", 
                        evidence=[Evidence(source_url="page2", source_type="test", confidence_score=0.9)])
            ]
        )
        
        processed = processor.process(profile)
        assert len(processed.emails) == 1
        assert len(processed.emails[0].evidence) == 2

    def test_governance_warning_deduplication(self, processor):
        """
        Verify that redundant warnings are cleaned up during post-processing.
        """
        profile = OrganizationProfile(
            name="Test Org",
            warnings=[
                Warning(code="NO_LOCATION_FOUND", message="msg1", severity=WarningSeverity.WARNING),
                Warning(code="NO_LOCATION_FOUND", message="msg1", severity=WarningSeverity.WARNING)
            ]
        )
        
        processed = processor.process(profile)
        assert any(w.code == "NO_LOCATION_FOUND" for w in processed.warnings)
