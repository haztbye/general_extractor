"""PDF 本地解析器（PyMuPDF），替代内部 OCR gRPC 服务。

能力：
- 文本层逐字符坐标（rawdict），生成与文本严格等长的 char_rects
- find_tables() 识别表格，生成 rows/cells 结构，单元格段落 id 为 "{t}-{r}-{c}-{p}"
- 纯图片扫描件（无文本层）会给出明确提示

局限：
- 不做 OCR。扫描件请先用 OCR 工具转成带文本层的 PDF（如 Adobe/福昕的 OCR 功能，
  或 PaddleOCR pp-structurev2），本项目保持零重型依赖。
"""

import io
from typing import List, Optional

from loguru import logger

import pymupdf as fitz  # PyMuPDF（2.0 起 `import fitz` 已废弃）

from extractor_pdf.document_parsing.models import (
    Cell, CharRects, FormDoc, Rect, Row, Section, Table,
)


def _bbox_to_coord(bbox) -> List:
    """PyMuPDF bbox (x0, y0, x1, y1) -> 四点坐标 [左上, 右上, 右下, 左下]。"""
    x0, y0, x1, y1 = bbox
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _make_char_rect(bbox, page_id: int) -> Rect:
    return Rect(coord=_bbox_to_coord(bbox), page_id=page_id)


def _extract_block_text(block: dict, page_id: int):
    """把 rawdict 的文本 block 转为 (text, char_rects)。

    行间插入 '\\n'，并为其生成占位字符框，保证 len(text) == len(rect_list)。
    """
    chars_text: List[str] = []
    rect_list: List[Rect] = []

    for line in block.get("lines", []):
        last_rect: Optional[Rect] = None
        line_has_content = False
        for span in line.get("spans", []):
            for ch in span.get("chars", []):
                c = ch.get("c", "")
                if not c:
                    continue
                chars_text.append(c)
                last_rect = _make_char_rect(ch["bbox"], page_id)
                rect_list.append(last_rect)
                line_has_content = True
        if line_has_content and last_rect is not None:
            chars_text.append("\n")
            rect_list.append(Rect(coord=list(last_rect.coord), page_id=last_rect.page_id))

    # 去掉末尾换行
    while chars_text and chars_text[-1] == "\n":
        chars_text.pop()
        rect_list.pop()

    text = "".join(chars_text)
    return text, rect_list


def _center_in_rects(bbox, table_bboxes) -> bool:
    """判断 block 中心是否落在任一表格区域内。"""
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    for tb in table_bboxes:
        if tb[0] <= cx <= tb[2] and tb[1] <= cy <= tb[3]:
            return True
    return False


def _chars_in_bbox(page_chars, bbox):
    """收集中心落在 bbox 内的字符（page_chars 已按阅读顺序排序）。"""
    x0, y0, x1, y1 = bbox
    picked = [
        (c, rc) for c, rc in page_chars
        if x0 - 1 <= (rc.coord[0][0] + rc.coord[2][0]) / 2 <= x1 + 1
        and y0 - 1 <= (rc.coord[0][1] + rc.coord[2][1]) / 2 <= y1 + 1
    ]
    return picked


def parse_pdf_bytes(data: bytes) -> FormDoc:
    """解析 PDF 字节流为 FormDoc。"""
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return _parse_pdf_document(doc)
    finally:
        doc.close()


def parse_pdf_file(path: str) -> FormDoc:
    doc = fitz.open(path)
    try:
        return _parse_pdf_document(doc)
    finally:
        doc.close()


def _parse_pdf_document(doc: fitz.Document) -> FormDoc:
    sections: List[Section] = []
    para_seq = 0
    table_seq = 0
    total_chars = 0

    for page_id in range(doc.page_count):
        page = doc[page_id]
        raw = page.get_text("rawdict")

        # 页面级字符流（含坐标），供表格单元格取文本用
        page_chars = []
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for ch in span.get("chars", []):
                        if ch.get("c"):
                            page_chars.append((ch["c"], _make_char_rect(ch["bbox"], page_id)))
        total_chars += len(page_chars)

        # 表格识别（失败或无表格则退化为纯段落流程）
        table_bboxes = []
        tables = []
        try:
            finder = page.find_tables()
            tables = list(getattr(finder, "tables", []) or [])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"第 {page_id + 1} 页表格识别失败（按纯文本处理）: {e}")

        for t in tables:
            table_bboxes.append(t.bbox)

        # 普通文本段落（跳过落入表格区域的 block）
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            if table_bboxes and _center_in_rects(block["bbox"], table_bboxes):
                continue
            text, rect_list = _extract_block_text(block, page_id)
            if not text.strip():
                continue
            block_rect = Rect(coord=_bbox_to_coord(block["bbox"]), page_id=page_id)
            sections.append(Section(
                id=str(para_seq),
                text=text,
                rects=[block_rect],
                char_rects=[CharRects(rect_list=rect_list)],
            ))
            para_seq += 1

        # 表格
        for t in tables:
            table = Table(rows=[])
            try:
                for row in t.rows:
                    r = Row(cells=[])
                    for col_idx, cell_bbox in enumerate(row.cells):
                        cell = Cell(children=[])
                        if cell_bbox is not None:
                            picked = _chars_in_bbox(page_chars, cell_bbox)
                            if picked:
                                cell_text = "".join(c for c, _ in picked)
                                cell_rects = [rc for _, rc in picked]
                                cell_rect = Rect(
                                    coord=_bbox_to_coord(cell_bbox), page_id=page_id
                                )
                                cell.children.append(Section(
                                    id=f"{table_seq}-{len(table.rows)}-{col_idx}-0",
                                    text=cell_text,
                                    rects=[cell_rect],
                                    char_rects=[CharRects(rect_list=cell_rects)],
                                ))
                        r.cells.append(cell)
                    table.rows.append(r)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"第 {page_id + 1} 页表格结构解析失败: {e}")
                continue

            if not any(c.children for row in table.rows for c in row.cells):
                continue  # 空表格跳过

            sections.append(Section(
                id=f"table-{table_seq}",
                text="",
                rects=[Rect(coord=_bbox_to_coord(t.bbox), page_id=page_id)],
                table=table,
            ))
            table_seq += 1

    if total_chars == 0:
        logger.warning(
            "该 PDF 没有文本层（疑似扫描件）。当前版本不带 OCR，"
            "请先用 OCR 工具将其转换为带文本层的 PDF。"
        )

    logger.info(
        f"PDF 解析完成: {doc.page_count} 页, "
        f"{len(sections)} 个顶层元素（含 {table_seq} 个表格）"
    )
    return FormDoc(sections=sections)
