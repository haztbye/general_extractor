from typing import List, Dict, Any, Tuple
from loguru import logger
from extractor_pdf.models.extractor_types import WindowData, WindowText, WindowResult
from extractor_pdf.core.extract_items import Extractor
from extractor_pdf.errors.error_manager import ExtractError, LocateError
import asyncio

async def process_window(
    wd: WindowData, 
    window_text: WindowText, 
    extractor_functions: List[Any], 
) -> WindowResult:
    """
    处理单个窗口的文本提取和定位
    
    Args:
        wd: 窗口数据
        window_text: 窗口文本
        extractor_functions: 提取器函数列表
        
    Returns:
        List[ExtractResult]: 窗口的提取结果
        
    性能优化:
    - 并行执行所有提取器函数
    - 使用return_exceptions=True避免因单个任务失败导致整个窗口处理失败
    """
    extractor_instance = Extractor(window_text)
    
    # 创建所有提取器函数的任务
    extract_tasks = [
        extractor_func(extractor_instance, window_text) 
        for extractor_func in extractor_functions
    ]
    
    try:
        # 并行执行所有提取任务
        extract_results = await asyncio.gather(*extract_tasks, return_exceptions=True)
        final_result = dict()
        # 处理每个结果
        for i, result in enumerate(extract_results):
            # 如果结果是异常，记录并继续
            if isinstance(result, Exception):
                func_name = extractor_functions[i].__name__
                logger.error(f"执行{func_name}时发生错误: {result}")
                continue
                
            # 如果没有提取到结果，跳过定位步骤
            if not result:
                continue

            final_result.update(result)

        return final_result
           
    except Exception as e:
        raise ExtractError(
            message="窗口处理过程中发生错误",
            original_error=e
        )

def update_global_and_get_changes(current_result: Dict[str, Any], global_result: Dict[str, Any]) -> Dict[str, Any]:
    """更新全局结果并返回本次更新的内容

    该函数会直接修改传入的global_result参数,并返回本次实际发生更新的项。
    更新策略: 对于相同的key,保留文本长度更长的值。

    Args:
        current_result: 当前窗口的处理结果
        global_result: 全局结果字典(会被直接修改)

    Returns:
        Dict[str, Any]: 本次实际发生更新的项的字典
    """
    updated_items = {}
    
    for key, value in current_result.items():
        should_update = False
        
        if key not in global_result or not global_result[key]:
            should_update = True
        # else:
        #     # 当前策略: 保留更长的文本
        #     # TODO: 可以在此添加更复杂的合并策略
        #     if len(value) > len(global_result[key]):
        #         should_update = True
                
        if should_update:
            global_result[key] = value
            updated_items[key] = value
            
    return updated_items

def process_table_text(
    current_text: str, 
    current_pos_id: str, 
    pre_id: List[str], 
    table_text: str
) -> Tuple[str, List[str]]:
    """处理表格文本的拼接逻辑
    
    Args:
        current_text: 当前文本
        current_pos_id: 当前位置ID
        pre_id: 前一个ID信息
        table_text: 当前表格文本
    
    Returns:
        Tuple[str, List[str]]: 返回处理后的表格文本和更新后的pre_id
    """
    now_id = current_pos_id.split('-')[:3]
    
    if not pre_id:
        return current_text, now_id
        
    if '-'.join(pre_id) == '-'.join(now_id):
        # 同一个单元格
        return table_text + '\t' + current_text, pre_id
    elif '-'.join(pre_id[:2]) == '-'.join(now_id[:2]):
        # 同一行不同列
        return table_text + '|' + current_text, now_id
    elif pre_id[0] == now_id[0]:
        # 同一个表格不同行
        return table_text + '\n' + current_text, now_id
    else:
        # 不同表格
        return table_text, []

def process_window_text(window_data: WindowData) -> WindowText:
    """处理窗口文本，将普通文本和表格文本按规则拼接
    
    Args:
        window_data: 窗口数据列表
    
    Returns:
        str: 处理后的窗口文本
    """
    window_text = ''
    table_text = ''
    pre_id: List[str] = []
    
    for item in window_data:
        text = item['text']
        pos_id = item['pos_id']
        
        if '-' not in pos_id:
            # 处理普通文本
            if not window_text:
                window_text = text
                continue
                
            if pre_id:
                # 如果之前有未处理的表格文本，先添加到window_text
                window_text = window_text + '\n' + table_text
                pre_id = []
                
            window_text = window_text + '\n' + text
        else:
            # 处理表格文本
            if not pre_id:
                table_text = text
                pre_id = pos_id.split('-')[:3]
            else:
                table_text, pre_id = process_table_text(text, pos_id, pre_id, table_text)
                if not pre_id:
                    # 如果pre_id被清空，说明遇到新表格，需要将之前的表格文本添加到window_text
                    window_text = window_text + '\n' + table_text
                    table_text = text
                    pre_id = pos_id.split('-')[:3]
    
    # 处理最后剩余的表格文本
    if pre_id:
        window_text = window_text + '\n' + table_text
    
    return window_text 