# 并行处理模块
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional
from extractor_pdf.utils.error_handler import error_handler
from extractor_pdf.models.extraction_result import ExtractionResponse

class ParallelExtractor:
    """并行处理类，负责管理并发抽取任务"""
    
    def __init__(self, max_workers: int = 5, timeout: int = 30):
        """
        初始化并行处理器
        
        Args:
            max_workers: 最大工作线程数
            timeout: 单个任务超时时间（秒）
        """
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        self.timeout = timeout
    
    @error_handler
    def parallel_extract(self, extract_func: Callable, tasks: List[Dict[str, Any]]) -> List[ExtractionResponse]:
        """
        并行执行多个抽取任务
        
        Args:
            extract_func: 抽取函数，接受参数 (formdoc_content, field_configs, request_id)
            tasks: 任务列表，每个任务包含 formdoc_content, field_configs, request_id
            
        Returns:
            List[ExtractionResponse]: 所有任务的抽取结果列表
        """
        if not tasks:
            self.logger.warning("任务列表为空，无需处理")
            return []
        
        start_time = time.time()
        results = []
        successful_tasks = 0
        failed_tasks = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务到线程池
            future_to_task = {}
            for task in tasks:
                future = executor.submit(
                    self._execute_single_task,
                    extract_func,
                    task.get('formdoc_content', ''),
                    task.get('field_configs', []),
                    task.get('request_id')
                )
                future_to_task[future] = task
            
            # 收集结果
            for future in as_completed(future_to_task.keys()):
                task = future_to_task[future]
                request_id = task.get('request_id', 'unknown')
                
                try:
                    result = future.result(timeout=self.timeout)
                    results.append(result)
                    successful_tasks += 1
                    self.logger.debug(f"任务完成 - 请求ID: {request_id}, 状态: {result.status}")
                except Exception as e:
                    failed_tasks += 1
                    self.logger.error(f"任务失败 - 请求ID: {request_id}, 错误: {e}")
                    # 创建错误响应
                    error_response = ExtractionResponse(
                        status="FAILED",
                        request_id=request_id,
                        results=[],
                        processing_time=0.0,
                        error_count=len(task.get('field_configs', [])),
                        success_count=0
                    )
                    results.append(error_response)
        
        processing_time = time.time() - start_time
        self.logger.info(
            f"并行处理完成 - 总任务数: {len(tasks)}, "
            f"成功: {successful_tasks}, 失败: {failed_tasks}, "
            f"总耗时: {processing_time:.2f}秒"
        )
        
        return results
    
    def _execute_single_task(self, extract_func: Callable, formdoc_content: str, 
                           field_configs: List, request_id: Optional[str] = None) -> ExtractionResponse:
        """
        执行单个抽取任务
        
        Args:
            extract_func: 抽取函数
            formdoc_content: 文档内容
            field_configs: 字段配置
            request_id: 请求ID
            
        Returns:
            ExtractionResponse: 抽取结果
        """
        if request_id is None:
            request_id = f"task_{time.time()}_{id(formdoc_content)}"
        
        try:
            return extract_func(formdoc_content, field_configs, request_id)
        except Exception as e:
            self.logger.error(f"执行单个任务失败 - 请求ID: {request_id}, 错误: {e}")
            raise
    
    def batch_extract_with_callback(self, extract_func: Callable, tasks: List[Dict[str, Any]], 
                                  callback: Optional[Callable] = None) -> List[ExtractionResponse]:
        """
        批量处理抽取任务，支持回调函数
        
        Args:
            extract_func: 抽取函数
            tasks: 任务列表
            callback: 回调函数，在每个任务完成后调用，参数为 (result, task)
            
        Returns:
            List[ExtractionResponse]: 所有任务的抽取结果
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(
                    self._execute_single_task,
                    extract_func,
                    task['formdoc_content'],
                    task['field_configs'],
                    task.get('request_id')
                ): task for task in tasks
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result(timeout=self.timeout)
                    results.append(result)
                    
                    # 调用回调函数
                    if callback:
                        callback(result, task)
                        
                except Exception as e:
                    self.logger.error(f"任务处理失败: {e}")
                    error_response = ExtractionResponse(
                        status="FAILED",
                        request_id=task.get('request_id', 'unknown'),
                        results=[],
                        processing_time=0.0,
                        error_count=len(task.get('field_configs', [])),
                        success_count=0
                    )
                    results.append(error_response)
        
        return results
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """
        获取执行统计信息（可用于监控）
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "max_workers": self.max_workers,
            "timeout": self.timeout,
            "timestamp": time.time()
        }
    
    def adjust_workers_based_on_load(self, pending_tasks: int) -> int:
        """
        基于负载动态调整工作线程数
        
        Args:
            pending_tasks: 待处理任务数
            
        Returns:
            int: 建议的工作线程数
        """
        if pending_tasks <= 0:
            return 1
        
        # 简单的负载均衡策略：每个工作线程处理最多10个任务
        suggested_workers = min(self.max_workers, max(1, pending_tasks // 10))
        
        self.logger.debug(
            f"负载调整建议 - 待处理任务: {pending_tasks}, "
            f"当前最大工作线程: {self.max_workers}, "
            f"建议工作线程: {suggested_workers}"
        )
        
        return suggested_workers


# 全局并行处理器实例
global_parallel_extractor = ParallelExtractor()

def parallel_extract(extract_func: Callable, tasks: List[Dict[str, Any]]) -> List[ExtractionResponse]:
    """全局并行抽取函数"""
    return global_parallel_extractor.parallel_extract(extract_func, tasks)

def batch_extract_with_callback(extract_func: Callable, tasks: List[Dict[str, Any]], 
                              callback: Optional[Callable] = None) -> List[ExtractionResponse]:
    """全局批量抽取带回调函数"""
    return global_parallel_extractor.batch_extract_with_callback(extract_func, tasks, callback)
