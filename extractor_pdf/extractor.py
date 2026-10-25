"""从新模块导入提取器函数。"""

from extractor_pdf.core.extractor import extractor, extractor_with_dynamic_fields
from extractor_pdf.models.field_config import FieldConfig, FieldType
from extractor_pdf.core.dynamic_extractor import create_field_config

__all__ = [
    'extractor',
    'extractor_with_dynamic_fields',
    'FieldConfig',
    'FieldType',
    'create_field_config'
]
