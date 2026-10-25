import json
import re
import ast
from typing import Dict, List, Union
from extractor_pdf.errors.error_manager import JSONProcessError
from extractor_pdf.utils.decorators import singleton
import logging
logger = logging.getLogger(__name__)
# logging.basicConfig(
#     level=logging.DEBUG,  # 这行是关键
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

@singleton
class JSONProcessor:
    """JSON处理器，用于处理大模型返回的JSON字符串"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_json(self, json_str: str) -> Union[Dict, List]:
        """将字符串解析为JSON数据结构（字典或列表）
        
        Args:
            json_str: 要解析的JSON格式字符串
            
        Returns:
            Union[Dict, List]: 解析后的Python对象（字典或列表）
            
        Raises:
            JSONProcessError: 当JSON字符串解析失败时抛出
        """
        # 首先尝试直接转换清理后的字符串
        tmp_json_str = json_str.replace('json', '').replace('```', '').replace('python', '')
        try:
            return json.loads(tmp_json_str)
        except json.JSONDecodeError:
            self.logger.debug('直接解析json失败')

        try:
            eval_result = ast.literal_eval(tmp_json_str.strip())
            return eval_result
        except (ValueError, SyntaxError) as e2:
            self.logger.debug(f"ast.literal_eval 失败: {e2}")
        
        try:
            # 如果失败，进行更复杂的处理
            tmp_json_str = self.fix_json_format_errors(tmp_json_str)
            return json.loads(tmp_json_str)
        except (json.JSONDecodeError, Exception):
            logger.debug('清洗了json字符串也失败')
        
        try:
            if tmp_json_str[-1] != '}':
                tmp_json_str = ','.join(tmp_json_str.split(',')[:-1])
                tmp_json_str = tmp_json_str + '}' if tmp_json_str[-1] != '}' else tmp_json_str
                if tmp_json_str[0] == '[':
                    tmp_json_str += ']'
            return json.loads(tmp_json_str)
        except:
            self.logger.error(f"字符串{tmp_json_str} 解析成JSON失败")
            raise JSONProcessError(f"无法解析JSON字符串")
            
    def get_json_str(self, json_str: str) -> str:
        """获取JSON字符串"""
        tmp_response = re.search(r'```[\w\W]*```', json_str)
        if tmp_response:
            json_str = tmp_response.group(0).strip('```')
            json_str = re.sub(r'(python|json)(\n)?', '', json_str)
        return json_str.strip()

    def fix_json_format_errors(self, json_str: str) -> str:
        """修复JSON格式错误"""
        try:
            # 1. 处理键的引号问题（将单引号键转换为双引号）
            json_str = re.sub(r"'([^']+)'(\s*:)", r'"\1"\2', json_str)
            
            # 2. 处理数字后带单位的值（如：100元, 50%）
            json_str = re.sub(r':\s*(\d+[元%]?)(?=\s*[,\n}])', r': "\1"', json_str)    
            
            # 3. 处理列表中未加引号的特殊格式（如：[69-1-2-0]）
            def quote_list_items(match):
                content = match.group(1)
                items = content.split(',')
                quoted_items = []
                for item in items:
                    item = item.strip()
                    # 如果是纯数字，不加引号
                    if re.match(r'^\d+$', item):
                        quoted_items.append(item)
                    # 如果包含特殊字符（如连字符），加引号
                    else:
                        # 清理item中的多余引号
                        item = re.sub(r'[\'"]', '', item)
                        quoted_items.append(f'"{item}"')
                return '[' + ','.join(quoted_items) + ']'
            
            json_str = re.sub(r'\[(.*?)\]', quote_list_items, json_str)
            
            # 4. 处理值的引号问题
            def replace_value_quotes(match):
                value = match.group(1)
                # 清理value中的多余引号
                value = re.sub(r'[\'"]', '', value)
                return f': "{value}",'
            
            json_str = re.sub(r':\s*\'([^\']+)\'(?=\s*\n)', replace_value_quotes, json_str)
            
            # 5. 处理末尾多余的逗号
            json_str = re.sub(r',(\s*})', r'\1', json_str)
            json_str = re.sub(r',(\s*])', r'\1', json_str)

            # 6. 处理所有引号问题
            json_str = re.sub(r'\["+\]', '[]', json_str)  # 处理空数组
            json_str = re.sub(r'"{2,}([\w-]+)"{2,}', r'"\1"', json_str)  # 处理多重引号
            json_str = re.sub(r"(?<!\")'([^']*)'(?!\")", r'"\1"', json_str)  # 处理单引号
        
        except Exception as e:
            raise JSONProcessError(f"修复JSON格式失败: {str(e)}")
        
        return json_str.strip()


    def save_json(self, data: Dict, path: str) -> None:
        """保存数据为JSON文件"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            self.logger.error(f"保存JSON文件失败 {path}: {str(e)}")
            raise

    def load_json(self, path: str) -> Dict:
        """加载JSON文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except IOError as e:
            self.logger.error(f"读取JSON文件失败 {path}: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"解析JSON文件失败 {path}: {str(e)}")
            raise

json_processor = JSONProcessor()