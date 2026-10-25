# 修改导入语句
from extractor_pdf.utils.llm import get_llm_response_async
from extractor_pdf.utils.prompt_manager import prompt_manager
from extractor_pdf.errors.error_manager import ExtractError, LLMError
from extractor_pdf.utils.json_processor import json_processor
import asyncio
import re
from loguru  import logger
from extractor_pdf.config.settings import Config


class Extractor:
    def __init__(self,text):
        self.text = text

    EXTRACT_RULES = {
        '金额': ('extract_amout_prompt', ['金额']),
        '其他': ('extract_other_prompt', ['合同基本信息', '其他财务信息', '其他']),
        '时间信息': ('extract_time_prompt', ['时间信息']),
        '标的物': ('extract_prompt', ['标的物']),
        '交易主体': ('extract_trade_prompt', ['交易主体']),
        '主体': ('extract_subject', ['主体']),
    }

    THING_FIELDS = {
        'description': '标的物描述',
        'quantity': '数量',
        'quantity_unit': '数量单位',
        'unit_price': '单价',
        'price_unit': '单价单位'
    }

    def _parse_subject(self, response: dict | list) -> dict:  # TODO: prompt已经修改，需要做出对应的修改
        """处理主体信息的解析，对重复的主体信息进行合并和重命名

        Args:
            response: 解析后的响应数据，可能是字典或列表

        Returns:
            dict: 处理后的主体信息字典
        """
        response = self._parse_response(response)
        if isinstance(response, dict):
            return response

        subject_all = {}
        key_counts = {}

        for item in response:
            if item.get("相对方"):
                counterparty = item.get("相对方")
                if counterparty not in subject_all:
                    key_counts[counterparty] = 0
                key_counts[counterparty] += 1
                subject_all[f'{counterparty}{key_counts[counterparty]}名称'] = item.get("名称")
                subject_all[f'{counterparty}{key_counts[counterparty]}银行账号'] = item.get("银行账号")
                subject_all[f'{counterparty}{key_counts[counterparty]}开户行'] = item.get("开户行")
        return subject_all

    def _parse_thing(self, response: dict | list) -> dict:
        """处理标的物信息的解析，支持单个标的物或标的物列表的处理

        Args:
            response (Union[dict, list]): 解析后的响应数据，可能是字典或列表

        Returns:
            dict: 处理后的标的物信息字典

        Examples:
            >>> extractor._parse_thing({'标的物': [{'标的物描述': '商品A', '数量': '10'}]})
            {'标的物描述_0': '商品A', '数量_0': '10'}
        """
        try:
            response = self._parse_response(response)

            if isinstance(response, dict) and '标的物' in response:
                response = response['标的物']

            if isinstance(response, list):
                thing_all = {}
                for i, item in enumerate(response):
                    if not isinstance(item, dict):
                        logger.warning(f"跳过无效的标的物数据: {item}")
                        continue

                    # 使用字典推导式简化代码
                    thing_all.update({
                        f"{value}_{i}": item.get(value)
                        for field, value in self.THING_FIELDS.items()
                    })
                return {k: v for k, v in thing_all.items() if v is not None}
            else:
                return response if response else {}

        except Exception as e:
            logger.error(f"解析标的物信息时发生错误: {str(e)}")
            return {}

    async def _extract(self, text: str, type: str):
        """
        通用提取方法，根据传入的字段类型来抽取信息
        """
        if type not in self.EXTRACT_RULES:
            raise ValueError(f"不支持的提取类型: {type}")
        elif type == '主体':
            prompt = prompt_manager.get_prompt("extract_subject")+ '合同原文:```\n' + text
            response = await get_llm_response_async(prompt=prompt, max_tokens=Config.MAX_TOKEN)
            return self._parse_subject(response)
        elif type == '标的物':
            prompt = prompt_manager.get_prompt("extract_thing")+ '合同原文:```\n' + text
            response = await get_llm_response_async(prompt=prompt)
            return self._parse_thing(response)
        else:
            prompt_key, fields = self.EXTRACT_RULES[type]
            prompt_items = await self._assemble_prompt(fields)
            prompt = prompt_manager.get_prompt(prompt_key) + f"抽取要素要求如下:\n{prompt_items}\n\n合同原文为:```\n{text}\n```"
            response = await get_llm_response_async(prompt=prompt, max_tokens=Config.MAX_TOKEN)

        return self._parse_response(response)

    async def extract_subject(self, text: str):
        return await self._extract(text, '主体')

    async def extract_amout(self, text):
        return await self._extract(text, '金额')

    async def extract_other(self, text):
        return await self._extract(text, '其他')

    async def extract_time(self, text):
        return await self._extract(text, '时间信息')

    async def extract_thing(self, text):
        return await self._extract(text, '标的物')

    async def extract_transaction(self, text):
        return await self._extract(text, '交易主体')

    async def _assemble_prompt(self, config):
        """
        情况一:抽取一个分类的所有字段:config = ["金额"]
        情况二:抽取一个分类下某个字段:config = ["合同基本信息:合同名称"]
        """
        if not config:
            raise ValueError("缺少config参数")

        explain_lines = []

        for item in config:
            try:
                if ':' in item:
                    category, field_name = item.split(':', 1)
                    info = prompt_manager.get_items_prompt(category, field_name)
                    if not info:
                        logger.warning(f"未找到字段 [{field_name}] 在分类 [{category}] 中的定义，跳过")
                        continue
                    explain = info.get('explain', '')
                    template = info.get('template', [])
                    line = f"{field_name}"
                    if explain:
                        line += f": {explain}"
                    if template:
                        line += f"[{','.join (template)}]"
                    explain_lines.append(f"- {line}")
                else:
                    category = item
                    cat_dict = prompt_manager.get_items_prompt(category)
                    if not cat_dict:
                        logger.warning(f"未找到分类 [{category}] 的定义，跳过")
                        continue
                    explain_lines.append(f"-【{category}】")
                    for field_name, info in cat_dict.items():
                        explain = info.get('explain', '')
                        template = info.get('template', [])
                        line = f"{field_name}"
                        if explain:
                            line += f": {explain}"
                        if template:
                            line += f"[{','.join (template)}]"
                        explain_lines.append(f"- {line}")
            except:
                ExtractError(f"提取失败 -- {item}")
                continue

        return '\n'.join(explain_lines)

    @staticmethod
    def _parse_response(response):
        if not response:
            raise LLMError("大模型返回结果为空")
        tmp_response = re.search(r'```[\w\W]*```', response)
        if tmp_response:
            response = tmp_response.group(0)
        response = response.strip('```')
        response = re.sub(r'(python|json)(\n)?', '', response)
        return json_processor.parse_json(response)


if __name__ == "__main__":
    text = """
    第五条 支付条款
    付款方为甲方北京某某科技有限公司，收款方为乙方上海某某信息技术有限公司。资金流向为从甲方账户支付至乙方账户。结算客商为中国工商银行股份有限公司北京分行。

    第六条 银行信息
    开户银行：中国工商银行
    银行账号：1001 2002 3003 4004
    户名：上海某某信息技术有限公司
    """
    async def main():
        extractor = Extractor(text=text)
        result = await extractor.extract_transaction(text)
        print(result)
    asyncio.run(main())
