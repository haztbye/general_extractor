"""动态字段提取器，用于集成通用抽取功能"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from extractor_pdf.core2.general_extractor import Extractor as Core2Extractor
from extractor_pdf.models.field_config import FieldConfig, FieldType
from extractor_pdf.models.extraction_result import ExtractionResponse, ExtractionResult, ExtractionStatus
from extractor_pdf.utils.get_formdoc import PDFWindowProcessor


class DynamicExtractor:
    """动态字段提取器，支持基于字段配置的灵活提取"""
    
    def __init__(self):
        self.core2_extractor = Core2Extractor()
        self.logger = logger
    
    async def extract_from_window(self, window: List[Dict[str, Any]], 
                                field_configs: List[FieldConfig],
                                window_id: int) -> Dict[str, Any]:
        """
        从单个窗口提取字段信息（基于分割而非拼接）
        
        Args:
            window: 窗口数据，包含文本和位置信息
            field_configs: 字段配置列表
            window_id: 窗口ID
            
        Returns:
            包含提取结果和位置信息的字典
        """
        try:
            # 不再拼接文本，保持窗口原始结构进行提取
            # 调用 core2 通用提取器，传递整个窗口结构
            request_id = f"window_{window_id}_{int(asyncio.get_event_loop().time())}"
            response = await asyncio.to_thread(
                self.core2_extractor.extract_fields_from_window,
                window,  # 传递整个窗口而不是拼接的文本
                field_configs,
                request_id
            )
            
            # 转换为标准格式并添加位置信息
            return self._format_extraction_result(response, window, window_id)
            
        except Exception as e:
            self.logger.error(f"窗口 {window_id} 提取失败: {str(e)}")
            return self._create_error_result(field_configs, window_id, str(e))
    
    def _format_extraction_result(self, response: ExtractionResponse,
                                window: List[Dict[str, Any]],
                                window_id: int) -> Dict[str, Any]:
        """格式化提取结果，添加位置信息"""
        result = {
            'window_id': window_id,
            'status': response.status.value,
            'results': {},
            'position_info': self._extract_position_info(window)
        }
        
        # 处理每个字段的提取结果
        for extraction_result in response.results:
            field_name = extraction_result.field_name
            result['results'][field_name] = {
                'value': extraction_result.raw_text,
                'confidence': extraction_result.confidence,
                'error': extraction_result.error_message,
                'field_type': extraction_result.field_type.value if extraction_result.field_type else None
            }
        
        return result
    
    def _extract_position_info(self, window: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从窗口中提取位置信息"""
        position_info = {}
        for item in window:
            if 'pos_id' in item:
                position_info[item['pos_id']] = {
                    'text': item.get('text', ''),
                    'window_id': item.get('window_id', 0)
                }
        return position_info
    
    def _create_error_result(self, field_configs: List[FieldConfig],
                           window_id: int, error_msg: str) -> Dict[str, Any]:
        """创建错误结果"""
        result = {
            'window_id': window_id,
            'status': 'ERROR',
            'results': {},
            'position_info': {},
            'error': error_msg
        }
        
        # 为所有字段创建错误结果
        for field_config in field_configs:
            result['results'][field_config.field_name] = {
                'value': None,
                'confidence': 0.0,
                'error': error_msg,
                'field_type': field_config.field_type.value if field_config.field_type else None
            }
        
        return result
    
    async def batch_extract_from_windows(self, windows: List[List[Dict[str, Any]]],
                                       field_configs: List[FieldConfig]) -> List[Dict[str, Any]]:
        """
        批量从多个窗口提取字段信息
        
        Args:
            windows: 窗口列表
            field_configs: 字段配置列表
            
        Returns:
            所有窗口的提取结果列表
        """
        tasks = []
        for i, window in enumerate(windows):
            task = self.extract_from_window(window, field_configs, i + 1)
            tasks.append(task)
        
        # 并行处理所有窗口
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"窗口 {i + 1} 处理异常: {str(result)}")
                final_results.append(
                    self._create_error_result(field_configs, i + 1, str(result))
                )
            else:
                final_results.append(result)
        
        return final_results


# 全局动态提取器实例
global_dynamic_extractor = DynamicExtractor()


async def extract_fields_from_windows(windows: List[List[Dict[str, Any]]],
                                    field_configs: List[FieldConfig]) -> List[Dict[str, Any]]:
    """
    从多个窗口提取字段信息的全局函数
    
    Args:
        windows: 窗口列表
        field_configs: 字段配置列表
        
    Returns:
        所有窗口的提取结果列表
    """
    return await global_dynamic_extractor.batch_extract_from_windows(windows, field_configs)


def create_field_config(field_name: str, field_type: FieldType, 
                       description: str = "", example: str = "") -> FieldConfig:
    """
    创建字段配置的辅助函数
    
    Args:
        field_name: 字段名称
        field_type: 字段类型
        description: 字段描述
        example: 提取示例
        
    Returns:
        FieldConfig对象
    """
    return FieldConfig(
        field_name=field_name,
        field_type=field_type,
        field_description=description,
        extraction_example=example
    )
