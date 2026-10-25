# 抽取结果数据模型
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from enum import Enum
from .field_config import FieldType


class ExtractionStatus(Enum):
    """抽取状态枚举"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class FieldValue(BaseModel):
    """字段值结构"""
    text: Optional[str] = None
    number: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    date: Optional[str] = None
    raw_value: Optional[str] = None  # 原始文本值


class Position(BaseModel):
    """字段位置信息"""
    page: int = 0
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


class ExtractionResult(BaseModel):
    """抽取结果数据模型"""
    field_name: str                   # 字段名
    field_value: FieldValue           # 结构化字段值
    raw_text: str                     # 原字段值文本
    field_type: FieldType             # 字段类型
    confidence: float = 1.0           # 置信度 (0.0-1.0)
    positions: List[Position] = []    # 字段位置信息
    is_intermediate: bool = False     # 是否为中间字段
    error_message: Optional[str] = None  # 错误信息
    position_info: Optional[Dict[str, Any]] = None  # 窗口内命中段落的 pos_id/window_id


class ExtractionResponse(BaseModel):
    """抽取响应数据模型"""
    status: ExtractionStatus          # 抽取状态
    request_id: str                   # 请求ID
    results: List[ExtractionResult]   # 抽取结果列表
    processing_time: float = 0.0      # 处理时间(秒)
    error_count: int = 0              # 错误数量
    success_count: int = 0            # 成功数量
    
    @property
    def total_count(self) -> int:
        """总字段数量"""
        return len(self.results)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count


class BatchExtractionRequest(BaseModel):
    """批量抽取请求"""
    requests: List[Dict[str, Any]]    # 多个抽取请求
    batch_id: str                     # 批次ID
    priority: int = 1                 # 处理优先级


class BatchExtractionResponse(BaseModel):
    """批量抽取响应"""
    batch_id: str                            # 批次ID
    responses: List[ExtractionResponse]      # 多个抽取响应
    total_processing_time: float = 0.0       # 总处理时间
    total_success_count: int = 0             # 总成功数量
    total_error_count: int = 0               # 总错误数量
    
    @property
    def total_requests(self) -> int:
        """总请求数量"""
        return len(self.responses)
    
    @property
    def overall_success_rate(self) -> float:
        """整体成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.total_success_count / (self.total_success_count + self.total_error_count)
