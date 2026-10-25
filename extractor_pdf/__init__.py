"""Extractor-PDF 主模块"""

from .extractor import (
    extractor,
    extractor_with_dynamic_fields,
    FieldConfig,
    FieldType,
    create_field_config
)

__all__ = [
    'extractor',
    'extractor_with_dynamic_fields',
    'FieldConfig',
    'FieldType',
    'create_field_config'
]

# 版本信息
__version__ = '1.0.0'
__description__ = '通用提取系统，支持动态字段配置'