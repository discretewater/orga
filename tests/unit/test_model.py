import pytest
from pydantic import ValidationError

from orga.model import (
    Address,
    Confidence,
    Contact,
    Document,
    DocumentBundle,
    Evidence,
    Location,
    OrganizationProfile,
    Warning,
    WarningSeverity,
)


class TestOrganizationProfile:
    """
    Test validation logic and field definitions of OrganizationProfile and its sub-models.
    """

    def test_profile_creation_minimal(self):
        """
        Test creating OrganizationProfile using only minimal required fields.
        Should ensure default fields (like list types) are correctly initialized as empty lists.
        """
        profile = OrganizationProfile(
            name="Test Org",
            schema_version="0.1.2"
        )
        assert profile.name == "Test Org"
        assert profile.locations == []
        assert profile.phones == []
        assert profile.emails == []
        assert profile.categories == []
        assert profile.warnings == []
        assert isinstance(profile.confidence, (Confidence, type(None))) # Allow empty or default object

    def test_profile_full_fields(self):
        """
        Test OrganizationProfile creation containing all fields, verifying the correctness of nested models.
        """
        profile = OrganizationProfile(
            name="Full Org",
            aliases=["FO", "Full Organization"],
            description="A test organization",
            locations=[
                Location(
                    label="HQ",
                    address=Address(raw="123 Main St", city="Metropolis"),
                    confidence=0.9,
                    evidence=[Evidence(source_url="http://test.com", source_type="html_text", snippet="123 Main St")]
                )
            ],
            phones=[
                Contact(kind="phone", value="+1234567890", label="Main")
            ],
            emails=[
                Contact(kind="email", value="info@full.org")
            ],
            social_links=[
                Contact(kind="social", value="https://twitter.com/fullorg")
            ],
            categories=["Technology", "Software"],
            keywords=["AI", "Parsing"],
            observed_at="2026-03-06T12:00:00Z",
            schema_version="0.1.2"
        )
        assert len(profile.aliases) == 2
        assert profile.locations[0].address.city == "Metropolis"
        assert profile.locations[0].evidence[0].source_type == "html_text"
        assert profile.phones[0].value == "+1234567890"
        assert "Technology" in profile.categories

class TestDocumentModels:
    """
    Test Document and DocumentBundle models.
    """

    def test_document_creation(self):
        """
        Test Document object creation and basic validation.
        """
        doc = Document(
            url="https://example.com/about",
            content="<html>About Us</html>",
            content_type="text/html",
            status_code=200,
            headers_summary={"content-type": "text/html"},
            source_kind="http_fetch"
        )
        assert doc.url == "https://example.com/about"
        assert doc.status_code == 200
        assert doc.source_kind == "http_fetch"
        assert len(doc.content) > 0

    def test_document_validation_error(self):
        """
        Test validation error when Document is missing required fields (like url or content).
        """
        with pytest.raises(ValidationError):
            Document(url="https://no-content.com") # Missing content

    def test_document_bundle_structure(self):
        """
        Test the structure of DocumentBundle, ensuring it can contain multiple Documents and identify the entry page.
        """
        entry_doc = Document(url="https://example.com", content="Index", content_type="text/html", status_code=200)
        contact_doc = Document(url="https://example.com/contact", content="Contact", content_type="text/html", status_code=200)
        
        bundle = DocumentBundle(
            entry_url="https://example.com",
            documents=[entry_doc, contact_doc],
            fetched_at="2026-03-06T12:00:00Z"
        )
        
        assert len(bundle.documents) == 2
        assert bundle.entry_url == "https://example.com"
        # Verify if the document can be found by URL (if the model supports this helper method, this is a reserved test here)
        # assert bundle.get_document("https://example.com/contact") == contact_doc

class TestGovernanceModels:
    """
    Test governance models like Evidence, Warning.
    """

    def test_evidence_structure(self):
        """
        Test field integrity of Evidence model.
        """
        ev = Evidence(
            source_url="https://example.com",
            source_type="meta_tag",
            snippet='<meta name="author" content="Orga">',
            extractor_name="MetaExtractor"
        )
        assert ev.source_type == "meta_tag"
        assert ev.snippet is not None

    def test_warning_severity(self):
        """
        Test Warning model and its Severity enum.
        """
        warn = Warning(
            code="FETCH_TIMEOUT",
            message="Connection timed out",
            severity=WarningSeverity.ERROR, # Assuming Enum is used
            related_field="locations"
        )
        assert warn.severity == WarningSeverity.ERROR
        assert warn.code == "FETCH_TIMEOUT"

class TestAddressModel:
    """
    Test Address model and its constraints.
    """
    
    def test_address_raw_retention(self):
        """
        Test Address model must retain the raw field, even if other fields fail to parse.
        """
        addr = Address(
            raw="123 Complex Road, Unit 456",
            street="123 Complex Road",
            unit="456"
        )
        assert addr.raw == "123 Complex Road, Unit 456"
        assert addr.street == "123 Complex Road"
        
        # Case with only raw
        addr_minimal = Address(raw="Unparseable String")
        assert addr_minimal.raw == "Unparseable String"
        assert addr_minimal.city is None
