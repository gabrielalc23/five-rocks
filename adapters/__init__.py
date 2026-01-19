from typing import List

from .base_adapter import BaseAdapter
from .docx_adapter import DocxAdapter
from .faiss_adapter import FaissAdapter
from .pdf_adapter import PdfAdapter

__all__: List[str] = [
    "BaseAdapter",
    "DocxAdapter",
    "FaissAdapter",
    "PdfAdapter"
]
