from typing import Literal
from enum import Enum

class ProcessingStatus(Enum):
    SUCCESS: Literal['success'] = 'success'
    ERROR: Literal['error'] = 'error'
    SKIPPED: Literal['skipped'] = 'skipped'
    EMPTY_CONTENT: Literal['empty_content'] = 'empty_content'
