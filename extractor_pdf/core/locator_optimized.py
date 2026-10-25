from typing import List, Dict, Optional, Union, Set
from collections import defaultdict
import re
from loguru import logger
import asyncio
from concurrent.futures import ThreadPoolExecutor
from extractor_pdf.utils.prompt_manager import prompt_manager
from extractor_pdf.utils.llm import get_llm_response_async
from extractor_pdf.models.document import TextSegment, Position, SearchPattern, ExtractResult
from extractor_pdf.errors.error_manager import LocateError
from extractor_pdf.utils.json_processor import json_processor
import json

class OptimizedLocator:
    CONFIG = {
        'WINDOW_SIZE': 2,
        'MAX_WORKERS': 5
    }
    
    def __init__(self, text_list: List[Dict[str, str]], extract_items: Dict[str, str]):
        """
        初始化定位器
        
        Args:
            text_list: 文本段落列表
            extract_items: 需要提取的项目字典
        """        
        # 初始化线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=self.CONFIG['MAX_WORKERS'])
        
        # 初始化文本段落
        self.segments = self._initialize_segments(text_list)
        self.extract_items = extract_items
        self._validate_inputs()
        
        # 构建索引
        self.full_text = ''.join(seg.text for seg in self.segments)
        self.char_index = None
        self.segment_index = {seg.position.pos_id: seg for seg in self.segments}
        
        # 预编译正则表达式
        self.space_pattern = re.compile(r'\s+')
        
        # 资源状态标记
        self._initialized = False
        self._closed = False

    def _validate_inputs(self):
        """验证输入数据的有效性"""
        if not self.extract_items:
            raise ValueError("text_list 和 extract_items 不能为空")
        
        new_extract_items = {}
        for k, v in self.extract_items.items():
            if isinstance(v, dict):
                new_extract_items.update(v)
            else:
                new_extract_items[k] = v
        self.extract_items = new_extract_items

    def _initialize_segments(self, text_list: List[Dict]) -> List[TextSegment]:
        """初始化文本段落，计算每个段落在全文中的位置"""
        segments = []
        # print(f'text_list >>> {text_list}')
        for item in text_list:
            text_length = len(item['text'])
            segment = TextSegment(
                position=Position(item['pos_id'], 0, text_length),
                text=item['text'],
            )
            segments.append(segment)
        return segments

    async def initialize(self):
        """异步初始化方法"""
        self.char_index = await self._build_char_index_async()
        return self

    async def _build_char_index_async(self) -> Dict[str, Set[int]]:
        """异步构建字符索引"""
        async def process_segment(segment: TextSegment) -> Dict[str, Set[int]]:
            local_index = defaultdict(set)
            for char in segment.text:
                local_index[char].add(segment.position.pos_id)
            return local_index

        # 创建所有段落的异步任务
        tasks = [process_segment(segment) for segment in self.segments]
        
        # 并发执行所有任务
        local_indices = await asyncio.gather(*tasks)
        
        # 合并所有局部索引
        final_index = defaultdict(set)
        for local_index in local_indices:
            for char, pos_ids in local_index.items():
                final_index[char].update(pos_ids)
        
        return final_index

    async def _prepare_search_pattern_async(self, extract_result: str, extract_item_name: str) -> SearchPattern:
        """异步准备搜索模式"""
        # logger.debug(f'extract_result >>> {extract_result}')
        if not extract_result:
            return None
        extract_result = re.sub(r'\s+','',extract_result)
        escaped = re.escape(str(extract_result))
        flexible_pattern = add_flexible_whitespace(escaped)
        compiled_pattern = re.compile(flexible_pattern)
        
        return SearchPattern(
            extract_item_name=extract_item_name,
            original=str(extract_result),
            flexible_pattern=flexible_pattern,
            char_set=frozenset(str(extract_result).replace(' ', '')),
            compiled_pattern=compiled_pattern
        )

    def _find_potential_segments(self, pattern: SearchPattern) -> tuple[List[TextSegment], bool]:
        """找出可能包含目标文本的段落，并判断是否需要LLM
        
        Returns:
            tuple[List[TextSegment], bool]: 返回潜在段落列表和是否需要使用LLM的标志
        """
        # 记录每个字符出现在哪些段落
        char_positions = {}
        for char in pattern.char_set:
            if char in self.char_index:
                char_positions[char] = self.char_index[char]
            else:
                # logger.debug('字符完全不存在，直接返回空列表和True（使用LLM）')
                return [], True
        
        tmp_positions = set()
        # logger.debug(f'char_positions >>> {char_positions}')
        for char, positions in char_positions.items():
            if not tmp_positions:
                tmp_positions = set(positions)
            else:
                tmp_positions = tmp_positions.intersection(positions)
        # logger.debug(f'tmp_positions >>> {tmp_positions}')
        return [self.segment_index[pos_id] for pos_id in tmp_positions], True if len(tmp_positions) > 1 else False
        

    async def _smart_locate(self, pattern: SearchPattern) -> Optional[Union[ExtractResult, SearchPattern]]:
        """智能定位策略"""
        if not pattern:
            return None
        # 1. 快速字符集检查
        if not pattern.char_set:
            return ExtractResult(
                item_name=pattern.extract_item_name,
                text='',
                result='',
                positions=[]
            )
        if not pattern.char_set.issubset(set(self.full_text)):
            logger.info(f"快速字符检查未通过，切换到 LLM 定位: {pattern.extract_item_name}")
            return pattern
        
        # 2. 获取潜在的相关段落
        potential_segments, need_llm = self._find_potential_segments(pattern)
        
        if need_llm:
            logger.info(f"字符分布复杂，切换到 LLM 定位: {pattern.extract_item_name}")
            return pattern
        
        # 3. 在相关段落中尝试匹配
        for strategy in [self._exact_match, self._regex_match, self._window_match]:
            if result := strategy(pattern, potential_segments):
                return result
        
        return pattern

    def _exact_match(self, pattern: SearchPattern, segments: List[TextSegment]) -> Optional[ExtractResult]:
        """精确匹配"""
        for segment in segments:
            if pattern.original in segment.text:
                start_pos = segment.text.find(pattern.original)
                return ExtractResult(
                    item_name=pattern.extract_item_name,
                    text=segment.text,
                    result=pattern.original,
                    positions = [Position(segment.position.pos_id, start_pos, start_pos + len(pattern.original))]
                )
        return None

    def _regex_match(self, pattern: SearchPattern, segments: List[TextSegment]) -> Optional[ExtractResult]:
        """正则匹配"""
        for segment in segments:
            if match := pattern.compiled_pattern.search(segment.text):
                return ExtractResult(
                    item_name=pattern.extract_item_name,
                    text=segment.text,
                    result=pattern.original,
                    positions = [Position(segment.position.pos_id, match.start(), match.end())]
                )
        return None

    def _window_match(self, pattern: SearchPattern, segments: List[TextSegment]) -> Optional[ExtractResult]:
        """滑动窗口匹配"""
        for i in range(len(segments) - self.CONFIG['WINDOW_SIZE'] + 1):
            window_segments = segments[i:i + self.CONFIG['WINDOW_SIZE']]
            merged_text = ''.join(seg.text for seg in window_segments)
            
            if match := pattern.compiled_pattern.search(merged_text):
                positions = self._calculate_window_positions(
                    window_segments, 
                    match.start(), 
                    match.end()
                )
                return ExtractResult(
                    item_name=pattern.extract_item_name,
                    text=merged_text,
                    result=pattern.original,
                    positions=positions
                )
        return None

    def _calculate_window_positions(
        self, 
        segments: List[TextSegment], 
        match_start: int, 
        match_end: int
    ) -> List[List]:
        """计算窗口中的位置信息"""
        positions = []
        current_pos = 0
        
        for segment in segments:
            text_len = len(segment.text)
            if current_pos <= match_start < current_pos + text_len:
                start_in_text = match_start - current_pos
                end_in_text = min(match_end - current_pos, text_len)
                positions.append(Position(segment.position.pos_id, start_in_text, end_in_text))
            elif current_pos < match_end <= current_pos + text_len:
                end_in_text = match_end - current_pos
                positions.append(Position(segment.position.pos_id, 0, end_in_text))
            current_pos += text_len
            
        return positions

    async def _llm_locator(self, unvalid_results: List[SearchPattern]) -> List[ExtractResult]:
        """使用大语言模型进行定位
        
        Args:
            unvalid_results: 未能通过常规方法定位的搜索模式列表
            
        Returns:
            List[ExtractResult]: 定位结果列表
        """
        if not unvalid_results:
            return []
            
        try:
            # 准备输入数据
            text_format = self._prepare_text_format()
            # 分段处理 text_format
            text_segments = self.split_text_format(text_format)
            all_llm_responses = {}
            locate_prompts = {result.extract_item_name: result.original for result in unvalid_results}
            for segment in text_segments:
                # 获取LLM响应并解析
                llm_response1 = await self._get_llm_response(locate_prompts, segment)
                if llm_response1:
                    all_llm_responses.update(llm_response1)
            if not all_llm_responses:
                return []
            # 处理LLM返回结果
            return self._process_llm_results(locate_prompts, all_llm_responses)
        except Exception as e:
            raise LocateError(
                message="LLM定位失败",
                original_error=e
            )

    def split_text_format(self, text_format):
        max_length = 10000
        if len(text_format) <= max_length:
            return [text_format]
        segments = []
        start = 0
        while start < len(text_format):
            end = start + max_length
            if end >= len(text_format):
                segments.append(text_format[start:])
                break
            # 找到行末
            while end > start and text_format[end - 1] != '\n':
                end -= 1
            if end == start:
                # 如果没有换行符，强制截断
                end = start + max_length
            segments.append(text_format[start:end])
            start = end
        return segments
            
    def _prepare_text_format(self) -> str:
        """准备用于LLM输入的文本格式"""
        return '\n'.join(
            f"【{seg.position.pos_id}】: {seg.text}" 
            for seg in self.segments
        )
        
    async def _get_llm_response(self, locate_prompts: Dict[str, str], text_format: str) -> Optional[Dict]:
        """获取LLM响应并解析结果
        
        Args:
            locate_prompts: 定位提示词字典
            text_format: 格式化后的文本
            
        Returns:
            Optional[Dict]: 解析后的LLM响应结果
        """
        logger.debug(f'locate_prompts >>> {locate_prompts}')
        response = await get_llm_response_async(
            prompt=prompt_manager.get_prompt('locate_text').format(
                extract_result=json.dumps(locate_prompts), 
                text=text_format
            )
        )
        return json_processor.parse_json(response)
        
    def _process_llm_results(self, locate_prompts: Dict[str, str], llm_response: Dict) -> List[ExtractResult]:
        """处理LLM返回的结果
        
        Args:
            locate_prompts: 原始定位提示词字典
            llm_response: LLM返回的响应结果
            
        Returns:
            List[ExtractResult]: 处理后的定位结果列表
        """
        results = []
        processed_items = set()
        unmatched_items = {}

        logger.debug(f'llm_response >>> {llm_response.items()}')
        # 首先处理直接匹配的结果
        for name, id_list in llm_response.items():
            # text = ''.join([self.segment_index[str(i)].text for i in id_list])
            text = ''
            for i in id_list:
                try:
                    text += self.segment_index[str(i)].text
                except:
                    logger.error(f'{i} 不在 segment_index 里')
                    continue
            try:
                results.append(ExtractResult(
                    item_name=name,
                    text=text,
                    result=locate_prompts[name],
                    positions=[Position(j, 0, len(text)) for j in id_list]
                ))
                processed_items.add(name)
            except:
                unmatched_items[name] = text
        
        # logger.debug(f'processed_items >>> {processed_items}')
        # logger.debug(f'unmatched_items >>> {unmatched_items}')
        # 处理未匹配的结果
        if unmatched_items:
            results.extend(self._match_remaining_items(
                locate_prompts,
                llm_response,
                processed_items,
                unmatched_items
            ))
            
        return results
        
    def _match_remaining_items(
        self,
        locate_prompts: Dict[str, str],
        llm_response: Dict,
        processed_items: Set[str],
        unmatched_items: Dict[str, str]
    ) -> List[ExtractResult]:
        """处理剩余未匹配的项目
        
        Args:
            locate_prompts: 原始定位提示词字典
            llm_response: LLM返回的响应结果
            processed_items: 已处理的项目集合
            unmatched_items: 未匹配的项目字典
            
        Returns:
            List[ExtractResult]: 匹配结果列表
        """
        results = []
        
        # 获取剩余的提示词和响应
        remaining_prompts = {k: v for k, v in locate_prompts.items() if k not in processed_items}
        remaining_responses = {k: v for k, v in llm_response.items() if k not in processed_items}
        # logger.debug(f'remaining_prompts >>> {remaining_prompts}')
        # logger.debug(f'remaining_responses >>> {remaining_responses}')
        # 如果只剩一个未匹配项
        if len(remaining_prompts) == len(remaining_responses) == 1:
            prompt_key = next(iter(remaining_prompts.keys()))
            prompt_value = remaining_prompts[prompt_key]
            response_key = next(iter(remaining_responses.keys()))
            result_text = next(iter(unmatched_items.values()))
            
            results.append(ExtractResult(
                item_name=prompt_key,
                text=result_text,
                result=prompt_value,
                positions=[Position(j, 0, len(result_text)) for j in remaining_responses[response_key]]
            ))
            return results
            
        # 处理多个未匹配项
        import Levenshtein
        
        # 计算编辑距离并排序
        distance_pairs = []
        prompt_keys = list(remaining_prompts.keys())
        response_keys = list(remaining_responses.keys())
        
        for i, name1 in enumerate(prompt_keys):
            for name2 in response_keys:
                distance_pairs.append((name1, name2, Levenshtein.distance(name1, name2)))
        # logger.debug(f'distance_pairs >>> {distance_pairs}')
        distance_pairs.sort(key=lambda x: x[2])
        
        # 根据编辑距离匹配剩余项
        matched_prompts = set()
        matched_responses = set()
        
        for prompt_key, response_key, _ in distance_pairs:
            if prompt_key not in matched_prompts and response_key not in matched_responses:
                results.append(ExtractResult(
                    item_name=prompt_key,
                    text=unmatched_items[response_key],
                    result=remaining_prompts[prompt_key],
                    positions=[Position(j, 0, len(unmatched_items[response_key])) 
                             for j in remaining_responses[response_key]]
                ))
                matched_prompts.add(prompt_key)
                matched_responses.add(response_key)
                
        return results

    async def locator(self) -> List[ExtractResult]:
        """定位所有提取项"""
        if self.char_index is None:
            await self.initialize()
            
        try:
            # 并发准备所有搜索模式
            patterns = await asyncio.gather(*[
                self._prepare_search_pattern_async(item_result, item_name)
                for item_name, item_result in self.extract_items.items()
            ])
            
            # 并发执行所有定位任务，让llm.py中的信号量来控制并发
            results = await asyncio.gather(*[
                self._smart_locate(pattern)
                for pattern in patterns
            ], return_exceptions=True)
            
            # 处理结果，过滤掉异常
            valid_results = []
            unvalid_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"定位任务失败: {str(result)}")
                    continue
                if not result:
                    continue
                if isinstance(result, ExtractResult):
                    valid_results.append(result)
                elif isinstance(result, SearchPattern):
                    unvalid_results.append(result)
            
            valid_results.extend(await self._llm_locator(unvalid_results))
            
            return valid_results
            
        except Exception as e:
            logger.error(f"定位过程发生错误: {str(e)}")
            raise LocateError(
                message="定位过程发生错误",
                original_error=e
            )

    def __del__(self):
        """确保线程池被正确关闭"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=True)


def add_flexible_whitespace(escaped_regex: str) -> str:
    """
    在已转义的正则表达式中，仅在非转义的普通字符间添加灵活的空白匹配(\s*)

    参数:
        escaped_regex (str): 已转义的正则表达式字符串

    返回:
        str: 处理后的正则表达式，只在普通字符间插入了\s*
    """
    if not escaped_regex:
        return escaped_regex

    # 构建正则表达式模式
    # 1. 匹配已转义的特殊字符序列
    # 2. 匹配非转义的普通字符
    pattern = r'(\\[\\[\]().*+?^${}|])|([^\\])'

    # 处理每一个匹配结果
    def replace(match):
        escaped_part = match.group(1)
        normal_char = match.group(2)

        if escaped_part:
            # 如果是转义的特殊字符，直接返回，不添加\s*
            return escaped_part
        else:
            # 如果是普通字符，检查是否为字符串末尾
            if match.end() == len(escaped_regex):
                return normal_char
            else:
                return normal_char + r'\s*'

    # 执行替换
    return re.sub(pattern, replace, escaped_regex)

if __name__ == '__main__':
    import asyncio
    
    async def main():
        text_list = [
            {'text': '这份合同的合同名称是风电222', 'pos_id': 1},
            {'text': '合同', 'pos_id': 2},
            {'text': '合同金额为100000（不含税）', 'pos_id': 3}
        ]
        extract_items = {
            '合同名称': '风电合同',
            '含税金额': '100000'
        }
        
        locator = OptimizedLocator(text_list, extract_items)
        await locator.initialize()  # 显式初始化
        result = await locator.locator()
        print(result)
    
    asyncio.run(main())