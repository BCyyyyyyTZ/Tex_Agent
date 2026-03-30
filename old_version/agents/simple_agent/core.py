import os
import json
from openai import OpenAI
from agents.base_agent import BaseAgent
from prompt.simple_agent_prompt import SIMPLE_AGENT_SYSTEM_PROMPT

class SimpleAgent(BaseAgent):
    def __init__(self, tools: list = None):
        super().__init__(name="SimpleAgent")
        # 假设我们使用兼容 OpenAI 接口的模型 (如 DeepSeek, 通义千问, 或 OpenAI 本身)
        # API Key 会在 main.py 启动时通过 load_dotenv() 加载到环境变量中
        self.client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL")
        )

        # 装载工具箱
        self.tools = tools or []
        # 将我们自定义的工具转为 OpenAI 认识的格式
        self.openai_tools = [tool.to_openai_function() for tool in self.tools] if self.tools else None
        
        # 建立工具名称到实例的映射，方便后续执行
        self.tool_map = {tool.name: tool for tool in self.tools}

    def run(self, task_input: str, **kwargs) -> dict:
        print(f"[DEBUG: {self.name}] 正在处理任务...")
        messages = [
            {"role": "system", "content": SIMPLE_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": task_input}
        ]

        try:
            # 第一轮对话：大模型判断是否需要调用工具
            response = self.client.chat.completions.create(
                model=os.environ.get("DEEPSEEK_MODEL", "gpt-3.5-turbo"),
                messages=messages,
                tools=self.openai_tools,
                tool_choice="auto", # 让大模型自己决定是否调用
                temperature=0.1
            )
            
            response_message = response.choices[0].message
            
            # 如果大模型觉得不需要调用工具，直接返回文本
            if not response_message.tool_calls:
                return {"status": "success", "agent_used": self.name, "result": response_message.content}

            # 如果大模型决定调用工具
            messages.append(response_message) # 把助手的调用请求存入上下文
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # 执行本地的 Python 函数
                if function_name in self.tool_map:
                    tool_instance = self.tool_map[function_name]
                    tool_result = tool_instance.execute(**function_args)
                else:
                    tool_result = f"Error: Tool {function_name} not found."
                
                # 将工具执行的结果追加到上下文中
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_result,
                })

            # 第三轮对话：大模型拿到工具返回的数据后，进行最终的总结归纳
            print(f"[{self.name}] 工具执行完毕，正在生成最终回答...")
            final_response = self.client.chat.completions.create(
                model=os.environ.get("DEEPSEEK_MODEL"),
                messages=messages,
                temperature=0.3
            )
            
            return {
                "status": "success",
                "agent_used": self.name,
                "result": final_response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                "status": "error",
                "agent_used": self.name,
                "result": str(e)
            }