# tool 基类
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称，只能包含 a-z, A-Z, 0-9, - 和 _"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具的详细描述，LLM 将依靠这段描述来决定是否调用该工具"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """遵循 JSON Schema 规范的参数定义"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """工具的具体执行逻辑，必须返回字符串形式的结果供 LLM 阅读"""
        pass

    def to_openai_function(self) -> Dict[str, Any]:
        """将工具转换为 OpenAI Function Calling 标准格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }