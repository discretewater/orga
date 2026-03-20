import pytest

@pytest.fixture
def sample_html_content() -> str:
    """
    返回一个简单的 HTML 内容用于测试。
    """
    return """
    <html>
        <head><title>Test Org</title></head>
        <body>
            <h1>Test Organization</h1>
            <p class="address">123 Test St, Test City, TC 12345</p>
            <a href="mailto:contact@test.org">contact@test.org</a>
        </body>
    </html>
    """

@pytest.fixture
def complex_html_content() -> str:
    """
    返回一个包含多种信号（JSON-LD, Meta, Text）的复杂 HTML。
    """
    return """
    <html>
        <head>
            <title>Complex Org - Leader in Tech</title>
            <meta name="description" content="We build the future.">
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "url": "https://complex.org",
                "logo": "https://complex.org/logo.png"
            }
            </script>
        </head>
        <body>
            <header>
                <h1>Complex Org</h1>
            </header>
            <main>
                <section id="contact">
                    <h2>Get in Touch</h2>
                    <p>Call us: +1-800-COMPLEX</p>
                    <p>Email: <a href="mailto:hello@complex.org">hello@complex.org</a></p>
                </section>
                <section id="locations">
                    <div class="location">
                        <h3>HQ</h3>
                        <p>100 Tech Blvd, Silicon Valley, CA</p>
                    </div>
                </section>
            </main>
            <footer>
                <a href="https://twitter.com/complex">Twitter</a>
            </footer>
        </body>
    </html>
    """

@pytest.fixture
def sample_config_dict() -> dict:
    """
    返回一个基础的配置字典。
    """
    return {
        "fetch": {
            "timeout": 30,
            "user_agent": "OrgaTest/0.1",
            "retries": 2
        },
        "parse": {
            "strategies": ["regex", "heuristic", "json_ld"]
        },
        "taxonomy": {
            "categories": ["Technology", "Finance", "Healthcare"]
        }
    }
