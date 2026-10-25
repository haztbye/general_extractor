# 结果合并模块
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from extractor_pdf.models.extraction_result import ExtractionResult, ExtractionResponse
from extractor_pdf.utils.error_handler import error_handler

class ResultMerger:
    """结果合并类，负责合并多个抽取结果"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @error_handler
    def merge_results(self, chunk_results: List[List[ExtractionResult]], 
                     original_text: str = None) -> List[ExtractionResult]:
        """
        合并多个chunk的抽取结果
        
        Args:
            chunk_results: 每个chunk的抽取结果列表
            original_text: 原始文本（可选，用于上下文验证）
            
        Returns:
            List[ExtractionResult]: 合并后的最终结果
        """
        if not chunk_results:
            self.logger.warning("没有需要合并的结果")
            return []
        
        # 如果只有一个chunk，直接返回
        if len(chunk_results) == 1:
            return chunk_results[0]
        
        # 按字段名分组所有结果
        field_results = self._group_results_by_field(chunk_results)
        
        # 合并每个字段的结果
        merged_results = []
        for field_name, results in field_results.items():
            merged_result = self._merge_field_results(field_name, results, original_text)
            merged_results.append(merged_result)
        
        self.logger.info(f"结果合并完成 - 原始chunk数: {len(chunk_results)}, 合并后字段数: {len(merged_results)}")
        return merged_results
    
    def _group_results_by_field(self, chunk_results: List[List[ExtractionResult]]) -> Dict[str, List[ExtractionResult]]:
        """按字段名分组结果"""
        field_results = defaultdict(list)
        
        for chunk_index, results in enumerate(chunk_results):
            for result in results:
                field_results[result.field_name].append({
                    'result': result,
                    'chunk_index': chunk_index
                })
        
        return field_results
    
    def _merge_field_results(self, field_name: str, results: List[Dict], 
                           original_text: str = None) -> ExtractionResult:
        """合并单个字段的多个结果"""
        if not results:
            return self._create_empty_result(field_name)
        
        # 如果只有一个结果，直接返回
        if len(results) == 1:
            return results[0]['result']
        
        # 收集所有非空结果
        non_null_results = []
        for result_info in results:
            result = result_info['result']
            if result.raw_text and result.raw_text.lower() != 'null':
                non_null_results.append(result_info)
        
        # 如果没有非空结果，返回第一个结果（可能是null）
        if not non_null_results:
            return results[0]['result']
        
        # 如果只有一个非空结果，返回它
        if len(non_null_results) == 1:
            return non_null_results[0]['result']
        
        # 多个非空结果，需要选择最优结果
        return self._select_best_result(field_name, non_null_results, original_text)
    
    def _select_best_result(self, field_name: str, results: List[Dict], 
                          original_text: str = None) -> ExtractionResult:
        """选择最优的结果（基于置信度、位置等）"""
        # 按置信度排序（降序）
        sorted_results = sorted(results, key=lambda x: x['result'].confidence, reverse=True)
        
        # 选择置信度最高的结果
        best_result_info = sorted_results[0]
        best_result = best_result_info['result']
        
        # 检查是否有多个高置信度结果
        high_confidence_results = [
            r for r in sorted_results 
            if r['result'].confidence >= best_result.confidence * 0.9  # 90%以上的置信度
        ]
        
        if len(high_confidence_results) > 1:
            # 多个高置信度结果，需要进一步选择
            best_result = self._resolve_conflicts(field_name, high_confidence_results, original_text)
        
        # 更新结果元数据，标记为合并结果
        best_result.is_merged = True
        best_result.merged_from = len(results)
        
        return best_result
    
    def _resolve_conflicts(self, field_name: str, results: List[Dict], 
                         original_text: str = None) -> ExtractionResult:
        """解决字段结果冲突"""
        # 策略1: 选择出现在最早chunk中的结果（假设重要信息在前面）
        earliest_result = min(results, key=lambda x: x['chunk_index'])
        
        # 策略2: 如果提供了原始文本，验证结果的上下文
        if original_text:
            validated_result = self._validate_with_context(field_name, results, original_text)
            if validated_result:
                return validated_result['result']
        
        # 策略3: 选择最长的结果（可能包含更完整的信息）
        longest_result = max(results, key=lambda x: len(x['result'].raw_text))
        
        # 默认返回最早的结果
        self.logger.debug(f"字段 '{field_name}' 有 {len(results)} 个冲突结果，选择最早chunk的结果")
        return earliest_result['result']
    
    def _validate_with_context(self, field_name: str, results: List[Dict], 
                             original_text: str) -> Optional[Dict]:
        """使用原始文本上下文验证结果"""
        # 简单的验证：检查结果是否确实出现在原始文本中
        valid_results = []
        
        for result_info in results:
            result = result_info['result']
            if result.raw_text and result.raw_text in original_text:
                valid_results.append(result_info)
        
        if valid_results:
            # 返回第一个有效结果
            return valid_results[0]
        
        return None
    
    def _create_empty_result(self, field_name: str) -> ExtractionResult:
        """创建空结果"""
        return ExtractionResult(
            field_name=field_name,
            field_value=None,
            raw_text="null",
            field_type=None,
            confidence=0.0,
            is_intermediate=False,
            error_message="字段未在任何chunk中找到"
        )
    
    def merge_responses(self, chunk_responses: List[ExtractionResponse]) -> ExtractionResponse:
        """
        合并多个ExtractionResponse
        
        Args:
            chunk_responses: 每个chunk的响应列表
            
        Returns:
            ExtractionResponse: 合并后的响应
        """
        if not chunk_responses:
            return ExtractionResponse(
                status="FAILED",
                request_id="merged_unknown",
                results=[],
                processing_time=0.0,
                error_count=0,
                success_count=0
            )
        
        # 提取所有结果
        all_results = [response.results for response in chunk_responses]
        
        # 合并结果
        merged_results = self.merge_results(all_results)
        
        # 计算统计信息
        total_processing_time = sum(response.processing_time for response in chunk_responses)
        total_error_count = sum(response.error_count for response in chunk_responses)
        total_success_count = sum(response.success_count for response in chunk_responses)
        
        # 确定整体状态
        if total_success_count == 0:
            status = "FAILED"
        elif total_error_count > 0:
            status = "PARTIAL_SUCCESS"
        else:
            status = "SUCCESS"
        
        # 使用第一个响应的request_id作为合并后的request_id
        request_id = chunk_responses[0].request_id if chunk_responses else "merged_unknown"
        
        return ExtractionResponse(
            status=status,
            request_id=request_id,
            results=merged_results,
            processing_time=total_processing_time,
            error_count=total_error_count,
            success_count=total_success_count
        )
    
    def calculate_overall_confidence(self, results: List[ExtractionResult]) -> float:
        """
        计算整体置信度
        
        Args:
            results: 抽取结果列表
            
        Returns:
            float: 平均置信度
        """
        if not results:
            return 0.0
        
        valid_confidences = [result.confidence for result in results if result.confidence > 0]
        if not valid_confidences:
            return 0.0
        
        return sum(valid_confidences) / len(valid_confidences)


# 全局结果合并器实例
global_result_merger = ResultMerger()

def merge_results(chunk_results: List[List[ExtractionResult]], 
                 original_text: str = None) -> List[ExtractionResult]:
    """全局结果合并函数"""
    return global_result_merger.merge_results(chunk_results, original_text)

def merge_responses(chunk_responses: List[ExtractionResponse]) -> ExtractionResponse:
    """全局响应合并函数"""
    return global_result_merger.merge_responses(chunk_responses)
