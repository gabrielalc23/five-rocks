
from typing import List, Type

from custom_types import T

from .dependency_info import DependencyInfo


class InjectableInfo:
    def __init__(self, cls: Type[T], deps: List[DependencyInfo]):
        self.cls = cls
        self.deps = deps

    def __repr__(self) -> str:
        return (
            f"InjectableInfo(class={self.cls.__name__}, deps={self.deps})"
        )