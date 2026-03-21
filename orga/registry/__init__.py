from typing import Any, Dict, List, Optional, Type


class StrategyRegistry:
    """
    Strategy Registry.
    Used to manage the registration and discovery of various strategies like Fetcher, Parser, Merger, etc.
    """
    _registry: dict[str, dict[str, Any]] = {}

    def __init__(self) -> None:
        # Ensure basic structure exists
        if not hasattr(self, "_registry") or not self._registry:
            self._registry = {}

    def register(self, kind: str, name: str, impl: Any, force: bool = False) -> None:
        """
        Register a strategy.
        
        Args:
            kind: Strategy type (e.g., 'fetcher', 'parser')
            name: Strategy name (e.g., 'httpx', 'regex')
            impl: Strategy implementation class or object
            force: Whether to force overwrite an existing strategy
        """
        if kind not in self._registry:
            self._registry[kind] = {}
        
        if name in self._registry[kind] and not force:
            raise ValueError(f"Strategy '{name}' of kind '{kind}' is already registered.")
        
        self._registry[kind][name] = impl

    def get(self, kind: str, name: str) -> Any:
        """
        Get a registered strategy.
        """
        if kind not in self._registry:
            raise KeyError(f"No strategies registered for kind '{kind}'")
        
        if name not in self._registry[kind]:
            raise KeyError(f"Strategy '{name}' not found for kind '{kind}'")
        
        return self._registry[kind][name]

    def list(self, kind: str) -> list[str]:
        """
        List all strategy names for a specific kind.
        """
        if kind not in self._registry:
            return []
        return list(self._registry[kind].keys())

# Global singleton instance
registry = StrategyRegistry()
