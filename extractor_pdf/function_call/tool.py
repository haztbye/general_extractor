import asyncio
from extractor_pdf.errors.error_manager import ToolExecutionError

class Tool:
    def __init__(self, name: str, description: str, func: callable):
        self.name = name
        self.description = description
        self.func = func
    
    async def run(self, *args, **kwargs):
        try:
            return await self.func(*args, **kwargs) if asyncio.iscoroutinefunction(self.func) else self.func(*args, **kwargs)
        except Exception as e:
            raise ToolExecutionError(
                message=f"执行工具 {self.name} 时发生错误",
                original_error=e
            ) 