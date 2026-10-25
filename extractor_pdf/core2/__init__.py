# core 模块初始化文件
"""
核心抽取模块 - 包含输入处理、文本分割、并行处理和结果合并功能
"""

from .input_processor import InputProcessor, process_input, batch_process_inputs
from .text_splitter import TextSplitter, split_text, calculate_optimal_chunk_size
from .parallel_extractor import ParallelExtractor, parallel_extract, batch_extract_with_callback
from .result_merger import ResultMerger, merge_results, merge_responses
from .general_extractor import Extractor, extract_fields, batch_extract

__all__ = [
    'InputProcessor', 'process_input', 'batch_process_inputs',
    'TextSplitter', 'split_text', 'calculate_optimal_chunk_size',
    'ParallelExtractor', 'parallel_extract', 'batch_extract_with_callback',
    'ResultMerger', 'merge_results', 'merge_responses',
    'Extractor', 'extract_fields', 'batch_extract'
]