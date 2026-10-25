from environs import Env
from loguru import logger

# 初始化环境变量解析器
env = Env()

# 尝试读取 .env 文件（从当前目录向上递归查找），不存在则忽略
try:
    env.read_env(recurse=True)
    logger.info(".env文件已加载")
except FileNotFoundError:
    logger.warning(".env未找到，使用系统环境变量或默认值（参考 .env.example）")


class Config:
    """LLM 与抽取行为配置（个人版）。

    所有项均可通过 .env 或环境变量覆盖。LLM 接口为任意 OpenAI 兼容服务：
    智谱 / DeepSeek / OpenAI / 本地 Ollama 均可。
    """
    # LLM 服务配置（默认智谱，免费模型最容易跑通；key 必须自己配）
    LLM_SERVICE_URL = env.str("LLM_SERVICE_URL", default="https://open.bigmodel.cn/api/paas/v4")
    LLM_SERVICE_API_KEY = env.str("LLM_SERVICE_API_KEY", default="")
    MODEL_NAME = env.str("MODEL_NAME", default="glm-4-flash")

    # 性能参数
    MAX_TOKEN = env.int("MAX_TOKEN", default=500)

    # 并发控制（同时进行的 LLM 请求数）
    MAX_CONCURRENT_REQUESTS = env.int("MAX_CONCURRENT_REQUESTS", default=5)

    # 单次请求超时（秒）
    DEFAULT_TIMEOUT = env.int("DEFAULT_TIMEOUT", default=120)


def check_llm_ready() -> bool:
    """检查 LLM 配置是否可用（CLI 启动时提示用，不在 import 时强制）。"""
    if not Config.LLM_SERVICE_API_KEY:
        logger.warning(
            "未配置 LLM_SERVICE_API_KEY：请在项目根目录创建 .env 并填入你的 key"
            "（模板见 .env.example），或设置环境变量。"
        )
        return False
    return True


logger.info("配置加载成功:")
logger.info(f"  LLM_SERVICE_URL: {Config.LLM_SERVICE_URL}")
logger.info(f"  MODEL_NAME: {Config.MODEL_NAME}")
logger.info(f"  LLM_SERVICE_API_KEY: {'已配置' if Config.LLM_SERVICE_API_KEY else '未配置（调用 LLM 前需在 .env 中填写）'}")


class SimpleExtractionConfig:
    """core2 通用抽取所用的配置（与 Config 保持同源）。"""

    LLM_SERVICE_URL = Config.LLM_SERVICE_URL
    LLM_SERVICE_API_KEY = Config.LLM_SERVICE_API_KEY
    MODEL_NAME = Config.MODEL_NAME
    MAX_CONCURRENT_REQUESTS = Config.MAX_CONCURRENT_REQUESTS

    DEFAULT_TEMPERATURE = 0.1        # 默认温度参数（低随机性）
    TIMEOUT_SECONDS = Config.DEFAULT_TIMEOUT
    MAX_RETRIES = 2                  # 最大重试次数

    # 字段类型映射
    FIELD_TYPE_NAMES = {
        0: "文本",
        1: "多行文本",
        2: "数字",
        3: "金额",
        4: "日期",
        5: "我方单位名称",
        6: "对方单位名称",
        7: "单选",
        8: "多选"
    }

    @classmethod
    def get_field_type_name(cls, field_type: int) -> str:
        """获取字段类型名称"""
        return cls.FIELD_TYPE_NAMES.get(field_type, "未知类型")
