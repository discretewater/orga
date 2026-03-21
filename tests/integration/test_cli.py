
from typer.testing import CliRunner

from orga.cli.main import app

runner = CliRunner()

class TestCLI:
    """
    Integration tests for the ORGA CLI.
    """

    def test_list_strategies(self):
        """
        Test 'list-strategies' command to see if it displays registered strategies.
        """
        result = runner.invoke(app, ["list-strategies"])
        assert result.exit_code == 0
        assert "FETCHER" in result.stdout
        assert "httpx" in result.stdout
        assert "CATEGORY_CLASSIFIER" in result.stdout
        assert "weighted_heuristic" in result.stdout

    def test_validate_config_success(self, tmp_path):
        """
        Test 'validate-config' with a valid YAML file.
        """
        config_path = tmp_path / "valid_config.yaml"
        config_path.write_text("""
fetch:
  timeout: 45
  concurrency: 10
parse:
  strategies: ["json_ld", "contact"]
""")
        result = runner.invoke(app, ["validate-config", str(config_path)])
        assert result.exit_code == 0
        assert "Configuration is valid" in result.stdout

    def test_validate_config_failure(self, tmp_path):
        """
        Test 'validate-config' with an invalid YAML file (invalid types).
        """
        config_path = tmp_path / "invalid_config.yaml"
        config_path.write_text("""
fetch:
  timeout: "not-an-integer"
""")
        result = runner.invoke(app, ["validate-config", str(config_path)])
        assert result.exit_code != 0
        assert "validation error" in result.stdout or "Error" in result.stdout

    def test_parse_batch(self, tmp_path, monkeypatch):
        """
        Test 'parse-batch' command without debug flag (default).
        """
        urls_file = tmp_path / "urls.txt"
        urls_file.write_text("https://example.com\nhttps://test.org")
        
        output_file = tmp_path / "output.jsonl"
        
        from orga.model import OrganizationProfile
        from orga.pipeline import OrgaPipeline
        
        async def mock_run_from_url(self, url):
            profile = OrganizationProfile(name=f"Mock for {url}")
            profile.debug_info = {"filtered": "stuff"}
            return profile
            
        monkeypatch.setattr(OrgaPipeline, "run_from_url", mock_run_from_url)
        
        result = runner.invoke(app, ["parse-batch", str(urls_file), "--output", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        lines = output_file.read_text().splitlines()
        assert len(lines) == 2
        # Default behavior: debug info excluded
        assert "filtered" not in lines[0]

    def test_parse_batch_debug(self, tmp_path, monkeypatch):
        """
        Test 'parse-batch' command WITH --debug flag.
        """
        urls_file = tmp_path / "urls_debug.txt"
        urls_file.write_text("https://example.com")
        
        output_file = tmp_path / "output_debug.jsonl"
        
        from orga.model import OrganizationProfile
        from orga.pipeline import OrgaPipeline
        
        async def mock_run_from_url(self, url):
            profile = OrganizationProfile(name=f"Mock for {url}")
            profile.debug_info = {"filtered": "stuff"}
            return profile
            
        monkeypatch.setattr(OrgaPipeline, "run_from_url", mock_run_from_url)
        
        result = runner.invoke(app, ["parse-batch", str(urls_file), "--output", str(output_file), "--debug"])
        
        assert result.exit_code == 0
        lines = output_file.read_text().splitlines()
        # Debug behavior: debug info included
        assert "filtered" in lines[0]

    def test_parse_single_url_pretty(self, monkeypatch):
        """
        Test single URL parse with pretty output.
        """
        from orga.model import OrganizationProfile
        from orga.pipeline import OrgaPipeline
        
        async def mock_run_from_url(self, url):
            return OrganizationProfile(name="Single Mock")
            
        monkeypatch.setattr(OrgaPipeline, "run_from_url", mock_run_from_url)
        
        result = runner.invoke(app, ["parse", "https://single.com"])
        assert result.exit_code == 0
        # Check if it looks like pretty JSON
        assert '"name": "Single Mock"' in result.stdout

    def test_parse_debug_mode(self, monkeypatch):
        """
        Test that --debug flag populates debug_info and outputs internal evidence.
        """
        from orga.model import Evidence, OrganizationProfile
        from orga.pipeline import OrgaPipeline
        
        async def mock_run_from_url(self, url):
            profile = OrganizationProfile(name="Debug Mock")
            # Populate fake internal evidence to verify it's output
            profile.internal_evidence = [Evidence(source_type="debug_test", snippet="rejected")]
            profile.debug_info = {"filtered_links": ["http://bad.com"]}
            return profile
            
        monkeypatch.setattr(OrgaPipeline, "run_from_url", mock_run_from_url)
        
        # 1. Run WITHOUT debug -> Should NOT see internal evidence
        result = runner.invoke(app, ["parse", "https://debug.com"])
        assert result.exit_code == 0
        assert '"internal_evidence":' not in result.stdout
        assert '"debug_info":' not in result.stdout
        
        # 2. Run WITH debug -> Should see internal evidence and debug_info
        result_debug = runner.invoke(app, ["parse", "https://debug.com", "--debug"])
        assert result_debug.exit_code == 0
        assert '"internal_evidence":' in result_debug.stdout
        assert '"debug_info":' in result_debug.stdout
        assert "filtered_links" in result_debug.stdout
