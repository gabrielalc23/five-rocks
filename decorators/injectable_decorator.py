from __future__ import annotations, print_function

from constants import INJECTABLES
from custom_types import InjectableClass, T

def injectable(cls: InjectableClass[T]) -> InjectableClass[T]:
    INJECTABLES[cls] = cls
    return cls