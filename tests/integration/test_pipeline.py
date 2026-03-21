
import pytest

from orga.model import (
    Document,
    DocumentBundle,
    OrgaConfig,
)
from orga.pipeline import OrgaPipeline


class TestPipelineIntegration:
    """
    Test integration flow of the core Pipeline, covering single Document and DocumentBundle scenarios.
    """

    @pytest.mark.asyncio
    async def test_pipeline_with_document_bundle(self):
        """
        Test processing flow when DocumentBundle is passed.
        Pipeline should be able to aggregate information from Entry page and Contact page.
        """
        entry_doc = Document(
            url="https://bundle.test",
            content="<html><title>Bundle Corp</title></html>",
            content_type="text/html",
            status_code=200
        )
        contact_doc = Document(
            url="https://bundle.test/contact",
            content="<html>Email: contact@bundle.test</html>",
            content_type="text/html",
            status_code=200
        )
        bundle = DocumentBundle(
            entry_url="https://bundle.test",
            documents=[entry_doc, contact_doc]
        )
        
        pipeline = OrgaPipeline(OrgaConfig())
        profile = await pipeline.run_bundle(bundle)
        
        assert profile.name == "Bundle Corp"
        email_values = [e.value for e in profile.emails]
        assert "contact@bundle.test" in email_values
        
        assert len(profile.evidence) > 0

    @pytest.mark.asyncio
    async def test_pipeline_governance_integration(self):
        """
        Test if the Pipeline correctly integrates the governance modules (Warning, Confidence).
        """
        low_quality_doc = Document(
            url="https://lowquality.test",
            content="<html><body>Empty Body</body></html>",
            content_type="text/html",
            status_code=200
        )
        
        pipeline = OrgaPipeline(OrgaConfig())
        profile = await pipeline.run([low_quality_doc])
        
        warning_codes = [w.code for w in profile.warnings]
        # Verify empty Profile should produce warnings
        assert "EMPTY_PROFILE" in warning_codes or "LOW_CONFIDENCE" in warning_codes
        
        # Verify confidence should be low
        if profile.confidence:
            assert profile.confidence.overall_score < 0.5

    @pytest.mark.asyncio
    async def test_pipeline_confidence_consistency(self):
        """
        [New] Test consistency of confidence.
        If field confidences are all low, overall confidence should not be too high.
        """
        # Simulate a document with only a low-confidence phone number
        # Assume parser extracts the phone but gives a low score because it is regex
        doc = Document(
            url="https://lowconf.test",
            content="<html>Call: 123-456-7890</html>",
            content_type="text/html",
            status_code=200
        )
        
        pipeline = OrgaPipeline(OrgaConfig())
        profile = await pipeline.run([doc])
        
        # Assuming correct implementation, phone confidence should be < 0.8
        if profile.phones:
            assert profile.phones[0].confidence < 0.8
        
        # Overall confidence should be affected, should not be 0.9 or 1.0
        # And if fields are extracted, the confidence object should not be empty
        assert profile.confidence is not None
        assert profile.confidence.overall_score < 0.8

    @pytest.mark.asyncio
    async def test_pipeline_warnings_for_missing_critical_fields(self):
        """
        [New] Test that a Warning is produced when critical fields (like address, categories) are missing.
        """
        # A document with a name but no address and no categories
        doc = Document(
            url="https://partial.test",
            content="<html><title>Partial Corp</title></html>",
            content_type="text/html",
            status_code=200
        )
        
        pipeline = OrgaPipeline(OrgaConfig())
        profile = await pipeline.run([doc])
        
        warning_codes = [w.code for w in profile.warnings]
        
        # Should warn about missing address
        assert "NO_LOCATION_FOUND" in warning_codes or "PARTIAL_PROFILE" in warning_codes
        # Should warn about missing categories
        assert "CLASSIFICATION_LOW_CONFIDENCE" in warning_codes or "PARTIAL_PROFILE" in warning_codes

    @pytest.mark.asyncio
    async def test_pipeline_strategy_switching(self):
        """
        Test switching strategies via configuration.
        """
        config = OrgaConfig(
            parse={"strategies": ["json_ld"]} 
        )
        
        doc_with_text_only = Document(
            url="https://textonly.test",
            content="<html>Phone: 1234567890</html>",
            content_type="text/html",
            status_code=200
        )
        
        pipeline = OrgaPipeline(config)
        profile = await pipeline.run([doc_with_text_only])
        
        assert len(profile.phones) == 0
