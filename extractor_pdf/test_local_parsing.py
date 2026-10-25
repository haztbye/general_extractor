"""本地解析层测试：PDF / DOCX -> FormDoc -> 窗口切分全链路（不调 LLM）。

运行: python extractor_pdf/test_local_parsing.py [文件路径]
"""

import os
import sys

# 支持从任意目录直接运行本脚本
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractor_pdf.document_parsing import form_doc, new_formdoc_from_path
from extractor_pdf.utils.get_formdoc import PDFWindowProcessor
from extractor_pdf.core.window_processor import process_window_text

DEFAULT_PDF = "examples/sample_contract.pdf"


def check_doc(path: str) -> None:
    print(f"\n===== 解析: {path} =====")
    doc = new_formdoc_from_path(path)

    paras, tables, mismatch = 0, 0, 0
    for _, s in form_doc.formdoc_iter(doc, with_table_whole=True):
        if form_doc.is_table(s):
            tables += 1
            for row in s.table.rows:
                for cell in row.cells:
                    for ch in cell.children:
                        if ch.char_rects and len(ch.char_rects[0].rect_list) != len(ch.text):
                            mismatch += 1
        else:
            paras += 1
            if s.char_rects and len(s.char_rects[0].rect_list) != len(s.text):
                mismatch += 1

    print(f"段落: {paras}, 表格: {tables}, char_rects/text 长度不一致: {mismatch}")
    assert paras + tables > 0, "解析结果为空"
    assert mismatch == 0, "存在字符框与文本长度不一致的段落"

    processor = PDFWindowProcessor(doc=doc)
    windows = processor.process() or []
    print(f"窗口数量: {len(windows)}")
    total = sum(len(process_window_text(wd)) for wd in windows)
    print(f"窗口文本总字符数: {total}")
    assert total > 0, "窗口文本为空"
    print(">>> 通过")


if __name__ == "__main__":
    paths = sys.argv[1:] or [DEFAULT_PDF]
    for p in paths:
        check_doc(p)
    print("\n全部通过 ✅")
