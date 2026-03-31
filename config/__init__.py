# ============================================================
# config/__init__.py
# 配置模块初始化入口
# ============================================================
# 本模块负责统一导出所有配置对象，供全局调用。
# 外部模块只需 `from config import settings` 即可获取配置。
#
# 【需要实现的内容】
# - 延迟加载 settings 单例，避免启动时就触发环境变量校验
# - 提供 reload_settings() 方法，支持测试时动态切换配置
# - 捕获配置加载异常并给出友好提示
# ============================================================
from typing import Any

from config.settings import Settings, get_settings
from config.agent_configs import get_agent_config
from config.model_configs import ModelConfig, get_model_config
from config.logging_config import setup_logging
from config.logging_config import debug_print, log_execution_time

__all__ = [
    "Settings",
    "get_settings",
    "setup_logging",
    "debug_print",
    "log_execution_time",
    "reload_settings",
    "settings",  # 把 settings 加入对外暴露列表
]

settings = get_settings()

def reload_settings() -> Settings:
    """重新加载配置，用于测试时动态切换环境"""
    global settings
    get_settings.cache_clear()  # 清除 lru_cache 的缓存
    settings = get_settings()
    return settings