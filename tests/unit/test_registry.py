import pytest
from orga.registry import StrategyRegistry
# 假设存在一个基类或接口定义
from orga.fetch import FetchStrategy

class TestStrategyRegistry:
    """
    测试策略注册机制（Registry）。
    """

    def test_register_and_get_strategy(self):
        """
        测试注册一个新的策略并成功获取它。
        """
        registry = StrategyRegistry()
        
        class MockFetcher:
            pass

        registry.register("fetcher", "mock_fetcher", MockFetcher)
        fetched_class = registry.get("fetcher", "mock_fetcher")
        assert fetched_class == MockFetcher

    def test_get_non_existent_strategy(self):
        """
        测试获取不存在的策略时应抛出异常。
        """
        registry = StrategyRegistry()
        with pytest.raises(KeyError):
            registry.get("fetcher", "non_existent")

    def test_list_strategies(self):
        """
        测试列出特定类型下的所有策略。
        """
        registry = StrategyRegistry()
        registry.register("parser", "parser_a", object)
        registry.register("parser", "parser_b", object)
        
        parsers = registry.list("parser")
        assert "parser_a" in parsers
        assert "parser_b" in parsers

    def test_duplicate_registration_error(self):
        """
        测试重复注册同名策略时，默认应抛出错误或覆盖（取决于设计，这里假设抛错以保证严谨性）。
        """
        registry = StrategyRegistry()
        registry.register("parser", "uniq_parser", object)
        
        with pytest.raises(ValueError):
            registry.register("parser", "uniq_parser", object)

    def test_overwrite_registration(self):
        """
        测试允许强制覆盖注册（如果提供了 force=True 参数）。
        """
        registry = StrategyRegistry()
        registry.register("parser", "parser_x", int)
        
        # 假设 register 支持 force 参数或 exist_ok
        registry.register("parser", "parser_x", str, force=True)
        assert registry.get("parser", "parser_x") == str
