from orga.model import Document
from orga.parse.fields.parsers import AddressParser


class TestAddressParserAdvanced:
    """
    Tests for advanced address parsing features:
    - Zone weighting
    - Termination signals
    - Generic pattern families
    - Multi-line aggregation
    """

    def test_termination_signals(self):
        """
        Verify that address extraction stops when encountering non-address signals
        like 'Tel:', 'Email:', 'Copyright'.
        """
        content = """
        <footer>
            <div class="address">
                123 Main Street,
                London, UK SW1A 1AA
                Tel: +44 20 7946 0123
                Email: info@example.com
            </div>
        </footer>
        """
        doc = Document(url="https://test.com", content=content)
        parser = AddressParser()
        locations = parser.parse(doc)
        
        assert len(locations) > 0
        raw = locations[0].address.raw
        assert "123 Main Street" in raw
        assert "SW1A 1AA" in raw
        # Should NOT contain the phone number or label
        assert "Tel:" not in raw
        assert "info@example.com" not in raw

    def test_zone_weighting_footer_priority(self):
        """
        Verify that addresses in footer/contact zones are prioritized over body text.
        (Note: AddressParser currently returns list, scoring happens later or order implies priority.
         Here we check if footer address is found and perhaps first).
        """
        content = """
        <html>
            <body>
                <p>We delivered to 500 random street yesterday.</p>
                <footer>
                    <p>Headquarters: 10 Downing St, London</p>
                </footer>
            </body>
        </html>
        """
        doc = Document(url="https://test.com", content=content)
        parser = AddressParser()
        locations = parser.parse(doc)
        
        # Should find the footer address
        assert any("10 Downing St" in l.address.raw for l in locations)
        # Ideally it should be the primary/first one or flagged with high confidence in evidence
        # For now, just ensuring it's extracted is key.

    def test_uk_postal_code_support(self):
        """
        Verify support for UK/Canada style alphanumeric postal codes.
        """
        content = "<footer>222 Balham High Rd, London SW12 9BS</footer>"
        doc = Document(url="https://test.com", content=content)
        parser = AddressParser()
        locations = parser.parse(doc)
        
        assert len(locations) > 0
        assert "SW12 9BS" in locations[0].address.raw

    def test_multi_line_aggregation(self):
        """
        Verify that address parts spanning multiple lines/tags are aggregated,
        but constrained to a single block.
        """
        content = """
        <div id="contact">
            <p>CIBSE</p>
            <p>222 Balham High Road</p>
            <p>London</p>
            <p>SW12 9BS</p>
        </div>
        """
        doc = Document(url="https://test.com", content=content)
        parser = AddressParser()
        locations = parser.parse(doc)
        
        assert len(locations) > 0
        # The raw string should ideally combine them
        combined = locations[0].address.raw.replace("\n", " ")
        assert "222 Balham High Road" in combined
        assert "London" in combined
        assert "SW12 9BS" in combined

    def test_abbreviation_support(self):
        """
        Verify extraction works with common abbreviations (Rd, St, Ave).
        """
        content = "<footer>123 Test Rd, Example St</footer>"
        doc = Document(url="https://test.com", content=content)
        parser = AddressParser()
        locations = parser.parse(doc)
        
        assert any("Test Rd" in l.address.raw for l in locations)
