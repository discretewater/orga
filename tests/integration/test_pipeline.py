import pytest
from unittest.mock import MagicMock
from orga.pipeline import OrgaPipeline
from orga.model import OrgaConfig, OrganizationProfile, Document, DocumentBundle, Warning, Confidence

class TestPipelineIntegration:
    """
    测试核心 Pipeline 的集成流程，覆盖单文档与文档束（Bundle）场景。
    """

    @pytest.mark.asyncio
    async def test_pipeline_with_document_bundle(self):
        """
        测试传入 DocumentBundle 时的处理流程。
        Pipeline 应能聚合来自 Entry 页和 Contact 页的信息。
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
        测试 Pipeline 是否正确集成了治理模块（Warning, Confidence）。
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
        # 验证空 Profile 应产生警告
        assert "EMPTY_PROFILE" in warning_codes or "LOW_CONFIDENCE" in warning_codes
        
        # 验证置信度应较低
        if profile.confidence:
            assert profile.confidence.overall_score < 0.5

    @pytest.mark.asyncio
    async def test_pipeline_confidence_consistency(self):
        """
        [新增] 测试置信度的一致性。
        如果字段置信度都很低，整体置信度不应过高。
        """
        # 模拟一个只有低置信度电话的文档
        # 假设 parser 会提取出电话但因为是 regex，给低分
        doc = Document(
            url="https://lowconf.test",
            content="<html>Call: 123-456-7890</html>",
            content_type="text/html",
            status_code=200
        )
        
        pipeline = OrgaPipeline(OrgaConfig())
        profile = await pipeline.run([doc])
        
        # 假设实现正确，电话置信度应 < 0.8
        if profile.phones:
            assert profile.phones[0].confidence < 0.8
        
        # 整体置信度应受到影响，不应是 0.9 或 1.0
        # 且如果有字段提取出来，confidence 对象就不应为空
        assert profile.confidence is not None
        assert profile.confidence.overall_score < 0.8

    @pytest.mark.asyncio
    async def test_pipeline_warnings_for_missing_critical_fields(self):
        """
        [新增] 测试当关键字段（如地址、分类）缺失时，产生 Warning。
        """
        # 一个有名字但没地址、没分类的文档
        doc = Document(
            url="https://partial.test",
            content="<html><title>Partial Corp</title></html>",
            content_type="text/html",
            status_code=200
        )
        
        pipeline = OrgaPipeline(OrgaConfig())
        profile = await pipeline.run([doc])
        
        warning_codes = [w.code for w in profile.warnings]
        
        # 应该警告地址缺失
        assert "NO_LOCATION_FOUND" in warning_codes or "PARTIAL_PROFILE" in warning_codes
        # 应该警告分类缺失
        assert "CLASSIFICATION_LOW_CONFIDENCE" in warning_codes or "PARTIAL_PROFILE" in warning_codes

    @pytest.mark.asyncio
    async def test_pipeline_strategy_switching(self):
        """
        测试通过配置切换策略。
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
