from abc import ABC, abstractmethod

from custom_types.path_like import PathLike


class BaseAdapter(ABC):

    @abstractmethod
    def read_text(self, file_path: PathLike) -> str:
        pass
