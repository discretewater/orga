from typing import Any, Dict, Type, Optional, List

class StrategyRegistry:
    """
    策略注册中心。
    用于管理 Fetcher, Parser, Merger 等各种策略的注册与发现。
    """
    _registry: Dict[str, Dict[str, Any]] = {}

    def __init__(self) -> None:
        # 确保基本结构存在
        if not hasattr(self, "_registry") or not self._registry:
            self._registry = {}

    def register(self, kind: str, name: str, impl: Any, force: bool = False) -> None:
        """
        注册一个策略。
        
        Args:
            kind: 策略类型 (e.g., 'fetcher', 'parser')
            name: 策略名称 (e.g., 'httpx', 'regex')
            impl: 策略实现类或对象
            force: 是否强制覆盖已存在的策略
        """
        if kind not in self._registry:
            self._registry[kind] = {}
        
        if name in self._registry[kind] and not force:
            raise ValueError(f"Strategy '{name}' of kind '{kind}' is already registered.")
        
        self._registry[kind][name] = impl

    def get(self, kind: str, name: str) -> Any:
        """
        获取一个已注册的策略。
        """
        if kind not in self._registry:
            raise KeyError(f"No strategies registered for kind '{kind}'")
        
        if name not in self._registry[kind]:
            raise KeyError(f"Strategy '{name}' not found for kind '{kind}'")
        
        return self._registry[kind][name]

    def list(self, kind: str) -> List[str]:
        """
        列出指定类型下的所有策略名称。
        """
        if kind not in self._registry:
            return []
        return list(self._registry[kind].keys())

# 全局单例实例
registry = StrategyRegistry()
