from typing import List
from extractor_pdf.proto_like import FormRes, LabelInfoList, Position, LabelInfo, Rect
from extractor_pdf.models.document import ExtractResult

def build_form_res(results: List[ExtractResult]) -> FormRes:
    """
    根据已经 merge 过的 ExtractResult 列表，
    直接构造并返回 Protobuf 的 FormRes 对象。
    """
    form_res = FormRes()

    for r in results:
        key = r.item_name
        label_list: LabelInfoList = form_res.labels[key]
        # 新增一个 LabelInfo
        info: LabelInfo = label_list.labels.add()
        raw_pos = r.positions
        for pos in raw_pos:
            p: Position = info.pos.add()
            p.coordinates = str(pos.pos_id)
            # 对于repeated字段，需要使用extend方法添加所有rect
            if hasattr(pos, 'rects') and pos.rects:
                p.rect.extend(pos.rects)  # 直接使用extend方法，更简洁高效
        info.value = str(r.text) or ""
        info.type = r.item_name
        info.meta['extract_data'] = r.result or ""
        # info.suggestion, info.legal_basis, info.value, info.rects
        # 默认就是空集合，不必显式赋值

    return form_res