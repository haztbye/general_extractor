from dataclasses import dataclass
import re
from typing import List, Dict, Optional, FrozenSet


@dataclass
class SearchPattern:
    """搜索模式的数据类"""
    extract_item_name: str
    original: str
    flexible_pattern: str
    char_set: FrozenSet[str]
    compiled_pattern: re.Pattern


@dataclass
class MatchResult:
    """匹配结果的数据类"""
    extract_item: str
    text: str
    positions: List[List]

@dataclass
class Position:
    """文本位置信息"""
    pos_id: int
    start: int
    end: int
    rects: Optional[List] = None

@dataclass
class TextSegment:
    """文本片段"""
    text: str
    position: Position
    window_id: Optional[int] = None

@dataclass
class ExtractResult:
    """提取结果"""
    item_name: str
    text: str
    result: str
    positions: List[Position]
    confidence: float = 1.0

@dataclass
class DocumentWindow:
    """文档窗口"""
    segments: List[TextSegment]
    window_id: int
    metadata: Dict = None

@dataclass
class RectangleCoordinates:
    """矩形坐标数据类"""
    left_up: float
    right_up: float
    right_down: float
    left_down: float
    page_id: int