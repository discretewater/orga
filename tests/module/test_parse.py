from orga.model import ContactKind, Document
from orga.parse.fields import AddressParser, CategoryClassifier, ContactParser


class TestContactParser:
    """
    Test contact parser.
    """

    def test_extract_emails_complex(self):
        """
        Test complex Email extraction scenarios, including obfuscated Emails and multiple Emails.
        """
        content = """
        <div>
            Contact us: <a href="mailto:info@test.org">info@test.org</a>
            Support: support@test.org
            Abuse: abuse [at] test [dot] org (Anti-scraping pattern)
        </div>
        """
        doc = Document(url="https://test.org", content=content, content_type="text/html", status_code=200)
        
        parser = ContactParser()
        contacts = parser.parse(doc)
        emails = [c for c in contacts if c.kind == ContactKind.EMAIL]
        
        email_values = [e.value for e in emails]
        assert "info@test.org" in email_values
        assert "support@test.org" in email_values

    def test_extract_emails_noise_filtering(self):
        """
        Verify that noise like file extensions and placeholders are filtered out.
        """
        content = """
        <p>Contact: valid@test.org</p>
        <p>Noise: image@2x.png, script.js@2.0, sentry@o1.ingest.sentry.io</p>
        <p>Placeholder: user@example.com</p>
        """
        doc = Document(url="https://test.com", content=content)
        parser = ContactParser()
        contacts = parser.parse(doc)
        emails = [c.value for c in contacts if c.kind == ContactKind.EMAIL]
        
        assert "valid@test.org" in emails
        assert "image@2x.png" not in emails
        assert "script.js@2.0" not in emails
        # sentry and example.com are filtered
        assert not any("sentry" in e for e in emails)
        assert "user@example.com" not in emails

    def test_extract_social_links(self):
        """
        Test extracting social media links from footer or icons.
        """
        content = """
        <footer>
            <a href="https://twitter.com/OrgaProj">Twitter</a>
            <a href="https://www.linkedin.com/company/orga">LinkedIn</a>
            <a href="/internal-link">Internal</a>
        </footer>
        """
        doc = Document(url="https://test.org", content=content, content_type="text/html", status_code=200)
        
        parser = ContactParser()
        contacts = parser.parse(doc)
        socials = [c for c in contacts if c.kind == ContactKind.SOCIAL]
        
        assert len(socials) == 2
        assert any("twitter.com" in s.value for s in socials)
        assert any("linkedin.com" in s.value for s in socials)

    def test_extract_phones_strict_validation(self):
        """
        [New] Test strict phone number validation.
        Should exclude: dates, long numeric strings, invalid numbers.
        Should retain: valid format numbers.
        """
        content = """
        <body>
            <p>Valid Phone: 613-737-7600</p>
            <p>Another Valid: +1 (555) 010-9999</p>
            <p>Date (Should fail): 2026-02-24</p>
            <p>Long Number (Should fail): 00000000-0000-000</p>
            <p>Serial Number (Should fail): 15018176-5</p>
            <p>Short Code (Should fail): 911-9449-0050569</p>
            <a href="tel:+16137377600">Call Us</a>
        </body>
        """
        doc = Document(url="https://test.org", content=content, content_type="text/html", status_code=200)
        
        parser = ContactParser()
        contacts = parser.parse(doc)
        phones = [c for c in contacts if c.kind == ContactKind.PHONE]
        phone_values = [p.value for p in phones]

        # Verify positive cases
        assert any("613-737-7600" in v or "+16137377600" in v for v in phone_values)
        
        # Verify negative cases (should not include)
        assert "2026-02-24" not in phone_values
        assert "00000000-0000-000" not in phone_values
        assert "15018176-5" not in phone_values
        assert "911-9449-0050569" not in phone_values

    def test_phone_confidence_scoring(self):
        """
        [New] Test confidence scoring for phone numbers.
        tel links should have higher confidence than plain text regex.
        """
        content = """
        <a href="tel:+12024561414">Call High Confidence</a>
        <p>Call Low Confidence: +1-202-456-1111</p>
        """
        doc = Document(url="https://test.org", content=content, content_type="text/html", status_code=200)
    
        parser = ContactParser()
        contacts = parser.parse(doc)
        phones = [c for c in contacts if c.kind == ContactKind.PHONE]
    
        tel_phone = next((p for p in phones if "+12024561414" in p.value), None)
        text_phone = next((p for p in phones if "+12024561111" in p.value), None)
        assert tel_phone is not None
        assert text_phone is not None
        # Verify confidence difference
        assert tel_phone.confidence > text_phone.confidence
        assert tel_phone.confidence >= 0.8 # Assuming high confidence threshold
        assert text_phone.confidence < 0.8

class TestAddressParser:
    """
    Test address parser.
    """

    def test_extract_address_from_schema_org(self):
        """
        Test extracting address from JSON-LD (Schema.org).
        """
        content = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "Schema Org Test",
          "address": {
            "@type": "PostalAddress",
            "streetAddress": "123 Schema St",
            "addressLocality": "Json City",
            "postalCode": "99999",
            "addressCountry": "US"
          }
        }
        </script>
        """
        doc = Document(url="https://schema.test", content=content, content_type="text/html", status_code=200)
        
        parser = AddressParser()
        locations = parser.parse(doc)
        
        assert len(locations) > 0
        addr = locations[0].address
        assert addr.street == "123 Schema St"
        assert addr.city == "Json City"
        assert addr.postal_code == "99999"
        assert addr.country == "US"

    def test_extract_address_regex_fallback(self):
        """
        Test extracting address based on regex or heuristic rules when no structured data is available.
        """
        content = """
        <footer>
            <p>Visit us at: 456 Regex Blvd, Pattern Town, PT 12345</p>
        </footer>
        """
        doc = Document(url="https://regex.test", content=content, content_type="text/html", status_code=200)
        
        parser = AddressParser()
        locations = parser.parse(doc)
        
        assert len(locations) > 0
        assert "456 Regex Blvd" in locations[0].address.raw

    def test_extract_address_from_footer_dom(self):
        """
        [New] Test extracting address from Footer or specific DOM areas.
        Prioritized over full-text scanning.
        """
        content = """
        <html>
        <body>
            <p>Some random text with numbers 12345.</p>
            <footer>
                <div class="contact-info">
                    <p>Our Office:</p>
                    <p>789 Footer Lane, Dom City, DC 54321</p>
                </div>
            </footer>
        </body>
        </html>
        """
        doc = Document(url="https://dom.test", content=content, content_type="text/html", status_code=200)
        
        parser = AddressParser()
        locations = parser.parse(doc)
        
        assert len(locations) > 0
        # Verify if the address in the Footer is extracted
        assert "789 Footer Lane" in locations[0].address.raw
        # Verify random numbers in the body should not be extracted (if regex is strict enough)
        address_texts = [l.address.raw for l in locations]
        assert not any("12345" in a and "Lane" not in a for a in address_texts)

class TestCategoryClassifier:
    """
    Test classifier.
    """
    
    def test_classify_by_keywords_baseline(self):
        """
        [New] Test keyword-based baseline classification.
        Should be able to identify common categories even without LLM.
        """
        content = """
        <title>Children's Hospital of Eastern Ontario</title>
        <h1>Welcome to CHEO</h1>
        <p>Providing pediatric healthcare and patient care.</p>
        """
        doc = Document(url="https://cheo.test", content=content, content_type="text/html", status_code=200)
        
        # Configure taxonomy
        taxonomy_config = {
            "Healthcare": ["hospital", "clinic", "healthcare", "patient"],
            "Education": ["university", "school", "college"]
        }
        classifier = CategoryClassifier(taxonomy=taxonomy_config)
        
        result = classifier.classify(doc)
        categories = result.categories
        assert "Healthcare" in categories
        assert "Education" not in categories
