"""grpc_services.contract.form_doc_pb2 中返回消息的本地等价结构。

保持原代码写法兼容（FormRes.labels[key] 访问即创建、.add() 链式添加、
rect.extend()），序列化改用 form_res_to_dict / form_res_to_json。
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List

from extractor_pdf.document_parsing.models import Rect  # noqa: F401  (转发导出)


class RepeatedField(list):
    """模拟 proto repeated field 的 .add() 行为。"""

    def __init__(self, item_factory):
        super().__init__()
        self._factory = item_factory

    def add(self):
        item = self._factory()
        self.append(item)
        return item


@dataclass
class Position:
    """字段位置：pos_id + 命中的矩形列表。"""
    coordinates: str = ""
    rect: List[Rect] = field(default_factory=list)


@dataclass
class LabelInfo:
    """单个要素的结果。"""
    value: str = ""
    type: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)
    pos: RepeatedField = field(default_factory=lambda: RepeatedField(Position))


@dataclass
class LabelInfoList:
    """同一要素名的多个结果。"""
    labels: RepeatedField = field(default_factory=lambda: RepeatedField(LabelInfo))


class FormRes:
    """整份文档的抽取结果：要素名 -> LabelInfoList。"""

    def __init__(self):
        self.labels = defaultdict(LabelInfoList)


def _rect_to_dict(rect: Rect) -> Dict[str, Any]:
    return {"coord": [list(p) for p in rect.coord], "page_id": rect.page_id}


def _position_to_dict(pos: Position) -> Dict[str, Any]:
    return {
        "coordinates": pos.coordinates,
        "rect": [_rect_to_dict(r) for r in pos.rect],
    }


def _label_info_to_dict(info: LabelInfo) -> Dict[str, Any]:
    return {
        "value": info.value,
        "type": info.type,
        "meta": info.meta,
        "pos": [_position_to_dict(p) for p in info.pos],
    }


def form_res_to_dict(form_res: FormRes) -> Dict[str, Any]:
    """FormRes -> 普通 dict（替代 MessageToJson）。"""
    return {
        "labels": {
            key: {"labels": [_label_info_to_dict(i) for i in val.labels]}
            for key, val in form_res.labels.items()
        }
    }


def form_res_to_json(form_res: FormRes, ensure_ascii: bool = False, indent: int = 2) -> str:
    """FormRes -> JSON 字符串。"""
    return json.dumps(
        form_res_to_dict(form_res), ensure_ascii=ensure_ascii, indent=indent
    )
