# 主抽取协调器
import logging
import time
import json
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from extractor_pdf.utils.llm_client import extract_fields_with_llm
from extractor_pdf.utils.prompt_builder import PromptEngineer
from extractor_pdf.utils.error_handler import ErrorHandler, error_handler, retry_on_error
from extractor_pdf.models.field_config import FieldConfig, FieldType
from extractor_pdf.models.extraction_result import ExtractionResult, ExtractionResponse, ExtractionStatus, FieldValue

class Extractor:
    """主抽取协调器，负责协调整个字段抽取流程"""
    
    def __init__(self, max_workers: int = 5):
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        self.error_handler = ErrorHandler()
        self.prompt_engineer = PromptEngineer()
    
    @error_handler
    def extract_fields(self, formdoc_content: str, field_configs: List[FieldConfig], request_id: str) -> ExtractionResponse:
        """
        执行字段抽取主流程
        
        Args:
            formdoc_content: 合同文档内容
            field_configs: 字段配置列表
            request_id: 请求ID
            
        Returns:
            ExtractionResponse: 抽取响应结果
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"开始处理请求 {request_id}, 字段数量: {len(field_configs)}")
            
            # 1. 调用大模型进行字段抽取
            model_response = self._call_llm_for_extraction(formdoc_content, field_configs)
            
            # 2. 解析模型响应
            results = self._parse_model_response(model_response, field_configs)
            
            # 3. 统计处理结果
            success_count = sum(1 for result in results if result.error_message is None)
            error_count = len(field_configs) - success_count
            
            processing_time = time.time() - start_time
            
            return ExtractionResponse(
                status=ExtractionStatus.SUCCESS if error_count == 0 else ExtractionStatus.PARTIAL_SUCCESS,
                request_id=request_id,
                results=results,
                processing_time=processing_time,
                error_count=error_count,
                success_count=success_count
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"请求 {request_id} 处理失败: {e}")
            
            # 返回错误响应
            return ExtractionResponse(
                status=ExtractionStatus.FAILED,
                request_id=request_id,
                results=[],
                processing_time=processing_time,
                error_count=len(field_configs),
                success_count=0
            )
    
    @retry_on_error(max_retries=3, delay=1.0)
    def _call_llm_for_extraction(self, formdoc_content: str, field_configs: List[FieldConfig]) -> str:
        """调用大模型进行字段抽取"""
        self.logger.debug(f"调用大模型进行字段抽取，文档长度: {len(formdoc_content)}, 字段数: {len(field_configs)}")
        return extract_fields_with_llm(formdoc_content, field_configs)
    
    def _parse_model_response(self, model_response: str, field_configs: List[FieldConfig]) -> List[ExtractionResult]:
        """解析大模型返回的响应"""
        try:
            # 提取 JSON 部分
            json_str = self.prompt_engineer.extract_json_from_response(model_response)
            
            # 解析 JSON
            extracted_data = json.loads(json_str)
            
            results = []
            for field_config in field_configs:
                field_name = field_config.field_name
                raw_value = extracted_data.get(field_name, "")
                
                # 创建抽取结果
                result = self._create_extraction_result(raw_value, field_config)
                results.append(result)
            
            return results
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON 解析失败，使用备用解析: {e}")
            return self._fallback_parsing(model_response, field_configs)
        except Exception as e:
            self.logger.error(f"响应解析失败: {e}")
            raise
    
    def _create_extraction_result(self, raw_value: str, field_config: FieldConfig) -> ExtractionResult:
        """创建抽取结果对象"""
        try:
            # 确保 raw_value 不为 None，如果是 None 则转换为空字符串
            if raw_value is None:
                raw_value = ""
            
            # 处理空值或null
            if not raw_value or raw_value.lower() == "null":
                return ExtractionResult(
                    field_name=field_config.field_name,
                    field_value=FieldValue(raw_value=raw_value),
                    raw_text=raw_value or "null",  # 确保不为 None
                    field_type=field_config.field_type,
                    confidence=0.0,
                    is_intermediate=field_config.is_intermediate,
                    error_message="字段未找到"
                )
            
            # 根据字段类型创建结构化值
            field_value = self._create_structured_value(raw_value, field_config.field_type)
            
            return ExtractionResult(
                field_name=field_config.field_name,
                field_value=field_value,
                raw_text=raw_value,  # 这里已经确保不为 None
                field_type=field_config.field_type,
                confidence=1.0,  # 默认置信度，可根据需要调整
                is_intermediate=field_config.is_intermediate
            )
            
        except Exception as e:
            self.logger.warning(f"创建抽取结果失败: {e}")
            return ExtractionResult(
                field_name=field_config.field_name,
                field_value=FieldValue(raw_value=raw_value or ""),
                raw_text=raw_value or "[创建结果失败]",  # 确保不为 None
                field_type=field_config.field_type,
                confidence=0.0,
                is_intermediate=field_config.is_intermediate,
                error_message=str(e)
            )
    
    def _create_structured_value(self, raw_value: str, field_type: FieldType) -> FieldValue:
        """根据字段类型创建结构化值"""
        field_value = FieldValue(raw_value=raw_value)
        
        try:
            # 使用枚举值的value属性进行比较
            if field_type.value == FieldType.TEXT.value:
                field_value.text = raw_value
            elif field_type.value == FieldType.NUMBER.value:
                try:
                    field_value.number = float(raw_value)
                except ValueError:
                    field_value.text = raw_value
            elif field_type.value == FieldType.AMOUNT.value:
                # 简单金额解析
                try:
                    import re
                    amount_match = re.search(r'[\d,]+\.?\d*', raw_value)
                    if amount_match:
                        amount_str = amount_match.group().replace(',', '')
                        field_value.amount = float(amount_str)
                        
                        currency_match = re.search(r'[￥¥$€£]', raw_value)
                        if currency_match:
                            field_value.currency = currency_match.group()
                        else:
                            field_value.currency = "CNY"
                except:
                    field_value.text = raw_value
            elif field_type.value == FieldType.DATE.value:
                field_value.date = raw_value
            else:
                field_value.text = raw_value
                
        except Exception as e:
            self.logger.warning(f"结构化值创建失败: {e}")
            field_value.text = raw_value
        
        return field_value
    
    def _fallback_parsing(self, model_response: str, field_configs: List[FieldConfig]) -> List[ExtractionResult]:
        """备用解析方法（当JSON解析失败时使用）"""
        results = []
        
        for field_config in field_configs:
            result = ExtractionResult(
                field_name=field_config.field_name,
                field_value=FieldValue(raw_value="[解析失败]"),
                raw_text="[解析失败，请检查模型响应]",
                field_type=field_config.field_type,
                confidence=0.0,
                is_intermediate=field_config.is_intermediate,
                error_message="模型响应解析失败"
            )
            results.append(result)
        
        return results
    
    def batch_extract(self, requests: List[Dict[str, Any]]) -> List[ExtractionResponse]:
        """批量处理多个抽取请求"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_request = {
                executor.submit(
                    self.extract_fields,
                    request['formdoc_content'],
                    request['field_configs'],
                    request.get('request_id', f'batch_{time.time()}_{i}')
                ): request for i, request in enumerate(requests)
            }
            
            # 收集结果
            for future in as_completed(future_to_request):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    request = future_to_request[future]
                    self.logger.error(f"批量处理请求失败: {e}")
                    results.append(ExtractionResponse(
                        status=ExtractionStatus.FAILED,
                        request_id=request.get('request_id', 'unknown'),
                        results=[],
                        processing_time=0.0,
                        error_count=len(request.get('field_configs', [])),
                        success_count=0
                    ))
        
        return results

    def extract_fields_from_window(self, window: List[Dict[str, Any]], 
                                 field_configs: List[FieldConfig], 
                                 request_id: str) -> ExtractionResponse:
        """
        从单个窗口提取字段信息（基于分割而非拼接）
        
        Args:
            window: 窗口数据，包含文本和位置信息
            field_configs: 字段配置列表
            request_id: 请求ID
            
        Returns:
            ExtractionResponse: 抽取响应结果
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"开始处理窗口请求 {request_id}, 字段数量: {len(field_configs)}")
            
            # 提取窗口中的文本内容（不拼接，保持原始结构）
            window_texts = []
            for item in window:
                if 'text' in item and item['text']:
                    window_texts.append(item['text'])
            
            # 使用换行符连接文本，但保持段落结构
            processed_text = "\n".join(window_texts)
            
            # 调用大模型进行字段抽取
            model_response = self._call_llm_for_extraction(processed_text, field_configs)
            
            # 解析模型响应
            results = self._parse_model_response(model_response, field_configs)
            
            # 添加位置信息到结果中
            for result in results:
                if result.raw_text:
                    # 查找原始文本在窗口中的位置信息
                    for item in window:
                        if item.get('text') == result.raw_text and 'pos_id' in item:
                            result.position_info = {
                                'pos_id': item['pos_id'],
                                'window_id': item.get('window_id', 0)
                            }
                            break
            
            # 统计处理结果
            success_count = sum(1 for result in results if result.error_message is None)
            error_count = len(field_configs) - success_count
            
            processing_time = time.time() - start_time
            
            return ExtractionResponse(
                status=ExtractionStatus.SUCCESS if error_count == 0 else ExtractionStatus.PARTIAL_SUCCESS,
                request_id=request_id,
                results=results,
                processing_time=processing_time,
                error_count=error_count,
                success_count=success_count
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"窗口请求 {request_id} 处理失败: {e}")
            
            # 返回错误响应
            return ExtractionResponse(
                status=ExtractionStatus.FAILED,
                request_id=request_id,
                results=[],
                processing_time=processing_time,
                error_count=len(field_configs),
                success_count=0
            )


# 全局提取器实例
global_extractor = Extractor()

def extract_fields(formdoc_content: str, field_configs: List[FieldConfig], request_id: str) -> ExtractionResponse:
    """全局提取函数"""
    return global_extractor.extract_fields(formdoc_content, field_configs, request_id)

def batch_extract(requests: List[Dict[str, Any]]) -> List[ExtractionResponse]:
    """全局批量提取函数"""
    return global_extractor.batch_extract(requests)
