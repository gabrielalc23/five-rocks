
from dataclasses import dataclass, field
from typing import List
from enums import ProcessingStatus
from .document_result import DocumentResult

@dataclass
class BatchResult:
    results: List[DocumentResult] = field(default_factory=list)
    total_processing_time_ms: float = 0.0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.is_success)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == ProcessingStatus.ERROR)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return ((self.success_count / self.total_count) * 100)

    def get_errors(self) -> list[DocumentResult]:
        return [r for r in self.results if r.status == ProcessingStatus.ERROR]

    def get_successful(self) -> list[DocumentResult]:
        return [r for r in self.results if r.is_success]

    def summary(self) -> str:
        return (
            f"Processados: {self.total_count} | "
            f"Sucesso: {self.success_count} | "
            f"Erros: {self.error_count} | "
            f"Taxa: {self.success_rate:.1f}% | "
            f"Tempo: {self.total_processing_time_ms:.0f}ms"
        )
