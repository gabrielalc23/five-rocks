from abc import ABC, abstractmethod


class BaseSummarizer(ABC):

    @abstractmethod
    def summarize(self, text: str) -> str:
        pass
