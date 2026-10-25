"""contractlib.form_doc 的兼容 API 层。

保持原项目使用的函数签名不变：
- formdoc_iter(doc, with_table_whole=True) -> Iterator[(section_type, section)]
- get_section_text(section) -> str
- is_table(section) -> bool
- get_section_by_id(doc, section_id) -> Optional[Section]
- parse(data: bytes) -> FormDoc
- new_formdoc_from_path(path: str) -> FormDoc
"""

import os
from typing import Iterator, List, Optional, Tuple

from loguru import logger

from extractor_pdf.document_parsing.models import FormDoc, Section


def _iter_all_sections(doc: FormDoc) -> Iterator[Section]:
    """深度优先遍历所有 section（含表格单元格内的段落）。"""
    for s in doc.sections:
        yield s
        if s.table is not None:
            for row in s.table.rows:
                for cell in row.cells:
                    for child in cell.children or []:
                        yield child


def formdoc_iter(doc: FormDoc, with_table_whole: bool = True) -> Iterator[Tuple[str, Section]]:
    """迭代文档顶层元素。表格既作为整体 yield，也可通过 table.rows 遍历内部段落。"""
    for s in doc.sections:
        if s.is_table:
            yield "table", s
            if not with_table_whole:
                continue
        else:
            yield "paragraph", s


def get_section_text(section: Section) -> str:
    """获取 section 文本。表格返回各单元格文本聚合。"""
    if section.is_table:
        parts = []
        for row in section.table.rows:
            for cell in row.cells:
                for child in cell.children or []:
                    if child.text:
                        parts.append(child.text)
        return "\n".join(parts)
    return section.text


def is_table(section: Section) -> bool:
    """判断 section 是否为表格。"""
    return section.is_table


def get_section_by_id(doc: FormDoc, section_id: str) -> Optional[Section]:
    """按 id 查找 section（含表格单元格段落）。"""
    target = str(section_id)
    for s in _iter_all_sections(doc):
        if s.id == target:
            return s
    return None


def parse(data: bytes) -> FormDoc:
    """解析文件字节流为 FormDoc（按魔数自动识别 PDF/DOCX）。"""
    if data[:4] == b"%PDF":
        from extractor_pdf.document_parsing.pdf_parser import parse_pdf_bytes
        return parse_pdf_bytes(data)
    # docx (zip) 魔数 PK
    if data[:2] == b"PK":
        import io
        from extractor_pdf.document_parsing.docx_parser import parse_docx_bytes
        return parse_docx_bytes(io.BytesIO(data))
    raise ValueError(f"不支持的文件格式（仅支持 PDF / DOCX）：{data[:8]!r}")


def new_formdoc_from_path(path: str) -> FormDoc:
    """从本地文件路径解析 FormDoc（兼容 contractlib.form_doc.new_formdoc_from_path）。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    with open(path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from extractor_pdf.document_parsing.pdf_parser import parse_pdf_bytes
        return parse_pdf_bytes(data)
    if ext in (".docx",):
        import io
        from extractor_pdf.document_parsing.docx_parser import parse_docx_bytes
        return parse_docx_bytes(io.BytesIO(data))
    if ext == ".doc":
        raise ValueError(
            "不再支持老版 .doc 格式（依赖已废弃的 textract）。"
            "请先用 Word/WPS 将其另存为 .docx 后重试。"
        )
    # 未知扩展名：按内容嗅探
    logger.warning(f"未知扩展名 {ext}，尝试按文件内容识别")
    return parse(data)
