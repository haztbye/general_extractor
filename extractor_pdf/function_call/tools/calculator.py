from typing import Union
from langchain.tools import BaseTool
import numexpr as ne
import numpy as np
from extractor_pdf.errors.error_manager import ToolExecutionError
from extractor_pdf.function_call.tools import register_tool

@register_tool
class Calculator(BaseTool):
    name: str = "math_calculator"
    description: str = """数学计算器：用于执行基本的数学运算。支持以下操作：
    1. 基本运算：加(+)、减(-)、乘(*)、除(/)、幂(**)、取模(%)
    2. 比较运算：<, <=, ==, !=, >, >=
    3. 数学函数：
       - abs(绝对值)
       - sqrt(开方)
       - sin, cos, tan(三角函数)
       - arcsin, arccos, arctan(反三角函数)
       - sinh, cosh, tanh(双曲函数)
       - exp(指数)
       - log, log10(对数)
       - maximum, minimum(最大最小值)
    4. 常数：pi(π)、e
    
    参数说明：
    - expression: 数学表达式字符串
    
    示例：
    - 简单计算："1 + 2 * 3"
    - 函数计算："sin(pi/2) + sqrt(16)"
    - 复杂公式："2 * pi * sqrt(abs(sin(x**2)))"
    """

    def _validate_expression(self, expression: str) -> bool:
        """验证表达式是否安全"""
        # numexpr支持的所有操作符和函数
        allowed_ops = {
            '+', '-', '*', '/', '**', '%',  # 算术运算符
            '<', '<=', '==', '!=', '>', '>=',  # 比较运算符
            '(', ')', ',', '.', ' ',  # 其他符号
        }
        
        # numexpr支持的所有函数
        allowed_funcs = {
            'abs', 'sqrt',
            'sin', 'cos', 'tan',
            'arcsin', 'arccos', 'arctan',
            'sinh', 'cosh', 'tanh',
            'exp', 'log', 'log10',
            'maximum', 'minimum'
        }
        
        # 常数
        allowed_consts = {'pi', 'e'}
        
        # 移除所有数字
        non_numeric = ''.join(c for c in expression if not (c.isdigit() or c == '.'))
        
        # 检查所有非数字字符是否在允许列表中
        for c in non_numeric:
            if c not in allowed_ops and c not in ' ':
                # 如果不是操作符，检查是否是函数名的一部分
                is_valid = False
                for func in allowed_funcs | allowed_consts:
                    if c in func:
                        is_valid = True
                        break
                if not is_valid:
                    return False
        
        return True

    def _run(self, expression: str) -> Union[float, str]:
        """执行计算"""
        # print(f'expression >>> {expression}')
        # print(f'ne.evaluate(expression) >>> {ne.evaluate(expression)}')
        # print(f'eval >>> {eval(expression)}')
        try:
            # 验证输入
            if not expression or not isinstance(expression, str):
                raise ValueError("输入必须是非空字符串")
            
            if not self._validate_expression(expression):
                raise ValueError("表达式包含不支持的字符或操作")
            
            # 替换常用常数
            expression = expression.replace('pi', str(np.pi))
            expression = expression.replace('e', str(np.e))
            
            # 使用numexpr计算表达式
            result = float(ne.evaluate(expression))
            
            # 处理特殊情况
            if np.isnan(result):
                raise ValueError("计算结果为NaN")
            if np.isinf(result):
                raise ValueError("计算结果为无穷大")
            
            # 处理精度问题，保留10位小数
            result = round(result, 10)
            
            return result
            
        except Exception as e:
            raise ToolExecutionError(
                message=str(e),
                error_code="E007.2"
            )

    async def _arun(self, expression: str) -> Union[float, str]:
        """异步执行计算"""
        return self._run(expression)