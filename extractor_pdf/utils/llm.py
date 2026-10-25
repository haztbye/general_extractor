from typing import Optional, List, Dict, Any
import json
import asyncio
import time
from openai import OpenAI, AsyncOpenAI
from extractor_pdf.config.settings import Config
from loguru import logger

# 使用配置类中的变量
LLM_SERVICE_URL = Config.LLM_SERVICE_URL
LLM_SERVICE_API_KEY = Config.LLM_SERVICE_API_KEY
MODEL_NAME = Config.MODEL_NAME
MAX_CONCURRENT_REQUESTS = Config.MAX_CONCURRENT_REQUESTS

# 创建信号量
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def _require_key() -> None:
    if not LLM_SERVICE_API_KEY:
        raise RuntimeError(
            "未配置 LLM_SERVICE_API_KEY：请在项目根目录创建 .env 并填入你的 key"
            "（模板见 .env.example），或设置环境变量 LLM_SERVICE_API_KEY。"
        )


def _build_messages(prompt: str, conversation: str, system_prompt: str) -> List[Dict[str, str]]:
    """构建消息列表"""
    conversation_list: List = json.loads(conversation)
    if len(conversation_list) > 1 and conversation_list[0].get('role', '') == "system":
        return conversation_list + [{"role": "user", "content": prompt}]
    return [{"role": "system", "content": system_prompt}] + conversation_list + [{"role": "user", "content": prompt}]


def _build_request_body(messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> Dict[str, Any]:
    """构建请求体"""
    body = {
        "messages": messages,
        "model": MODEL_NAME,
        "stream": True,
        "temperature": temperature,
        "top_p": 0.85
    }
    if max_tokens:
        body.update({"max_tokens": max_tokens})
    return body


def get_llm_response(prompt: str = '', temperature: float = 0.01, conversation: str = '[]', max_tokens: int = 500,
                    system_prompt: str = "你是一个专业的合同评审专家，精通合同的分析与审核。") -> str:
    """获取大模型的回答（同步版本，任意 OpenAI 兼容服务）"""
    _require_key()
    try:
        messages = _build_messages(prompt, conversation, system_prompt)
        body = _build_request_body(messages, temperature, max_tokens)
        client = OpenAI(
            base_url=LLM_SERVICE_URL,
            api_key=LLM_SERVICE_API_KEY,
            timeout=Config.DEFAULT_TIMEOUT,
        )
        response = client.chat.completions.create(**body)
        full = ''
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                full += chunk.choices[0].delta.content
        return full
    except Exception as e:
        logger.error(f"获取大模型回答失败: {str(e)}")
        raise Exception(f"获取大模型回答失败: {str(e)}")


async def get_llm_response_async(prompt: str = '', max_tokens: int = 0, temperature: float = 0.01, conversation: str = '[]',
                               system_prompt: str = "你是一个专业的合同评审专家，精通合同的分析与审核。") -> Optional[str]:
    """获取大模型的回答（异步版本，任意 OpenAI 兼容服务）"""
    _require_key()
    start_time = time.time()
    logger.debug(f"开始LLM请求，prompt长度: {len(prompt)}")

    async with _semaphore:  # 使用信号量控制并发
        try:
            messages = _build_messages(prompt, conversation, system_prompt)
            body = _build_request_body(messages, temperature, max_tokens)
            client = AsyncOpenAI(
                base_url=LLM_SERVICE_URL,
                api_key=LLM_SERVICE_API_KEY,
                timeout=Config.DEFAULT_TIMEOUT,
            )
            response = await client.chat.completions.create(**body)
            full = ""
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    full += chunk.choices[0].delta.content
            end_time = time.time()
            logger.debug(f"LLM请求完成，耗时: {end_time - start_time:.2f}秒")
            return full
        except Exception as e:
            end_time = time.time()
            logger.error(f"LLM请求失败，耗时: {end_time - start_time:.2f}秒, 错误: {str(e)}")
            raise


if __name__ == "__main__":
    prompt = '你好'
    start_time = time.time()
    response_llm = get_llm_response(prompt)
    print(response_llm)
    print(f"同步请求时间: {time.time() - start_time}秒")
