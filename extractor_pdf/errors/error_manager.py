from typing import Optional
from loguru import logger
import traceback

class ExtractorError(Exception):
    """提取器错误的基类"""
    def __init__(self, message: str, error_code: str = None, original_error: Optional[Exception] = None):
        self.message = message
        self.error_code = error_code or self.__class__.error_code
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self):
        error_msg = f"[{ERROR_CODES[self.error_code]}] {self.message}"
        if self.original_error:
            error_msg += f"\n原始错误: {str(self.original_error)}"
            if hasattr(self.original_error, '__traceback__'):
                error_msg += f"\n堆栈跟踪:\n{''.join(traceback.format_tb(self.original_error.__traceback__))}"
        return error_msg

    def log_error(self, level: str = "error"):
        """记录错误到日志"""
        log_func = getattr(logger, level)
        log_func(str(self))

class ConfigError(ExtractorError):
    """配置相关错误"""
    error_code = "E001"

class FileError(ExtractorError):
    """文件操作相关错误"""
    error_code = "E002"

class PDFProcessError(ExtractorError):
    """PDF处理相关错误"""
    error_code = "E003"

class LLMError(ExtractorError):
    """LLM相关错误"""
    error_code = "E004"

class LLMTimeoutError(LLMError):
    """LLM调用超时错误"""
    error_code = "E004.1"

class LLMResponseError(LLMError):
    """LLM响应解析错误"""
    error_code = "E004.2"

class ToolError(ExtractorError):
    """工具调用相关错误的基类"""
    error_code = "E007"

class ToolNotFoundError(ToolError):
    """工具未找到错误"""
    error_code = "E007.1"

class ToolExecutionError(ToolError):
    """工具执行错误"""
    error_code = "E007.2"

class ToolResponseParseError(ToolError):
    """工具响应解析错误"""
    error_code = "E007.3"

class PromptError(ExtractorError):
    """Prompt相关错误"""
    error_code = "E005"

class WindowProcessError(ExtractorError):
    """窗口处理相关错误"""
    error_code = "E006"

class ExtractError(ExtractorError):
    """抽取相关错误"""
    error_code = "E008"

class RelationError(ExtractorError):
    """关系处理相关错误"""
    error_code = "E009"

class LocateError(ExtractorError):
    """定位相关错误"""
    error_code = "E010"

class JSONProcessError(Exception):
    """JSON处理过程中的自定义异常"""
    error_code = "E011"

def handle_error(default_return=None):
    """
    通用错误处理装饰器
    
    Args:
        default_return: 发生错误时的默认返回值
    
    用法示例:
    @handle_error(default_return=[])
    def process_something():
        # 处理逻辑
        pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ExtractorError as e:
                # 已经是我们的自定义错误，直接记录
                e.log_error()
                logger.error(f"堆栈跟踪:\n{''.join(traceback.format_stack())}")
                return default_return
            except Exception as e:
                # 将其他错误转换为ExtractorError
                error = ExtractorError(
                    message=f"执行 {func.__name__} 时发生未知错误",
                    error_code="E999",
                    original_error=e
                )
                error.log_error()
                logger.error(f"堆栈跟踪:\n{''.join(traceback.format_stack())}")
                return default_return
        return wrapper
    return decorator

# 错误代码速查表
ERROR_CODES = {
    "E001": "配置错误",
    "E002": "文件错误",
    "E003": "PDF处理错误",
    "E004": "LLM错误",
    "E004.1": "LLM超时",
    "E004.2": "LLM响应解析错误",
    "E005": "Prompt错误",
    "E006": "窗口处理错误",
    "E007": "工具调用错误",
    "E007.1": "工具未找到",
    "E007.2": "工具执行错误",
    "E007.3": "工具响应解析错误",
    "E999": "未知错误",
    "E008": "抽取出错",
    "E009": "关系处理错误",
    "E010": "定位错误",
    "E011": "JSON处理错误"
}
