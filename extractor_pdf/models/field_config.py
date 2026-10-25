# 字段配置数据模型
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class FieldType(Enum):
    """字段类型枚举"""
    TEXT = 0                   # 单行文本
    MULTILINE_TEXT = 1         # 多行文本  
    NUMBER = 2                 # 数字
    AMOUNT = 3                 # 金额
    DATE = 4                   # 日期
    INTERNAL_PARTY = 5         # 我方单位名称
    EXTERNAL_PARTY = 6         # 对方单位名称
    SINGLE_CHOICE = 7          # 单选
    MULTIPLE_CHOICE = 8        # 多选


class FieldConfig(BaseModel):
    """字段配置数据模型"""
    field_name: str               # 字段名
    field_type: FieldType         # 字段类型
    field_description: Optional[str] = None  # 字段描述
    extraction_example: Optional[str] = None # 抽取示例
    is_intermediate: bool = False # 是否为中间字段

    @classmethod
    def get_field_type_name(cls, field_type: int) -> str:
        """获取字段类型名称"""
        type_names = {
            0: "文本",
            1: "多行文本", 
            2: "数字",
            3: "金额",
            4: "日期",
            5: "我方单位名称",
            6: "对方单位名称",
            7: "单选",
            8: "多选"
        }
        return type_names.get(field_type, "未知类型")
