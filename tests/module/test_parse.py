import pytest
from orga.parse.fields import ContactParser, AddressParser, CategoryClassifier
from orga.model import Document, Contact, Address, ContactKind, Evidence

class TestContactParser:
    """
    测试联系方式解析器。
    """

    def test_extract_emails_complex(self):
        """
        测试复杂的 Email 提取场景，包括混淆的 Email 和多个 Email。
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
        测试从页脚或图标提取社交媒体链接。
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
        [新增] 测试严格的电话号码校验。
        应排除：日期、长数字串、无效号码。
        应保留：合法格式号码。
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

        # 验证正向用例
        assert any("613-737-7600" in v or "+16137377600" in v for v in phone_values)
        
        # 验证负向用例 (不应包含)
        assert "2026-02-24" not in phone_values
        assert "00000000-0000-000" not in phone_values
        assert "15018176-5" not in phone_values
        assert "911-9449-0050569" not in phone_values

    def test_phone_confidence_scoring(self):
        """
        [新增] 测试电话号码的置信度评分。
        tel 链接应该比纯文本 regex 具有更高的置信度。
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
        # 验证置信度差异
        assert tel_phone.confidence > text_phone.confidence
        assert tel_phone.confidence >= 0.8 # 假设高置信度阈值
        assert text_phone.confidence < 0.8

class TestAddressParser:
    """
    测试地址解析器。
    """

    def test_extract_address_from_schema_org(self):
        """
        测试从 JSON-LD (Schema.org) 中提取地址。
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
        测试当无结构化数据时，基于正则或启发式规则提取地址。
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
        [新增] 测试从 Footer 或特定 DOM 区域提取地址。
        优先于全文扫描。
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
        # 验证是否提取到了 Footer 中的地址
        assert "789 Footer Lane" in locations[0].address.raw
        # 验证不应该提取到正文的随机数字 (如果正则够严谨)
        address_texts = [l.address.raw for l in locations]
        assert not any("12345" in a and "Lane" not in a for a in address_texts)

class TestCategoryClassifier:
    """
    测试分类器。
    """
    
    def test_classify_by_keywords_baseline(self):
        """
        [新增] 测试基于关键词的基线分类。
        即使没有 LLM，也应能识别常见类别。
        """
        content = """
        <title>Children's Hospital of Eastern Ontario</title>
        <h1>Welcome to CHEO</h1>
        <p>Providing pediatric healthcare and patient care.</p>
        """
        doc = Document(url="https://cheo.test", content=content, content_type="text/html", status_code=200)
        
        # 配置 taxonomy
        taxonomy_config = {
            "Healthcare": ["hospital", "clinic", "healthcare", "patient"],
            "Education": ["university", "school", "college"]
        }
        classifier = CategoryClassifier(taxonomy=taxonomy_config)
        
        result = classifier.classify(doc)
        categories = result.categories
        assert "Healthcare" in categories
        assert "Education" not in categories
