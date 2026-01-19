from typing import Type, Any
from custom_types import T

class DependencyInfo:
    def __init__(self, param_name: str, param_type: Type[T]):
        self.param_name = param_name
        self.param_type = param_type

    def __repr__(self) -> str:
        return f"DependencyInfo(name={self.param_name}, type={self.param_type.__name__})"
