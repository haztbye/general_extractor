from typing import List, Any, Optional
from loguru import logger
import traceback
from extractor_pdf.models.document import ExtractResult, Position, RectangleCoordinates
from extractor_pdf.proto_like import Rect
import asyncio

async def add_rect_info(items: List[ExtractResult], processor: Any) -> None:
    """
    为提取结果添加矩形位置信息
    
    Args:
        items: 提取结果列表
        processor: PDF处理器
        
    性能优化:
    - 批量收集所有位置信息，然后并行处理
    - 跳过空列表的处理
    """
    # 如果没有结果，直接返回
    if not items:
        return
        
    # 收集所有需要处理的位置信息
    positions_to_process = []
    for item in items:
        if hasattr(item, 'positions') and item.positions:
            for pos in item.positions:
                positions_to_process.append((item, pos))
    
    # 并行处理所有位置信息
    tasks = [process_position(pos, processor) for item, pos in positions_to_process]
    await asyncio.gather(*tasks)

async def process_position(pos: Position, processor: Any) -> None:
    """
    处理单个位置信息，计算文本的矩形位置坐标
    
    Args:
        pos: 位置对象，包含文本的起始和结束位置
        processor: PDF处理器，用于获取位置信息
    """
    pos_info = processor.get_position_info(str(pos.pos_id))
    if not pos_info:
        return
        
    if not (pos.start is not None and pos.end is not None and pos.start >= 0):
        pos.rects = pos_info['rects']
        return
        
    try:
        pos.rects = [Rect()]  # 改为列表，包含一个Rect对象
        char_rects = pos_info.get('char_rects')
        if not char_rects or not char_rects[0].rect_list:
            pos.rects = pos_info['rects']
            return
            
        coords = _calculate_rectangle_coordinates(
            char_rects[0].rect_list,
            pos.start,
            pos.end
        )
        
        if coords:
            pos.rects[0].coord.extend([
                coords.left_up,
                coords.right_up,
                coords.right_down,
                coords.left_down
            ])
            pos.rects[0].page_id = coords.page_id
        else:
            pos.rects = pos_info['rects']
            
    except Exception as e:
        if hasattr(e, '__traceback__'):
            logger.warning(f'详细错误信息: {traceback.format_exc()}')
        pos.rects = pos_info['rects']

def _calculate_rectangle_coordinates(
    rect_list: List[Any],
    start_idx: int,
    end_idx: int
) -> Optional[RectangleCoordinates]:
    """
    计算文本的矩形坐标
    
    Args:
        rect_list: 字符矩形列表
        start_idx: 起始字符索引
        end_idx: 结束字符索引
        
    Returns:
        Optional[RectangleCoordinates]: 计算得到的矩形坐标，如果计算失败则返回None
    """
    if not rect_list or start_idx >= len(rect_list) or end_idx >= len(rect_list):
        return None
        
    try:
        start_rect = rect_list[start_idx]
        end_rect = rect_list[end_idx]
        return RectangleCoordinates(
            left_up=start_rect.coord[0],
            right_up=end_rect.coord[1],
            right_down=end_rect.coord[2],
            left_down=start_rect.coord[3],
            page_id=start_rect.page_id
        )
    except (IndexError, AttributeError) as e:
        logger.debug(f"计算矩形坐标时出错: {str(e)}")
        return None 