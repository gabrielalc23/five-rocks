from __future__ import annotations
import inspect
from typing import Any, List
from inspect import Parameter, Signature

from constants import INJECTABLES
from custom_types import InjectableClass, T


def inject(cls: InjectableClass[T]) -> T:
    if cls not in INJECTABLES:
        raise ValueError(f"{cls.__name__} is not registered as @injectable.")

    signature: Signature = inspect.signature(cls.__init__)
    params: List[Parameter] = list[Parameter](signature.parameters.values())[1:]

    if not params:
        return cls()

    deps: List[T] = []

    for p in params:
        dep_type = p.annotation
        if dep_type is inspect.Parameter.empty:
            raise TypeError(
                f"Dependency '{p.name}' of {cls.__name__} is missing a type-hint."
            )
        
        dep_instance: T = inject(dep_type)
        deps.append(dep_instance)

    return cls(*deps)