"""
空闲润色 Prompt 构建（阶段 8）。
"""
from typing import Optional

LATEX_POLISH_SYSTEM_PROMPT = """你是一个专业的学术论文润色助手。
你的任务是对用户提供的 LaTeX 文本片段进行语言润色。
要求：
1. 保持原有的 LaTeX 格式和宏命令不变。
2. 提升英语表达的地道性、学术性和流畅度。
3. 修正语法、拼写和标点错误。
4. 如果原文已经很好，可以不提供修改建议。
5. 必须以 JSON 格式返回结果，包含 rationale_zh (中文修改理由) 和 replacement (润色后的 LaTeX 代码)。如果不需要修改，replacement 留空。

输出 JSON 格式示例：
{
  "rationale_zh": "将口语化表达替换为更正式的学术用语，并修正了主谓一致错误。",
  "replacement": "The proposed method demonstrates superior performance..."
}
"""

def build_polish_prompt(
    text_snippet: str,
    file_path: str,
    checklist: Optional[dict] = None
) -> str:
    """
    构建润色 Prompt。
    附加阶段 A 预留了 checklist 接口，如果提供，则将其纳入要求。
    """
    prompt = f"请润色以下来自文件 `{file_path}` 的 LaTeX 文本片段：\n\n```latex\n{text_snippet}\n```\n"
    
    if checklist:
        prompt += "\n此外，请特别注意以下审稿/写作要求：\n"
        for key, value in checklist.items():
            prompt += f"- {key}: {value}\n"
            
    return prompt
