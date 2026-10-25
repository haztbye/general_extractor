"""DOCX 本地解析器（python-docx），替代内部 parser gRPC 服务。

说明：
- Word 格式不含渲染坐标，因此 char_rects 为空（定位自动回退段落级，见
  position_processor 的回退分支），页码按"显式分页符 + 每页元素数上限"估算。
- 表格结构与 PDF 一致：单元格段落 id 为 "{t}-{r}-{c}-{p}"。
- 老版 .doc 二进制格式不支持，请先另存为 .docx。
"""

from typing import List

from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from loguru import logger

from extractor_pdf.document_parsing.models import (
    Cell, CharRects, FormDoc, Rect, Row, Section, Table,
)

# 每页兜底元素数（无显式分页符的长文档按此估算伪页码）
_MAX_BLOCKS_PER_PAGE = 60

_PARA_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
_TBL_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"
_BR_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
_PAGE_BREAK_TAG = (
    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lastRenderedPageBreak"
)


def _iter_block_items(doc):
    """按文档实际顺序迭代段落与表格。"""
    for child in doc.element.body.iterchildren():
        if child.tag == _PARA_TAG:
            yield DocxParagraph(child, doc)
        elif child.tag == _TBL_TAG:
            yield DocxTable(child, doc)


def _para_has_page_break(paragraph: DocxParagraph) -> bool:
    """检测段落中的显式/渲染分页符。"""
    for br in paragraph._p.iter(_BR_TAG):
        if br.get(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type"
        ) == "page":
            return True
    for _ in paragraph._p.iter(_PAGE_BREAK_TAG):
        return True
    return False


class _FakePager:
    """估算伪页码：显式分页符优先，元素数上限兜底。"""

    def __init__(self):
        self.page = 0
        self.blocks_in_page = 0

    def next_block(self, has_page_break: bool = False) -> int:
        if has_page_break or self.blocks_in_page >= _MAX_BLOCKS_PER_PAGE:
            self.page += 1
            self.blocks_in_page = 0
        self.blocks_in_page += 1
        return self.page


def _pseudo_rect(page_id: int, seq_in_page: int) -> Rect:
    """生成示意坐标（Word 无版面坐标，仅供结果展示/排序用）。"""
    y = seq_in_page * 20.0
    return Rect(coord=[(0.0, y), (500.0, y), (500.0, y + 18.0), (0.0, y + 18.0)], page_id=page_id)


def parse_docx_bytes(stream) -> FormDoc:
    """解析 DOCX 文件流为 FormDoc。"""
    doc = DocxDocument(stream)
    sections: List[Section] = []
    pager = _FakePager()
    para_seq = 0
    table_seq = 0
    seq_in_page = 0

    for block in _iter_block_items(doc):
        if isinstance(block, DocxParagraph):
            text = block.text
            if not text.strip():
                # 空段落不产出 section，但分页符仍要生效
                if _para_has_page_break(block):
                    pager.next_block(has_page_break=True)
                    seq_in_page = 0
                continue
            page = pager.next_block(has_page_break=_para_has_page_break(block))
            sections.append(Section(
                id=str(para_seq),
                text=text,
                rects=[_pseudo_rect(page, seq_in_page)],
                char_rects=[],
            ))
            para_seq += 1
            seq_in_page += 1
            continue

        # 表格
        page = pager.next_block()
        table = Table(rows=[])
        cell_texts = 0
        for row_idx, row in enumerate(block.rows):
            r = Row(cells=[])
            for col_idx, cell in enumerate(row.cells):
                c = Cell(children=[])
                for p_idx, para in enumerate(cell.paragraphs):
                    if not para.text.strip():
                        continue
                    c.children.append(Section(
                        id=f"{table_seq}-{row_idx}-{col_idx}-{p_idx}",
                        text=para.text,
                        rects=[_pseudo_rect(page, seq_in_page)],
                        char_rects=[],
                    ))
                    seq_in_page += 1
                    cell_texts += 1
                r.cells.append(c)
            table.rows.append(r)

        if cell_texts == 0:
            continue
        sections.append(Section(
            id=f"table-{table_seq}",
            text="",
            rects=[_pseudo_rect(page, seq_in_page)],
            table=table,
        ))
        table_seq += 1
        seq_in_page += 1

    logger.info(
        f"DOCX 解析完成: {len(sections)} 个顶层元素（含 {table_seq} 个表格），"
        f"估算 {pager.page + 1} 页（伪页码，仅用于窗口切分）"
    )
    return FormDoc(sections=sections)
