from typing import List, Type, Any
from inspect import Signature, Parameter
import inspect
from info import InjectableInfo, DependencyInfo
from constants import INJECTABLES

class DiscoveryService:
    @staticmethod
    def discover() -> List[InjectableInfo]:
        discovered: List[InjectableInfo] = []

        for cls in INJECTABLES.values():
            info: InjectableInfo = DiscoveryService._inspect_class(cls)
            discovered.append(info)

        return discovered

    @staticmethod
    def _inspect_class(cls: Type[Any]) -> InjectableInfo:
        signature: Signature = inspect.signature(cls.__init__)
        params: List[Parameter] = list(signature.parameters.values())[1:]  # remove self

        deps: List[DependencyInfo] = []

        for p in params:
            if p.annotation is inspect._empty:
                raise TypeError(
                    f"Dependência '{p.name}' de {cls.__name__} precisa de type-hint."
                )

            dep_type = p.annotation

            if dep_type not in INJECTABLES:
                raise TypeError(
                    f"'{cls.__name__}' depende de '{dep_type.__name__}', "
                    f"mas esta classe não está registrada com @injectable."
                )

            deps.append(DependencyInfo(p.name, dep_type))

        return InjectableInfo(cls, deps)