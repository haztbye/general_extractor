# 文本分割模块 - 使用extractor_pdf的窗口分割功能
import logging
from typing import List, Dict, Any
from extractor_pdf.utils.error_handler import error_handler
from extractor_pdf.utils.get_formdoc import PDFWindowProcessor

class TextSplitter:
    """文本分割类，使用PDFWindowProcessor进行窗口分割并保留位置信息"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @error_handler
    def split_text(self, formdoc_content: Any, strategy: str = "window") -> List[List[Dict[str, Any]]]:
        """
        使用窗口分割处理文档内容
        
        Args:
            formdoc_content: 已经解析好的formdoc对象
            strategy: 分割策略，目前只支持 "window"（窗口分割）
            
        Returns:
            List[List[Dict[str, Any]]]: 分割后的窗口列表，每个窗口包含文本和位置信息
            
        Raises:
            ValueError: 如果输入数据无效或策略不支持
        """
        if not formdoc_content:
            raise ValueError("文档内容不能为空")
        
        if strategy != "window":
            raise ValueError(f"不支持的分割策略: {strategy}，请使用 'window'")
        
        # 使用PDFWindowProcessor进行窗口分割
        processor = PDFWindowProcessor(doc=formdoc_content)
        windows = processor.process()
        
        if not windows:
            raise ValueError("窗口分割失败，未生成任何窗口")
        
        self.logger.info(f"窗口分割完成 - 生成窗口数: {len(windows)}")
        return windows
    
    def calculate_optimal_chunk_size(self, text: str, target_chunks: int = 5) -> int:
        """
        计算最优的块大小（兼容性方法）
        实际使用窗口分割，此方法仅用于兼容旧代码
        """
        if not text:
            return 2000  # 默认值
        
        text_length = len(text)
        suggested_size = max(500, text_length // target_chunks)
        
        self.logger.debug(f"计算最优块大小 - 文本长度: {text_length}, 目标块数: {target_chunks}, 建议大小: {suggested_size}")
        return suggested_size


# 全局文本分割器实例
global_text_splitter = TextSplitter()

def split_text(formdoc_content: Any, strategy: str = "window") -> List[List[Dict[str, Any]]]:
    """全局文本分割函数 - 使用窗口分割"""
    return global_text_splitter.split_text(formdoc_content, strategy)

def calculate_optimal_chunk_size(text: str, target_chunks: int = 5) -> int:
    """全局计算最优块大小函数（兼容性方法）"""
    return global_text_splitter.calculate_optimal_chunk_size(text, target_chunks)
