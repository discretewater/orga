import pytest
from orga.model import Document, OrganizationProfile, Warning
from orga.pipeline import OrgaPipeline
from orga.model.config import OrgaConfig

class TestInputQualityGate:
    """
    Tests for Page-Level Gating (Interception of blocked/challenge pages).
    """

    @pytest.mark.asyncio
    async def test_cloudflare_challenge_interception(self):
        """
        Verify that a Cloudflare 'Just a moment...' page is blocked 
        and produces a specific warning, stopping extraction.
        """
        content = """
        <html>
            <head><title>Just a moment...</title></head>
            <body>
                <h1>Checking your browser before accessing...</h1>
                <p>Please wait while we verify you are human.</p>
            </body>
        </html>
        """
        doc = Document(url="https://blocked.test", content=content, status_code=403)
        pipeline = OrgaPipeline(OrgaConfig())
        
        profile = await pipeline.run([doc])
        
        # Should NOT have extracted garbage name
        assert "Just a moment" not in (profile.name or "")
        # Should have specific warning
        codes = [w.code for w in profile.warnings]
        assert "PAGE_CHALLENGE" in codes or "PAGE_BLOCKED" in codes
        # Should ideally be empty/minimal
        assert not profile.locations
        assert not profile.phones

    @pytest.mark.asyncio
    async def test_access_denied_interception(self):
        """
        Verify that 'Access Denied' pages are handled gracefully.
        """
        content = """
        <html><title>Access Denied</title><body><h1>Error 1020</h1></body></html>
        """
        doc = Document(url="https://denied.test", content=content, status_code=403)
        pipeline = OrgaPipeline(OrgaConfig())
        profile = await pipeline.run([doc])
        
        codes = [w.code for w in profile.warnings]
        assert "PAGE_ACCESS_DENIED" in codes or "PAGE_BLOCKED" in codes

class TestAddressHardening:
    """
    Tests for stricter address acceptance criteria (No DOI, No Policy text).
    """
    
    def test_reject_doi_and_policy_text(self):
        """
        Ensure academic citations (DOI) and policy statements are NOT extracted as addresses.
        """
        # Common false positive: "10.1016/j.energy.2020.117765" or "123 Policy Statement St."
        from orga.parse.fields.parsers import AddressParser
        
        content = """
        <footer>
            <p>Research supported by Grant No. 12345.</p>
            <p>DOI: 10.1016/j.energy.2020.117765</p>
            <p>See our Privacy Policy at 100 Policy St (Fake match).</p>
            <p>Real Address: 10 Downing St, London</p>
        </footer>
        """
        doc = Document(url="https://academic.test", content=content)
        parser = AddressParser()
        locations = parser.parse(doc)
        
        raws = [l.address.raw for l in locations]
        assert not any("10.1016" in r for r in raws)
        assert not any("Grant No" in r for r in raws)
        # Should still find the real one
        assert any("10 Downing St" in r for r in raws)

    def test_reject_navigation_noise(self):
        """
        Ensure navigation strings like "Home Contact About" are not aggregated into addresses.
        """
        from orga.parse.fields.parsers import AddressParser
        content = """
        <div class="footer">
            Home Contact Us About Map Directions
            123 Real Street
        </div>
        """
        doc = Document(url="https://nav.test", content=content)
        parser = AddressParser()
        locations = parser.parse(doc)
        
        raws = [l.address.raw for l in locations]
        # Should not contain "Home Contact Us"
        assert not any("Home Contact" in r for r in raws)

class TestPhoneHardening:
    """
    Tests for stricter phone validation (No DOI, No version numbers).
    """
    
    def test_reject_doi_and_versions(self):
        from orga.parse.fields.parsers import ContactParser
        from orga.model import ContactKind
        
        content = """
        <p>DOI: 10.1002/0471140864</p>
        <p>Version 12.3.4567</p>
        <p>Call: +1-202-456-1111</p>
        """
        doc = Document(url="https://noise.test", content=content)
        parser = ContactParser()
        contacts = parser.parse(doc)
        phones = [c.value for c in contacts if c.kind == ContactKind.PHONE]
        
        assert "+12024561111" in phones
        # DOI looks like a number but should be rejected
        assert not any("10.1002" in p for p in phones)
        assert not any("12.3.4567" in p for p in phones)

class TestSocialHardening:
    """
    Tests for stricter social link filtering (No watch/share/hashtag).
    """
    
    def test_reject_non_profile_paths(self):
        from orga.merge.processor import ProfilePostProcessor
        from orga.model import OrganizationProfile, Contact, ContactKind, Evidence
        
        processor = ProfilePostProcessor()
        profile = OrganizationProfile(
            social_links=[
                Contact(kind=ContactKind.SOCIAL, value="https://youtube.com/watch?v=123", evidence=[Evidence(source_type="test", confidence_score=0.9)]),
                Contact(kind=ContactKind.SOCIAL, value="https://instagram.com/p/12345", evidence=[Evidence(source_type="test", confidence_score=0.9)]),
                Contact(kind=ContactKind.SOCIAL, value="https://twitter.com/hashtag/News", evidence=[Evidence(source_type="test", confidence_score=0.9)]),
                Contact(kind=ContactKind.SOCIAL, value="https://facebook.com/OfficialPage", evidence=[Evidence(source_type="test", confidence_score=0.9)])
            ]
        )
        
        processed = processor.process(profile)
        vals = [s.value for s in processed.social_links]
        
        assert "https://facebook.com/officialpage" in vals
        assert not any("watch" in v for v in vals)
        assert not any("/p/" in v for v in vals)
        assert not any("hashtag" in v for v in vals)
