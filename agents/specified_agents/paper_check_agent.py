from typing import List, Optional, Union
from agents.base_agent import BaseAgent
from agents.simple_agent import SimpleAgent
from core.message import AgentMessage
from core.exceptions import AgentError
from tools.base_tool import BaseTool
from config.settings import settings
from utils.logger import get_logger
from tools.pdf_comment_tool import PdfCommentTool
import json

MODEL_NAME = "gemini-3.1-flash-lite-preview"
API_KEY = None
TEMPERATURE = 0.2

MODE = "release"

SYSTEM_PROMPT = """你是一个专业的论文检查助手，你的任务是根据用户提供的论文要求，对用户以PDF格式给出的论文进行检查，找出论文中所有不符合要求的问题，并在总结中按指定格式逐条列出问题相关信息。
论文要求：
{rules}

你的回答应该严格按照以下要求：
   RESULT [BEGIN [{{“page_idx": 【问题1在论文中的页码】, "text": 【问题1需要高亮的原文内容】, "comment": 【问题1的不符合要求的原因】}}, {{“page_idx": 【问题2在论文中的页码】, "text": 【问题2需要高亮的原文内容】, "comment": 【问题2的不符合要求的原因】}}, ...] END]

   RESULT 是结果标记，其后用中括号包围结果，中括号内被BEGIN标记和END标记包围的即为回答的核心内容——问题列表，问题列表是一个字典列表，每个字典包含了一个问题的所有信息：
   1. page_idx：问题在原论文中的页码，数值类型。
   2. text：原文中需要高亮的文本，必须在字符串层面上严格匹配原文内容，字符串类型。
   3. comment：当前论文内容存在的问题，字符串类型。
   问题列表应该严格符合python的json格式，确保可以直接转换成字典类型，且每个值的数据类型与定义匹配。不要遗漏包围结果的中括号和BEGIN标记，END标记。
   论文/原文均指用户上传的PDF附件，不是上面的论文要求。text字段必须严格匹配附件中原文内容，idx字段是text字段在附件中原文的页码。
   由于PDF中等特殊格式可能出现无法匹配的问题，在text字段中尽量不要包含角标等特殊格式，可以考虑高亮原文中其他无特殊格式的文本或在特殊格式前截断。
   json解析器要求正确使用转义字符'\\'，如果原文中有字符'\\'(如latex公式中），在返回的对应text字段中应该用'\\\\'替代，以便于json解析器正确解析字符串。
   问题列表中的问题最好按照在原文中出现的顺序排列，先出现的在前，后出现的在后。

   举例：
   如果你认为论文存在以下问题：
   1. 论文序号为1的页码中，原文”We use prior work to show that the proposed method is effective.”这句话缺少文献引用，
   2. 论文序号为2的页码中，原文”Here is the proposed method.” 处对方法的描述缺少详细的解释。
   则返回：
   RESULT [BEGIN [{{“page_idx": 1, "text": "We use prior work to show that the proposed method is effective.", "comment": "缺少文献引用"}}, {{“page_idx": 2, "text": "Here is the proposed method.", "comment": "缺少详细的解释"}}] END]
   例子中的描述仅供格式参考，具体要求参考上面的论文要求。
   注意每个问题的text字段必须严格匹配原文内容，是你认为有问题的原文的内容，可以是词，句子或段落，但必须在字符串意义上匹配原文存在的内容；comment字段必须是问题的不符合要求的原因，是你自己生成的内容。
   
   如果论文没有任何问题，按照如下形式给出空的问题列表即可：
    RESULT [BEGIN [] END]
不要给出除以上定义的格式外其他任何格式的回复。"""

class PaperCheckAgent(SimpleAgent):
    def __init__(
        self,
        name: str,
        rules_path: str,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = None,
        max_history: int = 100,
    ):
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                rules = f.read()
        except FileNotFoundError:
            raise RuntimeError(f"论文要求文件 {rules_path} 不存在")
        except Exception as e:
            raise RuntimeError(f"读取论文要求文件 {rules_path} 时出错: {e}") from e
        
        tools = [PdfCommentTool()]   
        tools_info_list = []
        for tool in tools:
            tools_info_list.append({"tool_name": tool.name, "tool_description": tool.description, "tool_input_schema": tool.input_schema})
        system_prompt = SYSTEM_PROMPT.format(rules=rules)
        super().__init__(
            name = name, 
            system_prompt = system_prompt, 
            tools = tools, 
            model_name = model_name or MODEL_NAME, 
            api_key = api_key or API_KEY,
            temperature = temperature or TEMPERATURE,
            max_history = max_history
        )

    def paper_check(self, message: AgentMessage) -> AgentMessage:
        llm_content = self.run(message).content
        begin_index = llm_content.find("BEGIN")
        end_idx = llm_content.find("END")
        if begin_index != -1 and end_idx != -1:
            # 直接回答，提取结果
            question_list_str = llm_content[begin_index + len("BEGIN"):end_idx].strip()
            print(f"问题列表字符串: {question_list_str}")
        else:
            raise RuntimeError("模型回复中未包含问题列表")
                    
        question_list = json.loads(question_list_str)
        tool_result = self.call_tool("pdf_comment", {"question_list": question_list})

        return AgentMessage(
            role="assistant",
            content=tool_result.output,
        )

if __name__ == "__main__":
    rules_path = r"C:\Users\86138\Downloads\thesis-checklists.md"
    paper_check_agent = PaperCheckAgent(name="paper_check_agent", rules_path=rules_path)
    pdf_path = r"C:\Users\86138\Downloads\AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework.pdf"
    output_path = r"C:\Users\86138\Downloads\AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework0.pdf"
    msg = AgentMessage(
        role="user",
        content="",
        metadata={"attachment": [pdf_path], "tool_args": {"pdf_comment": {"pdf_path": pdf_path, "output_path": output_path}}},
    )
    response = paper_check_agent.paper_check(msg)
    print(response.content)
