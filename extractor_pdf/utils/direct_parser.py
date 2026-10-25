"""本地文档解析入口（原为内部 OCR/parser gRPC 直连，现全部本地完成）。

- parse_pdf_direct(path)   : PDF  -> FormDoc（PyMuPDF，字符级坐标 + 表格）
- parse_docx_direct(path)  : DOCX -> FormDoc（python-docx，段落级定位）
- parse_file_direct(path)  : 按扩展名自动选择
"""

from loguru import logger


def parse_pdf_direct(pdf_path: str):
    """本地解析 PDF 文件为 FormDoc"""
    try:
        from extractor_pdf.document_parsing.pdf_parser import parse_pdf_file
        logger.info(f"本地解析 PDF: {pdf_path}")
        return parse_pdf_file(pdf_path)
    except Exception as e:
        logger.error(f"PDF 解析失败: {e}")
        raise


def parse_docx_direct(docx_path: str):
    """本地解析 DOCX 文件为 FormDoc"""
    try:
        from extractor_pdf.document_parsing.docx_parser import parse_docx_bytes
        logger.info(f"本地解析 DOCX: {docx_path}")
        with open(docx_path, "rb") as f:
            import io
            return parse_docx_bytes(io.BytesIO(f.read()))
    except Exception as e:
        logger.error(f"DOCX 解析失败: {e}")
        raise


def parse_file_direct(file_path: str):
    """根据文件扩展名自动选择解析方式"""
    if file_path.lower().endswith('.pdf'):
        return parse_pdf_direct(file_path)
    elif file_path.lower().endswith('.docx'):
        return parse_docx_direct(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}（支持 .pdf / .docx）")
