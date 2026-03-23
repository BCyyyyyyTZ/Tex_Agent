# agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, task_input: str, **kwargs) -> Dict[str, Any]:
        """
        所有子类Agent都必须实现这个方法。
        :param task_input: 用户的自然语言输入或具体任务描述
        :param kwargs: 其他可能需要的参数（如文件路径等）
        :return: 统一返回一个字典，包含 'status' 和 'result'
        """
        pass