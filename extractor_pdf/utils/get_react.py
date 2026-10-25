from extractor_pdf.document_parsing import form_doc

# def get_section_by_id(doc, section_id):
#     for _, s in form_doc.formdoc_iter(doc, with_table_whole=True):
#         if s.id == section_id:
#             return s
#     return None

def get_char_rects_for_range_by_id(doc, section_id, start_idx, end_idx):
    """
    通过 section_id ,str类型，在文档中查找 section，并提取字符框。
    
    :param doc: 整个文档对象
    :param section_id: 要提取的 section 的 id（字符串）
    :param start_idx: 起始字符索引
    :param end_idx: 结束字符索引
    :return: 字符 bounding box 列表，每个为 [x0, y0, x1, y1]
    """
    section = form_doc.get_section_by_id(doc, section_id)
    if section is None:
        print(f"Section id {section_id} not found.")
        return []

    if not hasattr(section, "char_rects") or len(section.char_rects) == 0:
        print(f"Section {section_id} has no char_rects.")
        return []

    char_rect_list = section.char_rects[0].rect_list

    if start_idx < 0 or end_idx > len(char_rect_list) or start_idx >= end_idx:
        print(f"Invalid index range: [{start_idx}, {end_idx}) for section {section_id}")
        return []

    rects = []
    for i in range(start_idx, end_idx):
        r = char_rect_list[i]
        rect = [r.coord[0], r.coord[1], r.coord[2], r.coord[3]]
        rects.append(rect)

    return rects
