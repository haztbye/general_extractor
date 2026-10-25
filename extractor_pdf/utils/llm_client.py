# 大模型集成模块 - 基于用户提供的代码适配
import os
import logging
import json
import asyncio
from openai import OpenAI, AsyncOpenAI
from typing import Optional, List, Dict, Any
import time
from loguru import logger

# 导入配置
from extractor_pdf.config.settings import SimpleExtractionConfig

# 创建信号量控制并发
_semaphore = asyncio.Semaphore(SimpleExtractionConfig.MAX_CONCURRENT_REQUESTS)


def _require_key() -> None:
    if not SimpleExtractionConfig.LLM_SERVICE_API_KEY:
        raise RuntimeError(
            "未配置 LLM_SERVICE_API_KEY：请在项目根目录创建 .env 并填入你的 key"
            "（模板见 .env.example），或设置环境变量 LLM_SERVICE_API_KEY。"
        )

def _build_messages(prompt: str, conversation: str, system_prompt: str) -> List[Dict[str, str]]:
    """构建消息列表 - 基于用户提供的代码"""
    try:
        conversation_list: List = json.loads(conversation)
        if len(conversation_list) > 1 and conversation_list[0].get('role', '') == "system":
            return conversation_list + [{"role": "user", "content": prompt}]
        return [{"role": "system", "content": system_prompt}] + conversation_list + [{"role": "user", "content": prompt}]
    except json.JSONDecodeError:
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

def _build_request_body(messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> Dict[str, Any]:
    """构建请求体 - 基于用户提供的代码"""
    body = {
        "messages": messages,
        "model": SimpleExtractionConfig.MODEL_NAME,
        "temperature": temperature,
        "stream": True,
        "top_p": 0.85
    }
    if max_tokens:
        body.update({"max_tokens": max_tokens})
    return body

def get_llm_response(prompt: str = '', temperature: float = 0.01, conversation: str = '[]', max_tokens: int = 500,
                    system_prompt: str = "你是一个专业的合同字段抽取专家，擅长从合同文档中精确提取结构化信息。") -> str:
    """
    获取大模型的回答（同步版本） - 基于用户提供的代码
    
    Args:
        prompt: 提示文本
        temperature: 温度参数
        conversation: 对话历史
        max_tokens: 最大token数
        system_prompt: 系统提示
        
    Returns:
        str: 模型响应文本
    """
    try:
        _require_key()
        messages = _build_messages(prompt, conversation, system_prompt)
        full = ''
        body = _build_request_body(messages, temperature, max_tokens)

        client = OpenAI(
            base_url=SimpleExtractionConfig.LLM_SERVICE_URL,
            api_key=SimpleExtractionConfig.LLM_SERVICE_API_KEY,
            timeout=SimpleExtractionConfig.TIMEOUT_SECONDS
        )
        
        response = client.chat.completions.create(**body)
        
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta is not None:
                full += delta
                
        return full
    except Exception as e:
        logging.error(f"获取大模型回答失败: {str(e)}")
        raise Exception(f"获取大模型回答失败: {str(e)}")

async def get_llm_response_async(prompt: str = '', max_tokens: int = 0, temperature: float = 0.01, 
                               conversation: str = '[]', system_prompt: str = "你是一个专业的合同字段抽取专家。") -> Optional[str]:
    """
    获取大模型的回答（异步版本） - 基于用户提供的代码
    
    Args:
        prompt: 提示文本
        max_tokens: 最大token数
        temperature: 温度参数
        conversation: 对话历史
        system_prompt: 系统提示
        
    Returns:
        Optional[str]: 模型响应文本或None
    """
    start_time = time.time()
    logger.debug(f"开始LLM请求，prompt长度: {len(prompt)}")
    
    async with _semaphore:  # 使用信号量控制并发
        try:
            _require_key()
            messages = _build_messages(prompt, conversation, system_prompt)
            body = _build_request_body(messages, temperature, max_tokens)

            client = AsyncOpenAI(
                base_url=SimpleExtractionConfig.LLM_SERVICE_URL,
                api_key=SimpleExtractionConfig.LLM_SERVICE_API_KEY,
                timeout=SimpleExtractionConfig.TIMEOUT_SECONDS
            )
            
            try:
                response = await client.chat.completions.create(**body)
                full = ""
                async for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        full += chunk.choices[0].delta.content
                end_time = time.time()
                logger.debug(f"LLM请求完成，耗时: {end_time - start_time:.2f}秒")
                return full
            except Exception as e:
                end_time = time.time()
                logger.error(f"LLM请求失败，耗时: {end_time - start_time:.2f}秒, 错误: {str(e)}")
                raise Exception(f"OpenAI API调用失败: {str(e)}")
        except Exception as e:
            end_time = time.time()
            logger.error(f"LLM请求失败，耗时: {end_time - start_time:.2f}秒, 错误: {str(e)}")
            raise

# 简单抽取专用的同步调用函数
def extract_fields_with_llm(formdoc_content: str, field_configs: List, system_prompt: str = None) -> str:
    """
    使用大模型进行字段抽取（同步版本）
    
    Args:
        formdoc_content: 合同文档内容
        field_configs: 字段配置列表
        system_prompt: 自定义系统提示
        
    Returns:
        str: 模型返回的JSON字符串
    """
    from extractor_pdf.utils.prompt_builder import PromptEngineer
    
    # 构建提示
    prompt = PromptEngineer.build_extraction_prompt(formdoc_content, field_configs)
    
    # 设置默认系统提示
    if system_prompt is None:
        system_prompt = "你是一个专业的合同字段抽取专家，擅长从合同文档中精确提取结构化信息。请确保返回纯JSON格式。"
    
    # 调用大模型
    response = get_llm_response(
        prompt=prompt,
        temperature=SimpleExtractionConfig.DEFAULT_TEMPERATURE,
        system_prompt=system_prompt,
        max_tokens=1000
    )
    
    return response
