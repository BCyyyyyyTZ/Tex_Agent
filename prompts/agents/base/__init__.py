# Tex/prompts/agents/base/__init__.py

# 导入 Simple Agent 的提示词
from .simple_agent_prompt import SIMPLE_AGENT_SYSTEM_PROMPT

# 导入 ReAct Agent 的提示词
from .react_prompt import (
    REACT_SYSTEM_PROMPT, 
    REACT_REASON_PROMPT
)

# 导入 Reflection Agent 的提示词
from .reflection_prompt import (
    INITIAL_PROMPT_TEMPLATE, 
    REFLECT_PROMPT_TEMPLATE, 
    REFINE_PROMPT_TEMPLATE
)

# 导入 Plan and Solve Agent 的提示词
from .plan_and_solve_prompt import (
    PLAN_PROMPT, 
    SOLVE_PROMPT, 
    MERGE_PROMPT
    # 注意：这里忽略了它内部同名的 SIMPLE_AGENT_SYSTEM_PROMPT，避免冲突
)

# 显式声明该模块导出的变量（有助于 IDE 提示和规范规范）
__all__ = [
    # Simple
    "SIMPLE_AGENT_SYSTEM_PROMPT",
    
    # ReAct
    "REACT_SYSTEM_PROMPT",
    "REACT_REASON_PROMPT",
    
    # Reflection
    "INITIAL_PROMPT_TEMPLATE",
    "REFLECT_PROMPT_TEMPLATE",
    "REFINE_PROMPT_TEMPLATE",
    
    # Plan and Solve
    "PLAN_PROMPT",
    "SOLVE_PROMPT",
    "MERGE_PROMPT"
]