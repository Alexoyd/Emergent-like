# stacks/registry.py
from __future__ import annotations
from typing import Dict, Type, Optional, Any
from .base_handler import StackHandler

class StackRegistry:
    _handlers: Dict[str, Type[StackHandler]] = {}

    @classmethod
    def register(cls, name: str, handler_cls: Type[StackHandler]) -> None:
        key = name.strip().lower()
        cls._handlers[key] = handler_cls

    @classmethod
    def get(cls, name: str) -> Optional[Type[StackHandler]]:
        return cls._handlers.get((name or "").strip().lower())

    @classmethod
    def all(cls) -> Dict[str, Type[StackHandler]]:
        return dict(cls._handlers)

class StackFactory:
    @staticmethod
    def create(name: str, **kwargs: Any) -> StackHandler:
        handler_cls = StackRegistry.get(name)
        if not handler_cls:
            raise ValueError(f"No handler registered for stack '{name}'")
        return handler_cls(**kwargs)  # type: ignore[misc]