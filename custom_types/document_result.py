from dataclasses import dataclass, field
from enum import Enum
from typing import List, Literal, Optional
from enums import ProcessingStatus

@dataclass
class DocumentResult:
    file_path: str
    status: ProcessingStatus
    summary: Optional[str] = None
    error_message: Optional[str] = None
    page_count: int = 0
    word_count: int = 0
    processing_time_ms: float = 0.0

    @property
    def file_name(self) -> str:
        from pathlib import Path
        return Path(self.file_path).name

    @property
    def is_success(self) -> bool:
        return self.status == ProcessingStatus.SUCCESS

    def __repr__(self) -> str:
        status_icon = "✓" if self.is_success else "✗"
        return f"{status_icon} {self.file_name} ({self.status.value})"


