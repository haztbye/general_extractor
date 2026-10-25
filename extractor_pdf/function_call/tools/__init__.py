from typing import Dict, Type
from extractor_pdf.function_call.tool import Tool
import os
import importlib

class ToolRegistry:
    """工具注册器"""
    _instance = None
    _tools: Dict[str, Tool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 在创建实例时自动导入所有工具
            cls._import_tools()
        return cls._instance

    @classmethod
    def register(cls, tool_cls: Type):
        """注册工具类"""
        tool_instance = tool_cls()
        cls._tools[tool_instance.name] = Tool(
            name=tool_instance.name,
            description=tool_instance.description,
            func=tool_instance._run
        )
        return tool_cls

    @classmethod
    def get_tools(cls) -> Dict[str, Tool]:
        """获取所有注册的工具"""
        if not cls._tools:
            cls._import_tools()
        return cls._tools

    @classmethod
    def _import_tools(cls):
        """导入tools目录下的所有工具模块"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        for file in os.listdir(current_dir):
            if file.endswith('.py') and not file.startswith('__'):
                module_name = file[:-3]  # 移除.py后缀
                importlib.import_module(f'extractor_pdf.function_call.tools.{module_name}')

def register_tool(cls):
    """工具注册装饰器"""
    return ToolRegistry.register(cls)

# 确保在模块导入时就初始化ToolRegistry
ToolRegistry() 