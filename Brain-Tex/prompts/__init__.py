# Tex/prompts/__init__.py

# 导入具体的子模块命名空间，方便外部直接通过 prompts.base_agents 访问
from .agents import base as base_agents
# 未来你可以继续加：
# from .agents import specialized as specialized_agents
# from .skills import academic as academic_skills

__all__ = [
    "base_agents",
]