# 输入处理模块
import logging
import uuid
import re
from typing import List, Dict, Any, Tuple, Union
from extractor_pdf.models.field_config import FieldConfig
from extractor_pdf.utils.error_handler import error_handler

class InputProcessor:
    """输入处理类，负责验证和预处理输入数据"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @error_handler
    def process_input(self, formdoc_content: Union[str, bytes], field_configs: List[FieldConfig], request_id: str = None) -> Tuple[str, List[FieldConfig], str]:
        """
        处理输入数据，包括验证和预处理
        
        Args:
            formdoc_content: 合同文档内容（字符串或PDF字节流）
            field_configs: 字段配置列表
            request_id: 请求ID（可选）
            
        Returns:
            Tuple[str, List[FieldConfig], str]: 处理后的文档内容、字段配置和请求ID
            
        Raises:
            ValueError: 如果输入数据无效
        """
        # 生成或验证请求ID
        processed_request_id = self._validate_or_generate_request_id(request_id)
        
        # 验证和处理文档内容
        if isinstance(formdoc_content, bytes):
            # PDF字节流处理
            processed_content = self._process_pdf_content(formdoc_content)
        else:
            # 文本内容处理
            processed_content = self._validate_and_preprocess_content(formdoc_content)
        
        # 验证字段配置
        processed_field_configs = self._validate_field_configs(field_configs)
        
        self.logger.info(f"输入处理完成 - 请求ID: {processed_request_id}, 文档长度: {len(processed_content)}, 字段数: {len(processed_field_configs)}")
        
        return processed_content, processed_field_configs, processed_request_id
    
    def _validate_or_generate_request_id(self, request_id: str) -> str:
        """验证或生成请求ID"""
        if request_id is None:
            # 生成新的请求ID
            return f"req_{uuid.uuid4().hex[:8]}"
        elif not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("请求ID必须是非空字符串")
        else:
            return request_id.strip()
    
    def _validate_and_preprocess_content(self, formdoc_content: str) -> str:
        """验证和预处理文档内容"""
        if not isinstance(formdoc_content, str):
            raise ValueError("文档内容必须是字符串")
        
        if not formdoc_content.strip():
            raise ValueError("文档内容不能为空")
        
        # 预处理：去除多余空白字符，但保留基本格式
        processed_content = self._clean_content(formdoc_content)
        
        if len(processed_content) < 10:
            self.logger.warning("文档内容非常短，可能影响抽取效果")
        
        return processed_content
    
    def _clean_content(self, content: str) -> str:
        """清理文档内容"""
        # 去除首尾空白
        content = content.strip()
        
        # 合并多个连续空白字符为单个空格
        content = re.sub(r'\s+', ' ', content)
        
        # 去除不可见字符（保留常见标点）
        content = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', content)
        
        return content
    
    def _validate_field_configs(self, field_configs: List[FieldConfig]) -> List[FieldConfig]:
        """验证字段配置"""
        if not isinstance(field_configs, list):
            raise ValueError("字段配置必须是列表")
        
        if not field_configs:
            raise ValueError("字段配置列表不能为空")
        
        valid_configs = []
        for i, config in enumerate(field_configs):
            if not isinstance(config, FieldConfig):
                raise ValueError(f"字段配置索引 {i} 必须是 FieldConfig 对象")
            
            # 验证字段名
            if not config.field_name or not isinstance(config.field_name, str):
                raise ValueError(f"字段配置索引 {i} 的字段名无效")
            
            # 验证字段类型
            if not hasattr(config, 'field_type') or config.field_type is None:
                raise ValueError(f"字段配置索引 {i} 的字段类型无效")
            
            valid_configs.append(config)
        
        # 检查重复字段名
        field_names = [config.field_name for config in valid_configs]
        if len(field_names) != len(set(field_names)):
            duplicate_names = [name for name in field_names if field_names.count(name) > 1]
            raise ValueError(f"发现重复字段名: {list(set(duplicate_names))}")
        
        return valid_configs

    def _process_pdf_content(self, pdf_bytes: bytes) -> str:
        """
        处理PDF字节流，提取文本内容
        
        Args:
            pdf_bytes: PDF文件字节流
            
        Returns:
            str: 提取的文本内容
            
        Raises:
            ValueError: 如果PDF处理失败或内容无效
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise ValueError("PDF内容不能为空")
        
        # 检查是否为有效的PDF文件
        if not self._is_valid_pdf(pdf_bytes):
            raise ValueError("无效的PDF文件格式")
        
        try:
            # 使用本地解析层（PyMuPDF）提取PDF文本内容
            from extractor_pdf.document_parsing import form_doc
            
            # 解析PDF文档
            doc = form_doc.parse(pdf_bytes)
            
            # 提取所有文本内容
            extracted_text = ""
            for _, section in form_doc.formdoc_iter(doc, with_table_whole=True):
                section_text = form_doc.get_section_text(section)
                if section_text:
                    extracted_text += section_text + "\n"
            
            # 验证提取的文本内容
            if not extracted_text or len(extracted_text.strip()) < 10:
                raise ValueError("PDF文档提取的文本内容过少或为空")
            
            # 清理和预处理文本内容
            cleaned_text = self._clean_content(extracted_text)
            
            self.logger.info(f"PDF处理成功，提取文本长度: {len(cleaned_text)}")
            return cleaned_text
            
        except ImportError as e:
            self.logger.error(f"PDF处理依赖缺失: {e}")
            raise ValueError("PDF处理功能不可用")
        except Exception as e:
            self.logger.error(f"PDF处理失败: {e}")
            raise ValueError(f"PDF文档处理失败: {str(e)}")
    
    def _is_valid_pdf(self, content: bytes) -> bool:
        """
        检查是否为有效的PDF文件
        
        Args:
            content: 文件内容字节流
            
        Returns:
            bool: 是否为有效的PDF文件
        """
        # 检查PDF文件签名
        if len(content) < 4:
            return False
        
        # PDF文件签名: %PDF
        if content[:4] == b'%PDF':
            return True
        
        # 检查文件扩展名或内容中是否包含PDF标识
        if b'%PDF' in content[:1024]:  # 检查前1KB内容
            return True
        
        return False
    
    def batch_process_inputs(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理多个输入请求
        
        Args:
            requests: 请求列表，每个请求包含 formdoc_content 和 field_configs
            
        Returns:
            List[Dict[str, Any]]: 处理后的请求列表，包含 processed_content, processed_field_configs, request_id
        """
        processed_requests = []
        
        for i, request in enumerate(requests):
            try:
                formdoc_content = request.get('formdoc_content', '')
                field_configs = request.get('field_configs', [])
                request_id = request.get('request_id')
                
                processed_content, processed_field_configs, processed_request_id = self.process_input(
                    formdoc_content, field_configs, request_id
                )
                
                processed_requests.append({
                    'formdoc_content': processed_content,
                    'field_configs': processed_field_configs,
                    'request_id': processed_request_id
                })
                
            except Exception as e:
                self.logger.error(f"批量处理请求索引 {i} 失败: {e}")
                # 可以选择跳过失败请求或重新抛出异常
                raise
        
        return processed_requests


# 全局输入处理器实例
global_input_processor = InputProcessor()

def process_input(formdoc_content: Union[str, bytes], field_configs: List[FieldConfig], request_id: str = None) -> Tuple[str, List[FieldConfig], str]:
    """全局输入处理函数"""
    return global_input_processor.process_input(formdoc_content, field_configs, request_id)

def batch_process_inputs(requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """全局批量输入处理函数"""
    return global_input_processor.batch_process_inputs(requests)

