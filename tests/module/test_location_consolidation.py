import pytest

from orga.merge.processor import ProfilePostProcessor
from orga.model import Address, Evidence, Location


class TestLocationConsolidation:
    """
    Tests for advanced location deduplication and consolidation.
    Focuses on merging 'approximate' addresses into single canonical entities.
    """

    @pytest.fixture
    def processor(self):
        return ProfilePostProcessor()

    def test_fingerprint_deduplication_exact_match(self, processor):
        """
        Scenario: Exact string match (normalized) should merge.
        """
        locs = [
            Location(address=Address(raw="123 Main St, London"), confidence=0.8),
            Location(address=Address(raw="123 Main St, London "), confidence=0.7)
        ]
        merged = processor._process_locations(locs)
        assert len(merged) == 1
        assert merged[0].address.raw == "123 Main Street, London"

    def test_fingerprint_deduplication_postal_match(self, processor):
        """
        Scenario: Different raw strings but same Postal Code and Street Number.
        Should merge based on 'Fingerprint'.
        """
        locs = [
            Location(address=Address(raw="123 Main St, London, SW1A 1AA"), confidence=0.9),
            # Slightly different format, maybe missing city, but same zip + number
            Location(address=Address(raw="123 Main Street, SW1A 1AA"), confidence=0.7)
        ]
        # We need to ensure the processor logic implements this 'Fingerprint' logic
        merged = processor._process_locations(locs)
        
        assert len(merged) == 1
        # Should ideally keep the more complete one (longer raw?)
        assert "London" in merged[0].address.raw

    def test_fingerprint_deduplication_street_name_match(self, processor):
        """
        Scenario: Same street name and number, missing postal code.
        Should merge if street name is strong enough.
        """
        locs = [
            Location(address=Address(raw="10 Downing St"), confidence=0.8),
            Location(address=Address(raw="10 Downing Street"), confidence=0.8)
        ]
        merged = processor._process_locations(locs)
        assert len(merged) == 1

    def test_merge_evidence_accumulation(self, processor):
        """
        Scenario: Merging should accumulate evidence count and boost confidence.
        """
        locs = [
            Location(address=Address(raw="HQ: 123 Test Rd"), evidence=[Evidence(source_type="p1", confidence_score=0.5)]),
            Location(address=Address(raw="123 Test Road"), evidence=[Evidence(source_type="p2", confidence_score=0.6)])
        ]
        merged = processor._process_locations(locs)
        
        assert len(merged) == 1
        assert len(merged[0].evidence) == 2
        # Merged confidence is weighted average (0.5 + 0.6) / 2 = 0.55
        assert merged[0].confidence == 0.55

class TestAddressStructuredParsing:
    """
    Tests for extracting structured fields (City, Zip) from raw strings.
    This logic might reside in AddressParser or a utility helper used by Parser/Merger.
    """
    
    def test_extract_postal_code_uk(self):
        # We'll test the parsing logic directly if possible, or via a dummy doc
        from orga.parse.fields.parsers import AddressParser
        parser = AddressParser()
        
        raw = "222 Balham High Road, London SW12 9BS"
        # Simulate internal method or parsing result
        parsed_addr = parser._structure_address(raw)
        
        assert parsed_addr.postal_code == "SW12 9BS"
        assert parsed_addr.city == "London"
        assert parsed_addr.street == "222 Balham High Road"

    def test_extract_postal_code_us(self):
        from orga.parse.fields.parsers import AddressParser
        parser = AddressParser()
        
        raw = "1600 Pennsylvania Ave NW, Washington, DC 20500"
        parsed_addr = parser._structure_address(raw)
        
        assert parsed_addr.postal_code == "20500"
        # Region/City extraction might be harder without NLP, but Zip is key
        assert parsed_addr.city == "Washington" # If heuristics work
