"""本地文档解析模块（contractlib 的开源等价实现）。

- PDF:  PyMuPDF，字符级坐标 + 表格识别
- DOCX: python-docx，段落级定位（伪页码）
"""

from extractor_pdf.document_parsing import models
from extractor_pdf.document_parsing.form_doc import (
    formdoc_iter,
    get_section_by_id,
    get_section_text,
    is_table,
    new_formdoc_from_path,
    parse,
)
from extractor_pdf.document_parsing.models import (  # noqa: F401
    Cell, CharRects, FormDoc, Rect, Row, Section, Table,
)

__all__ = [
    "models",
    "formdoc_iter",
    "get_section_by_id",
    "get_section_text",
    "is_table",
    "new_formdoc_from_path",
    "parse",
    "Cell",
    "CharRects",
    "FormDoc",
    "Rect",
    "Row",
    "Section",
    "Table",
]
