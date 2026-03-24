import os
from openai import OpenAI
from agents.base_agent import BaseAgent
from prompt.simple_agent_prompt import SIMPLE_AGENT_SYSTEM_PROMPT

class SimpleAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SimpleAgent")
        # 假设我们使用兼容 OpenAI 接口的模型 (如 DeepSeek, 通义千问, 或 OpenAI 本身)
        # API Key 会在 main.py 启动时通过 load_dotenv() 加载到环境变量中
        self.client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL")
        )

    def run(self, task_input: str, **kwargs) -> dict:
        print(f"[DEBUG: {self.name}] 正在处理任务...")
        try:
            response = self.client.chat.completions.create(
                model=os.environ.get("DEEPSEEK_MODEL"),
                messages=[
                    {"role": "system", "content": SIMPLE_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": task_input}
                ],
                temperature=0.3
            )
            result_text = response.choices[0].message.content
            
            return {
                "status": "success",
                "agent_used": self.name,
                "result": result_text
            }
            
        except Exception as e:
            return {
                "status": "error",
                "agent_used": self.name,
                "result": str(e)
            }