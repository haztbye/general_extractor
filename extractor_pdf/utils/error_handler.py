# 错误处理模块
import logging
import time
from typing import Optional, Callable, Any
from enum import Enum
from functools import wraps


class ErrorLevel(Enum):
    """错误级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCode(Enum):
    """错误代码枚举"""
    # 网络相关错误
    NETWORK_ERROR = "NETWORK_001"
    TIMEOUT_ERROR = "NETWORK_002"
    CONNECTION_ERROR = "NETWORK_003"
    
    # LLM 相关错误
    LLM_API_ERROR = "LLM_001"
    LLM_RATE_LIMIT = "LLM_002"
    LLM_INVALID_RESPONSE = "LLM_003"
    
    # 处理相关错误
    PROCESSING_ERROR = "PROCESS_001"
    PARSING_ERROR = "PROCESS_002"
    VALIDATION_ERROR = "PROCESS_003"
    
    # 配置相关错误
    CONFIG_ERROR = "CONFIG_001"
    MISSING_PARAMETER = "CONFIG_002"
    
    # 未知错误
    UNKNOWN_ERROR = "UNKNOWN_001"


class ExtractionError(Exception):
    """自定义抽取异常基类"""
    
    def __init__(self, 
                 code: ErrorCode, 
                 message: str, 
                 level: ErrorLevel = ErrorLevel.ERROR,
                 details: Optional[dict] = None):
        self.code = code
        self.message = message
        self.level = level
        self.details = details or {}
        self.timestamp = time.time()
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """将异常转换为字典格式"""
        return {
            "code": self.code.value,
            "message": self.message,
            "level": self.level.value,
            "timestamp": self.timestamp,
            "details": self.details
        }
    
    def __str__(self):
        return f"[{self.code.value}] {self.message}"


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, logger_name: str = "extractor_pdf"):
        self.logger = logging.getLogger(logger_name)
    
    def handle_error(self, 
                    error: Exception, 
                    context: Optional[str] = None,
                    raise_exception: bool = True) -> Optional[ExtractionError]:
        """
        处理错误
        
        Args:
            error: 原始异常
            context: 错误上下文信息
            raise_exception: 是否重新抛出异常
            
        Returns:
            Optional[ExtractionError]: 转换后的异常对象
        """
        # 转换错误类型
        extraction_error = self._convert_error(error, context)
        
        # 记录日志
        self._log_error(extraction_error)
        
        if raise_exception:
            raise extraction_error
        return extraction_error
    
    def _convert_error(self, error: Exception, context: Optional[str] = None) -> ExtractionError:
        """将普通异常转换为 ExtractionError"""
        error_details = {
            "original_type": type(error).__name__,
            "context": context,
            "original_message": str(error)
        }
        
        # 根据错误类型映射错误代码
        if isinstance(error, ConnectionError):
            code = ErrorCode.CONNECTION_ERROR
            level = ErrorLevel.ERROR
        elif isinstance(error, TimeoutError):
            code = ErrorCode.TIMEOUT_ERROR
            level = ErrorLevel.WARNING
        elif "rate limit" in str(error).lower():
            code = ErrorCode.LLM_RATE_LIMIT
            level = ErrorLevel.WARNING
        else:
            code = ErrorCode.UNKNOWN_ERROR
            level = ErrorLevel.ERROR
        
        message = f"{context}: {str(error)}" if context else str(error)
        
        return ExtractionError(
            code=code,
            message=message,
            level=level,
            details=error_details
        )
    
    def _log_error(self, error: ExtractionError):
        """根据错误级别记录日志"""
        log_methods = {
            ErrorLevel.DEBUG: self.logger.debug,
            ErrorLevel.INFO: self.logger.info,
            ErrorLevel.WARNING: self.logger.warning,
            ErrorLevel.ERROR: self.logger.error,
            ErrorLevel.CRITICAL: self.logger.critical
        }
        
        log_method = log_methods.get(error.level, self.logger.error)
        log_method(f"{error.code.value}: {error.message}", extra=error.details)


def error_handler(func: Callable) -> Callable:
    """错误处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        handler = ErrorHandler()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 如果已经是 ExtractionError，直接抛出
            if isinstance(e, ExtractionError):
                raise
            # 否则转换并处理
            context = f"Error in {func.__name__}"
            handler.handle_error(e, context)
    return wrapper


def retry_on_error(max_retries: int = 3, 
                  delay: float = 1.0,
                  retryable_errors: Optional[list] = None):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试延迟(秒)
        retryable_errors: 可重试的错误类型列表
    """
    if retryable_errors is None:
        retryable_errors = [ErrorCode.NETWORK_ERROR, ErrorCode.TIMEOUT_ERROR]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler()
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except ExtractionError as e:
                    last_error = e
                    # 检查是否可重试
                    if e.code not in retryable_errors:
                        raise
                    # 记录重试信息
                    handler.logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"due to {e.code.value}"
                    )
                    time.sleep(delay)
                except Exception as e:
                    # 转换非 ExtractionError
                    extraction_error = handler._convert_error(e, f"Attempt {attempt + 1}")
                    last_error = extraction_error
                    if extraction_error.code not in retryable_errors:
                        raise extraction_error
                    handler.logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"due to {extraction_error.code.value}"
                    )
                    time.sleep(delay)
            
            # 所有重试都失败
            if last_error:
                raise last_error
            raise ExtractionError(
                code=ErrorCode.UNKNOWN_ERROR,
                message="All retry attempts failed",
                level=ErrorLevel.ERROR
            )
        return wrapper
    return decorator


# 全局错误处理器实例
global_error_handler = ErrorHandler()

def handle_global_error(error: Exception, context: Optional[str] = None):
    """全局错误处理函数"""
    return global_error_handler.handle_error(error, context, raise_exception=False)
