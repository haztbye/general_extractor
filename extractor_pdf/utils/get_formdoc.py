from loguru import logger
import traceback
import os
import time
from collections import defaultdict
from extractor_pdf.document_parsing import form_doc
from typing import Dict, List, Optional, Any

class PDFWindowProcessor:
    """
    处理 PDF 文件，将其内容按滑动窗口提取为字符串列表。
    """
    def __init__(self, doc, window_size=6, overlap=1):
        """
        初始化处理器。

        Args:
            pdf_path (str): PDF文件的路径
            doc: 已经解析好的formdoc。
            window_size (int): 每个窗口包含的页数。
            overlap (int): 窗口之间的重叠页数。
        """
        self.doc = doc
        self.window_size = window_size
        if overlap >= window_size:
            overlap = 1
            raise ValueError("Overlap must be less than window size.")
        self.overlap = overlap
        self.stride = self.window_size - self.overlap
        self.pages_sections = defaultdict(list)
        self.max_page = -1
        self.windows = []
        self.window_outputs = []
        self.position_mapping = {}

    def _group_sections_by_page(self):
        """将解析后的 sections 按页码分组。"""
        if not self.doc:
            logger.error("No document parsed yet.")
            return False
            
        # print("--- Grouping sections by page ---")
        self.pages_sections.clear()
        self.max_page = -1
        
        for _, s in form_doc.formdoc_iter(self.doc, with_table_whole=True):
            if s.rects: # Ensure section has position info
                page_num = s.rects[0].page_id # page_id is 0-based
                self.pages_sections[page_num].append(s)
                self.max_page = max(self.max_page, page_num)
            else:
                # Handle sections without rects if necessary
                pass 

        if self.max_page == -1:
            logger.warning("Could not determine page numbers from the document or document is empty/has no positioned elements.")
            # Decide if this is an error or just an empty doc case
            return False # If it's considered an error state
        
        # print(f"--- Document has {self.max_page + 1} pages ---")
        return True

    def _define_windows(self):
        """根据页数、窗口大小和重叠定义处理窗口。"""
        if self.max_page == -1:
             logger.warning("Cannot define windows as max page is unknown.")
             return False
             
        self.windows = []
        current_page = 0 
        while current_page <= self.max_page:
            start_page = current_page
            end_page = current_page + self.window_size - 1
            actual_end_page = min(end_page, self.max_page)

            if actual_end_page - start_page == 0 and self.windows:
                break
            
            self.windows.append((start_page, actual_end_page))
            
            next_start_page = start_page + self.stride
            if next_start_page > self.max_page:
                break
            current_page = next_start_page
            
        return True

    def _process_position_mapping(self, element: Any, element_id: str) -> None:
        """处理元素的位置映射信息。"""
        if hasattr(element, 'id'):
            self.position_mapping[element_id] = {
                'rects': element.rects,
                'char_rects': element.char_rects if hasattr(element, 'char_rects') else None
            }

    def _create_window_line(self, text: str, pos_id: str, window_id: int) -> Dict[str, Any]:
        """创建窗口行数据。"""
        return {
            'text': text,
            'pos_id': pos_id,
            'window_id': window_id
        }

    def _process_table_cell(self, cell: Any, window_id: int) -> List[Dict[str, Any]]:
        """处理表格单元格内容。"""
        cell_lines = []
        for p in cell.children:
            if hasattr(p, 'id'):
                self._process_position_mapping(p, p.id)
                p_text = form_doc.get_section_text(p)
                cell_lines.append(self._create_window_line(p_text, p.id, window_id))
        return cell_lines

    def _process_windows(self) -> bool:
        """遍历窗口，提取每个窗口的内容为字符串。"""
        if not self.windows:
            logger.warning("No windows defined to process.")
            return False
            
        self.window_outputs = [] 
        for i, (start, end) in enumerate(self.windows):
            window_sections = []
            page_section_indices = {}
            
            # 收集窗口范围内的所有sections
            for page_num in range(start, end + 1):
                if page_num in self.pages_sections:
                    for idx, s in enumerate(self.pages_sections[page_num]):
                        page_section_indices[id(s)] = idx + 1  # 行号从1开始
                    window_sections.extend(self.pages_sections[page_num])
            
            if not window_sections:
                continue

            current_window_lines = []
            window_id = i + 1
            for section in window_sections:
                if form_doc.is_table(section):
                    # 处理表格
                    for row in section.table.rows:
                        for cell in row.cells:
                            current_window_lines.extend(self._process_table_cell(cell, window_id))
                    continue
                
                # 处理普通文本
                if hasattr(section, 'id'):
                    self._process_position_mapping(section, section.id)
                    section_text = form_doc.get_section_text(section)
                    current_window_lines.append(self._create_window_line(section_text, section.id, window_id))

            self.window_outputs.append(current_window_lines)
        
        return True

    def process(self):
        """
        执行完整的处理流程：解析、分组、定义窗口、处理窗口。
        
        Returns:
            list[str] or None: 包含每个窗口内容的字符串列表，如果处理失败则返回 None。
        """
        if not self.doc:
            return None
        if not self._group_sections_by_page():
             # Decide how to handle this - maybe return empty list if doc was just empty?
             # For now, returning None if grouping failed significantly
             if self.max_page == -1: 
                 logger.error("Processing stopped: Could not group sections by page.")
                 return None 
        if not self._define_windows():
             # If max_page was 0 or -1, windows might be empty, which is okay.
             # Only return None if defining windows failed unexpectedly.
             # Let _process_windows handle the case of empty self.windows list.
             pass
        if not self._process_windows():
             # Handle potential failure in processing windows
             logger.error("Processing stopped: Failed during window content extraction.")
             return None # Or return partially processed data if desired
        return self.window_outputs

    def get_window_outputs(self):
        """返回处理后的窗口内容列表。"""
        return self.window_outputs

    def print_window_outputs(self):
         """打印收集到的窗口内容。"""
         if not self.window_outputs:
             print("\nNo window outputs to print.")
             return
             
         print("\n--- Collected Window Contents ---")
         for idx, content in enumerate(self.window_outputs):
             print(f"--- Content for Window {idx + 1} ---")
             print(content)
             print("-" * 30) # Separator

    def get_position_info(self, section_id):
        """
        获取指定ID的位置信息。
        """
        if section_id not in self.position_mapping:
            return None
        return self.position_mapping[section_id]

if __name__ == '__main__':
    # 本地自检示例：解析合成示例合同并打印窗口输出
    import os
    sample = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'examples', 'sample_contract.pdf'
    )
    try:
        from extractor_pdf.document_parsing import new_formdoc_from_path
        doc = new_formdoc_from_path(sample)
        processor = PDFWindowProcessor(doc=doc)
        output_windows = processor.process()
        print(output_windows)
    except Exception:
        logger.error(traceback.format_exc())
