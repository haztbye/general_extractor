from typing import Any, Dict, List, Optional
from loguru import logger
import asyncio
from extractor_pdf.utils.get_formdoc import PDFWindowProcessor
from extractor_pdf.core.extract_items import Extractor
from extractor_pdf.errors.error_manager import ExtractError, PDFProcessError, RelationError, handle_error, LocateError
from extractor_pdf.core.locator_optimized import OptimizedLocator
from extractor_pdf.core.position_processor import add_rect_info
from extractor_pdf.core.window_processor import process_window, process_window_text, update_global_and_get_changes
from extractor_pdf.utils.label_info_builder import build_form_res
from extractor_pdf.core.merge_results import merge_results
from extractor_pdf.core.logic_process import process_relation
from extractor_pdf.core.dynamic_extractor import extract_fields_from_windows, create_field_config
from extractor_pdf.models.field_config import FieldConfig, FieldType
from extractor_pdf.proto_like import form_res_to_json

@handle_error(default_return=None)
async def extractor(formdoc: Any) -> Any:
    """
    从PDF文档中提取信息的主函数
    
    Args:
        formdoc: 输入的form文档对象
        
    Returns:
        FormRes: 提取结果的表单对象
        
    性能优化:
    - 使用异步并行处理多个窗口
    - 批量处理位置信息
    - 优化文本拼接逻辑
    """
    logger.info('enter function extractor')
    
    try:
        ################### 模块一：文本分割 ###################
        processor = PDFWindowProcessor(doc=formdoc)
        output_windows = processor.process()
        logger.info('ocr finished, start to extract')
        
        # 定义要执行的提取器函数列表
        extractor_functions = [
            Extractor.extract_subject,
            Extractor.extract_amout,
            Extractor.extract_other,
            Extractor.extract_time,
            # Extractor.extract_thing,
            Extractor.extract_transaction
        ]
        
        ################### 模块二：文本抽取 + 文本定位 ###################
        window_results = []
        global_result = {}

        async def process_single_window(wd):
            """处理单个窗口的异步函数"""
            try:
                # ===== 抽取 =====
                window_text = process_window_text(wd)
                final_result = await process_window(wd, window_text, extractor_functions)

                # ===== 合并 =====
                final_result = update_global_and_get_changes(final_result, global_result)
                logger.debug(f'Window processing result: {final_result}')

                if not final_result:
                    return []

                # ===== 定位 =====
                locator = OptimizedLocator(wd, final_result)
                located_result = await locator.locator()
                await add_rect_info(located_result, processor)
                return located_result
                
            except Exception as e:
                logger.error(f"处理窗口时发生错误: {str(e)}")
                if isinstance(e, LocateError):
                    raise LocateError(
                        message=f"处理结果定位时发生错误",
                        original_error=e
                    )
                raise ExtractError(
                    message=f"抽取结果时发生错误",
                    original_error=e
                )

        # 并行处理所有窗口
        tasks = [process_single_window(wd) for wd in output_windows]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"窗口处理失败: {str(result)}")
                continue
            if result:
                window_results.extend(result)
        
        # 合并抽取结果
        all_extract_result = merge_results(window_results)

        ################### 模块三：逻辑处理 ###################
        # # 并行处理关系
        # async def process_single_relation(name, result):
        #     if not result.text:
        #         await process_relation(name, result, all_extract_result)

        # relation_tasks = [
        #     process_single_relation(name, result) 
        #     for name, result in all_extract_result.items()
        # ]
        # await asyncio.gather(*relation_tasks, return_exceptions=True)

        # 构建返回结果
        extract_results = [v for k, v in all_extract_result.items()]
        final_result = build_form_res(extract_results)
        logger.info(f'finish extractor function, the result is: {form_res_to_json(final_result)}')
        
        return final_result
        
    except Exception as e:
        if not isinstance(e, (ExtractError, RelationError)):  # 添加RelationError到异常处理
            raise PDFProcessError(
                message="PDF处理过程中发生错误",
                original_error=e
            )
        raise


@handle_error(default_return=None)
async def extractor_with_dynamic_fields(formdoc: Any, field_configs: List[FieldConfig]) -> List[Dict[str, Any]]:
    """
    支持动态字段配置的提取器函数
    
    Args:
        formdoc: 输入的form文档对象
        field_configs: 字段配置列表
        
    Returns:
        List[Dict]: 包含所有窗口提取结果的列表
    """
    logger.info('进入动态字段提取器函数')
    
    try:
        ################### 模块一：文本分割 ###################
        processor = PDFWindowProcessor(doc=formdoc)
        output_windows = processor.process()
        logger.info(f'OCR完成，开始提取，窗口数量: {len(output_windows)}，字段数量: {len(field_configs)}')
        
        ################### 模块二：动态字段提取 ###################
        # 使用动态提取器处理所有窗口
        dynamic_results = await extract_fields_from_windows(output_windows, field_configs)
        
        logger.info(f'动态字段提取完成，结果数量: {len(dynamic_results)}')
        return dynamic_results
        
    except Exception as e:
        logger.error(f"动态字段提取过程中发生错误: {str(e)}")
        if not isinstance(e, (ExtractError, RelationError)):
            raise PDFProcessError(
                message="PDF动态字段处理过程中发生错误",
                original_error=e
            )
        raise
