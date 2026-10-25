from typing import Dict
from extractor_pdf.models.document import ExtractResult, Position
from loguru import logger
from extractor_pdf.get_relations.get_relations import get_relations

BRACKET_TRANS_TABLE = str.maketrans('（）', '()')

async def process_relation(name: str, result: ExtractResult, all_extract_result: Dict[str, ExtractResult]) -> None:
    """处理单个关系提取逻辑，直接修改传入的result对象
    
    Args:
        name: 关系名称
        result: 要修改的提取结果对象（会被直接修改）
        all_extract_result: 所有提取结果字典（用于查找相关关系）
        
    Note:
        此函数会直接修改传入的result对象，不需要返回值
    """
    relations = get_relations.get_relations(name)
    # logger.debug(f'{name} 的 relations >>> {relations}')
    
    if not relations:
        return
        
    for relation_list in relations:
        # 使用列表推导式收集相关文本和位置
        relation_texts = [f'我想要计算{name}是多少，现在已知以下要素：']
        relation_positions = []
        
        for relation_value in relation_list:
            # 转换括号
            relation_value = relation_value.translate(BRACKET_TRANS_TABLE)
            relation_result = all_extract_result.get(relation_value)
            
            if not (relation_result and relation_result.text):
                break
                
            relation_texts.append(f'{relation_value}是```{relation_result.text}```')
            relation_positions.extend(relation_result.positions)
        else:
            # 所有关系值都处理成功
            text = '\n'.join(relation_texts)
            logger.debug(f'处理关系 {name} 的文本: {text}')
            
            from extractor_pdf.function_call.base import tool_manager
            cal_result = await tool_manager.process_query(text)
            # print(f'result >>> {result}')
            result.text = cal_result
            result.positions = relation_positions
            break
    return all_extract_result


if __name__ == '__main__':
    all_extract_result = {
        '含税总金额': ExtractResult(
            item_name='含税总金额',
            text='187633元',
            positions=[Position(pos_id=10, start=0, end=10, rects=(10, 10, 10, 12))]
        ),
        '不含税金额': ExtractResult(
            item_name='不含税金额',
            text='180000元',
            positions=[Position(pos_id=11, start=0, end=8, rects=(11, 10, 10, 15))]
        ),
        '税金': ExtractResult(
            item_name='税金',
            text='',
            positions=[Position(pos_id=12, start=0, end=8, rects=(16, 9, 8, 19))]
        )
    }
    import asyncio
    result = asyncio.run(process_relation('税金', all_extract_result['税金'], all_extract_result))
    print(result)