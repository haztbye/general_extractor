"""FormDoc 等价数据模型（替代 contractlib）。

属性形状与 contractlib 保持一致，使 core/core2 流水线无改动即可运行：
- section.id            : str，普通段落为纯数字，表格单元格段落为 "{t}-{r}-{c}-{p}"
- section.rects         : List[Rect]，rects[0].page_id 为 0 起始页码
- section.char_rects    : List[CharRects]，char_rects[0].rect_list 与 section.text 逐字符对齐
- section.table         : Table（仅表格 section），table.rows[].cells[].children[] 为段落列表
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Rect:
    """矩形。coord 为四点顺序：左上、右上、右下、左下，每点 (x, y)。"""
    coord: List = field(default_factory=list)
    page_id: int = -1


@dataclass
class CharRects:
    """一个 section 的字符框集合。rect_list 与 section.text 等长、逐字符对应。"""
    rect_list: List[Rect] = field(default_factory=list)


@dataclass
class Section:
    """文档元素：普通段落或表格。"""
    id: str
    text: str = ""
    rects: List[Rect] = field(default_factory=list)
    char_rects: List[CharRects] = field(default_factory=list)
    children: Optional[List["Section"]] = None   # 仅表格单元格内的段落
    table: Optional["Table"] = None              # 仅表格 section

    @property
    def is_table(self) -> bool:
        return self.table is not None


@dataclass
class Cell:
    """表格单元格。children 为其中的段落 Section 列表。"""
    children: List[Section] = field(default_factory=list)


@dataclass
class Row:
    """表格行。"""
    cells: List[Cell] = field(default_factory=list)


@dataclass
class Table:
    """表格。"""
    rows: List[Row] = field(default_factory=list)


@dataclass
class FormDoc:
    """整篇文档：顶层元素按出现顺序排列。"""
    sections: List[Section] = field(default_factory=list)
