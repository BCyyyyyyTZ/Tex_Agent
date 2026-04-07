"""
日志配置模块。
统一管理日志级别、格式与输出目标，其他模块通过 utils/logger.py 获取 Logger 实例。
"""
import logging
import logging.config
from typing import Dict, Any


def get_logging_config(log_level: str = "INFO", log_format: str = "") -> Dict[str, Any]:
    """
    构建并返回 logging 配置字典。

    Args:
        log_level: 日志级别字符串（DEBUG / INFO / WARNING / ERROR）
        log_format: 日志格式字符串

    Returns:
        符合 logging.config.dictConfig 规范的配置字典
    """
    if not log_format:
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": log_format,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
    }


def setup_logging() -> None:
    """初始化全局日志配置，从 settings 读取参数。"""
    from config.settings import settings
    config = get_logging_config(settings.log_level, settings.log_format)
    logging.config.dictConfig(config)
