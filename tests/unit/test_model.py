import pytest
from pydantic import ValidationError
from orga.model import (
    OrganizationProfile,
    Document,
    DocumentBundle,
    Location,
    Address,
    Contact,
    Evidence,
    Warning,
    WarningSeverity,
    Confidence
)

class TestOrganizationProfile:
    """
    测试 OrganizationProfile 及其子模型的验证逻辑与字段定义。
    """

    def test_profile_creation_minimal(self):
        """
        测试仅使用最小必需字段创建 OrganizationProfile。
        应确保默认字段（如 list 类型）被正确初始化为空列表。
        """
        profile = OrganizationProfile(
            name="Test Org",
            schema_version="0.1.0"
        )
        assert profile.name == "Test Org"
        assert profile.locations == []
        assert profile.phones == []
        assert profile.emails == []
        assert profile.categories == []
        assert profile.warnings == []
        assert isinstance(profile.confidence, (Confidence, type(None))) # 允许为空或默认对象

    def test_profile_full_fields(self):
        """
        测试包含所有字段的 OrganizationProfile 创建，验证嵌套模型的正确性。
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
            schema_version="0.1.0"
        )
        assert len(profile.aliases) == 2
        assert profile.locations[0].address.city == "Metropolis"
        assert profile.locations[0].evidence[0].source_type == "html_text"
        assert profile.phones[0].value == "+1234567890"
        assert "Technology" in profile.categories

class TestDocumentModels:
    """
    测试 Document 和 DocumentBundle 模型。
    """

    def test_document_creation(self):
        """
        测试 Document 对象的创建与基本校验。
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
        测试 Document 缺少必要字段（如 url 或 content）时的校验错误。
        """
        with pytest.raises(ValidationError):
            Document(url="https://no-content.com") # 缺少 content

    def test_document_bundle_structure(self):
        """
        测试 DocumentBundle 的结构，确保它能包含多个 Document 并识别入口页。
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
        # 验证是否可以通过 URL 查找文档（如果模型支持该辅助方法，这里作为预留测试）
        # assert bundle.get_document("https://example.com/contact") == contact_doc

class TestGovernanceModels:
    """
    测试 Evidence, Warning 等治理模型。
    """

    def test_evidence_structure(self):
        """
        测试 Evidence 模型的字段完整性。
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
        测试 Warning 模型及其 Severity 枚举。
        """
        warn = Warning(
            code="FETCH_TIMEOUT",
            message="Connection timed out",
            severity=WarningSeverity.ERROR, # 假设使用了 Enum
            related_field="locations"
        )
        assert warn.severity == WarningSeverity.ERROR
        assert warn.code == "FETCH_TIMEOUT"

class TestAddressModel:
    """
    测试 Address 模型及其约束。
    """
    
    def test_address_raw_retention(self):
        """
        测试 Address 模型必须保留 raw 字段，即使其他字段解析失败。
        """
        addr = Address(
            raw="123 Complex Road, Unit 456",
            street="123 Complex Road",
            unit="456"
        )
        assert addr.raw == "123 Complex Road, Unit 456"
        assert addr.street == "123 Complex Road"
        
        # 仅有 raw 的情况
        addr_minimal = Address(raw="Unparseable String")
        assert addr_minimal.raw == "Unparseable String"
        assert addr_minimal.city is None
