"""
统一日志封装。
所有模块通过 get_logger(__name__) 获取各自的 Logger 实例。
首次调用时自动完成全局日志配置初始化。
"""
import logging

_initialized = False


def get_logger(name: str) -> logging.Logger:
    """
    获取模块专属 Logger 实例。

    首次调用时会自动触发全局日志配置初始化（读取 config/logging_config.py）。
    后续调用直接返回对应名称的 Logger，不会重复初始化。

    Args:
        name: 模块名称，通常传入 __name__，使日志来源清晰可追溯。

    Returns:
        已配置好的 logging.Logger 实例。

    Example:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("模块启动")
    """
    global _initialized
    if not _initialized:
        from config.logging_config import setup_logging
        setup_logging()
        _initialized = True
    return logging.getLogger(name)
