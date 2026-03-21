import pytest

# Assuming a base class or interface definition exists
from orga.registry import StrategyRegistry


class TestStrategyRegistry:
    """
    Test the Strategy Registry mechanism.
    """

    def test_register_and_get_strategy(self):
        """
        Test registering a new strategy and retrieving it successfully.
        """
        registry = StrategyRegistry()
        
        class MockFetcher:
            pass

        registry.register("fetcher", "mock_fetcher", MockFetcher)
        fetched_class = registry.get("fetcher", "mock_fetcher")
        assert fetched_class is MockFetcher

    def test_get_non_existent_strategy(self):
        """
        Test that retrieving a non-existent strategy raises an exception.
        """
        registry = StrategyRegistry()
        with pytest.raises(KeyError):
            registry.get("fetcher", "non_existent")

    def test_list_strategies(self):
        """
        Test listing all strategies under a specific type.
        """
        registry = StrategyRegistry()
        registry.register("parser", "parser_a", object)
        registry.register("parser", "parser_b", object)
        
        parsers = registry.list("parser")
        assert "parser_a" in parsers
        assert "parser_b" in parsers

    def test_duplicate_registration_error(self):
        """
        Test that duplicate registration of a strategy with the same name throws an error by default
        (assuming throwing an error ensures strictness based on design).
        """
        registry = StrategyRegistry()
        registry.register("parser", "uniq_parser", object)
        
        with pytest.raises(ValueError):
            registry.register("parser", "uniq_parser", object)

    def test_overwrite_registration(self):
        """
        Test allowing forced overwrite of a registration (if force=True is provided).
        """
        registry = StrategyRegistry()
        registry.register("parser", "parser_x", int)
        
        # Assuming register supports force or exist_ok parameter
        registry.register("parser", "parser_x", str, force=True)
        assert registry.get("parser", "parser_x") is str
