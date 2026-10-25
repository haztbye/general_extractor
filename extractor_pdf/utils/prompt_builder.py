# 提示工程工具
import json
from typing import List
from extractor_pdf.config.settings import SimpleExtractionConfig
from extractor_pdf.models.extraction_result import FieldValue
from extractor_pdf.models.field_config import FieldType



class PromptEngineer:
    """提示工程工具类，负责构建大模型抽取提示"""
    
    @staticmethod
    def build_extraction_prompt(formdoc_content: str, field_configs: List) -> str:
        """
        构建字段抽取提示
        
        Args:
            formdoc_content: 合同文档内容
            field_configs: 字段配置列表
            
        Returns:
            str: 构建好的提示文本
        """
        # 构建字段信息部分
        fields_info = ""
        for i, field in enumerate(field_configs, 1):
            fields_info += f"{i}. 字段名: {field.field_name}\n"
            fields_info += f"   类型: {SimpleExtractionConfig.get_field_type_name(field.field_type.value)}\n"
            
            # 为选择字段添加特定指令
            if field.field_type.value == FieldType.SINGLE_CHOICE.value:
                fields_info += "   要求: 请根据描述选择唯一正确的选项\n"
            elif field.field_type.value == FieldType.MULTIPLE_CHOICE.value:
                fields_info += "   要求: 请识别所有相关的值，多个值用逗号分隔\n"
            
            if field.field_description:
                fields_info += f"   描述: {field.field_description}\n"
            if field.extraction_example:
                fields_info += f"   示例: {field.extraction_example}\n"
            fields_info += "\n"
        
        # 构建完整提示
        prompt = f"""请从以下合同文档中精确提取指定字段的值：

合同文档内容：
{formdoc_content}

需要提取的字段信息：
{fields_info}
请严格按照以下JSON格式返回结果：
{{
    "字段名1": "提取的值或null",
    "字段名2": "提取的值或null"
}}

要求：
1. 只返回JSON格式，不要有其他文本
2. 如果字段未找到，使用null值
3. 保持值的原始格式
4. 确保JSON格式正确，可以直接被解析
"""
        return prompt
    
    @staticmethod
    def extract_json_from_response(model_response: str) -> str:
        """
        从模型响应中提取JSON部分
        
        Args:
            model_response: 大模型返回的响应文本
            
        Returns:
            str: 提取出的JSON字符串
        """
        # 尝试找到JSON的开始和结束位置
        start = model_response.find('{')
        end = model_response.rfind('}') + 1
        
        if start >= 0 and end > start:
            json_str = model_response[start:end]
            # 验证是否为有效的JSON
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass
        
        # 如果找不到有效的JSON，返回原始响应
        return model_response
    
    @staticmethod
    def create_field_value(raw_value: str, field_type: int):
        """
        根据字段类型创建结构化字段值
        
        Args:
            raw_value: 原始文本值
            field_type: 字段类型
            
        Returns:
            FieldValue: 结构化的字段值对象
        """
        # 处理空值
        if not raw_value or raw_value.lower() == "null":
            return None
            
        # 创建FieldValue对象
        field_value = FieldValue(raw_value=raw_value)
        
        try:
            # 根据字段类型设置相应的字段
            if field_type == 0:  # TEXT
                field_value.text = raw_value
            elif field_type == 1:  # MULTILINE_TEXT
                field_value.text = raw_value
            elif field_type == 2:  # NUMBER
                try:
                    field_value.number = float(raw_value)
                except ValueError:
                    field_value.text = raw_value
            elif field_type == 3:  # AMOUNT
                # 解析金额格式
                try:
                    import re
                    amount_match = re.search(r'[\d,]+\.?\d*', raw_value)
                    if amount_match:
                        amount_str = amount_match.group().replace(',', '')
                        field_value.amount = float(amount_str)
                        
                        # 提取货币单位
                        currency_match = re.search(r'[￥¥$€£]', raw_value)
                        if currency_match:
                            field_value.currency = currency_match.group()
                        else:
                            field_value.currency = "CNY"
                    else:
                        field_value.text = raw_value
                except:
                    field_value.text = raw_value
            elif field_type == 4:  # DATE
                field_value.date = raw_value
            elif field_type == 5:  # INTERNAL_PARTY
                field_value.text = raw_value
            elif field_type == 6:  # EXTERNAL_PARTY
                field_value.text = raw_value
            elif field_type == 7:  # SINGLE_CHOICE
                field_value.text = raw_value
            elif field_type == 8:  # MULTIPLE_CHOICE
                field_value.text = raw_value
            else:
                field_value.text = raw_value
                
        except Exception as e:
            # 如果解析失败，保留原始文本值
            field_value.text = raw_value
        
        return field_value
