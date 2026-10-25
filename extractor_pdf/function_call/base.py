from extractor_pdf.utils.llm import get_llm_response_async
from extractor_pdf.utils.prompt_manager import prompt_manager
from extractor_pdf.errors.error_manager import (
    ToolNotFoundError,
    ToolResponseParseError,
    handle_error
)
from extractor_pdf.function_call.tool import Tool
import asyncio
import json
import re

class ToolManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        from extractor_pdf.function_call.tools import ToolRegistry
        self.tools = ToolRegistry.get_tools()
        self._initialized = True
        
    @classmethod
    def get_instance(cls):
        """获取ToolManager的单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register_tool(self, tool: Tool):
        """手动注册工具（不推荐，优先使用装饰器注册）"""
        self.tools[tool.name] = tool
    
    async def run_tool(self, tool_name: str, *args, **kwargs):
        if tool_name not in self.tools:
            raise ToolNotFoundError(f"工具 {tool_name} 未找到")
        return await self.tools[tool_name].run(*args, **kwargs)
    
    @handle_error(default_return=None)
    async def process_query(self, query: str):
        # 1. 调用 LLM 解析用户查询，确定使用哪个工具
        tool_name, tool_args = await self._parse_query(query)
        # 2. 执行相应的工具
        return await self.run_tool(tool_name, **tool_args)
    
    async def _parse_query(self, query: str):
        # 构造 prompt，让 LLM 选择合适的工具
        tools_desc = "\n".join([f"{name}: {tool.description}" for name, tool in self.tools.items()])
        # print(f"tools_desc >>> {tools_desc}")
        prompt = prompt_manager.get_prompt("get_tool").format(tools_desc=tools_desc, query=query)
        # print(f"prompt >>> {prompt}")
        response = await get_llm_response_async(prompt=prompt)
        # print(f"response >>> {response}")
        # 解析 LLM 的响应，返回工具名和参数
        return self._parse_llm_response(response)

    def _parse_llm_response(self, response: str) -> tuple[str, dict]:
        """
        解析LLM的响应，提取工具名称和参数

        Args:
            response: LLM的响应文本，应该是JSON格式

        Returns:
            tuple[str, dict]: 返回工具名和参数字典
        """
        try:
            # 清理响应文本，移除可能的markdown代码块标记
            cleaned_response = response.strip()
            cleaned_response = re.sub(r'^```(json)?\s*', '', cleaned_response)
            cleaned_response = cleaned_response.strip()
            
            # 处理单引号问题：将Python字典字符串转换为标准JSON
            try:
                # 首先尝试直接解析
                data = json.loads(cleaned_response)
            except json.JSONDecodeError:
                # 如果失败，尝试将Python字典字符串转换为JSON
                # 使用ast.literal_eval安全地评估Python字面量
                import ast
                data = ast.literal_eval(cleaned_response)
            
            if not isinstance(data, dict):
                raise ToolResponseParseError("响应格式错误：不是一个JSON对象")
            
            if "tool" not in data:
                raise ToolResponseParseError("响应格式错误：缺少'tool'字段")
            
            if "parameters" not in data:
                raise ToolResponseParseError("响应格式错误：缺少'parameters'字段")
            
            if not isinstance(data["parameters"], dict):
                raise ToolResponseParseError("响应格式错误：'parameters'不是一个对象")
            
            return data["tool"], data["parameters"]
            
        except (json.JSONDecodeError, SyntaxError) as e:
            raise ToolResponseParseError(f"JSON解析错误：{str(e)}")
        except Exception as e:
            if isinstance(e, ToolResponseParseError):
                raise
            raise ToolResponseParseError(f"解析响应时出错：{str(e)}")


tool_manager = ToolManager.get_instance()

async def main():
    query = "不含税金额是十万元，税率是13%，请计算含税金额。"
    result = await tool_manager.process_query(query)
    print(f"结果: {result}")

if __name__ == "__main__":
    asyncio.run(main())