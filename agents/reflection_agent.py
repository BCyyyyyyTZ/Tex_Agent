"""
[扩展] ReflectionAgent 接口定义。
实现自我反思迭代模式：生成初始答案后，通过批判性反思机制识别不足并迭代改进。

TODO: 开发者 B 负责实现此类（第一阶段任务）
"""
from abc import abstractmethod
from typing import Optional
from typing import List, Optional, Union

from agents.base_agent import BaseAgent
from agents.simple_agent import SimpleAgent
from core.message import AgentMessage
from tools.base_tool import BaseTool
from tools.tool_list import tool_list

MODEL_NAME = "llama-3.3-70b-versatile"
API_KEY = ""
BASE_URL = "https://api.groq.com/openai/v1"
TEMPERATURE = 0.2

MODE = "release"

EXECUTOR_SYSTEM_PROMPT = """你是一个专业的助手，你的任务是根据用户的问题和可能提供的对历史回复的修改意见，使用工具列表中的工具来回答用户的问题或结合修改意见修改历史回复。
工具列表：{tools}
工具列表中每个工具包含三个属性：
1. tool_name：工具唯一标识名
2. tool_description：工具的描述，用于说明工具的功能和适用场景。
3. tool_input_schema：工具的输入参数规约，用于定义工具的输入参数格式。对于每个参数，包含 arg_name:参数名 和 arg_description:参数描述，必填参数有必填标识，必须填入；可选参数有可选标识，需要时填入。
你的回答应该满足如下要求：
1. 如果你认为当前信息已经足够给出答案，则直接给出结果，按照如下格式回答问题，注意把回答的内容用英文中括号包围：
   RESULT [回答的内容]
2. 如果你认为当前信息不足以给出答案，则使用工具列表中的工具来获取缺失信息，按照如下格式调用工具，注意把工具名称和工具输入参数用英文中括号包围：
   TOOL_NAME [工具名称]
   TOOL_INPUT [工具输入参数]
   其中，工具名称必须字符串意义上匹配对应工具列表中工具的 tool_name 属性，工具输入参数必须符合工具列表中对应工具的 tool_input_schema 属性要求
   例如工具列表如下：[{{"tool_name": "arxiv_search", "tool_description": "搜索 arXiv 论文", "tool_input_schema": [{{"arg_name": "query", "arg_description": "可选，搜索查询词"}}, {{"arg_name": "author", "arg_description": "可选，论文作者"}}]}}，
                   {{"tool_name": "latex_parser", "tool_description": "解析 LaTeX 文档", "tool_input_schema": [{{"arg_name": "latex_path", "arg_description": "必填，LaTeX 文档路径"}}, {{"arg_name": "output_format", "arg_description": "可选，输出格式"}}]}}]
   如需调用工具arxiv_search查询机器学习领域的论文,作者为 Sam，则按照如下格式返回：
   TOOL_NAME [arxiv_search]
   TOOL_INPUT [{{"query": "机器学习", "author": "Sam"}}]
   如需调用工具latex_parser解析路径为 “~/data/latex_file.tex" 的 LaTeX 文档，且无需指定输出格式，则按照如下格式返回：
   TOOL_NAME [latex_parser]
   TOOL_INPUT [{{"latex_path": "~/data/latex_file.tex"}}]
不要给出除以上两种定义的格式外其他任何格式的回复。"""

SYSTEM_PROMPT = """你是一个专业的评审员，你的任务是根据用户的问题和可能提供的修改历史，对当前的回复提出专业的修改意见，以更好地满足用户的需求。
你的回答应该满足如下要求：
1. 如果你认为当前回复已经足够很好地解决用户的问题，则按照如下格式给出肯定的回复，注意把当前回复用英文中括号包围：
   FINISHED [当前回复]
2. 如果你认为当前回复有需要修改的地方，则按照如下格式给出专业的修改意见，注意把修改意见用英文中括号包围：
   MODIFICATION [修改意见]
不要给出除以上两种定义的格式外其他任何格式的回复。"""

class ReflectionAgent(BaseAgent):
    """
    [扩展] 自我反思 Agent 抽象基类。

    工作流程（循环直到 is_satisfactory() 返回 True 或达到 MAX_REFLECTION_ROUNDS）：
        1. Generate: 生成初始答案
        2. Reflect:  批判性分析答案的不足（充当"评审者"角色）
        3. Refine:   基于反思结果改进答案（充当"修改者"角色）
        重复 2-3 直到质量满足要求

    适用场景：论文润色、表达改进、逻辑一致性检查等高质量要求的写作任务。

    Class Attributes:
        MAX_REFLECTION_ROUNDS: 最大反思迭代轮数，默认 3。

    TODO: 开发者 B 实现时建议将 Generate/Reflect/Refine 分配给不同 system prompt 的 LLM 调用
    """


    MAX_REFLECTION_ROUNDS: int = 3

    def __init__(
        self,
        name: str,
        system_prompt: str = None,
        tools: Optional[List[BaseTool]] = None,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = None,
        max_history: int = 100,
    ):
        """
        初始化 ReflectionAgent。

        该 Agent 内部包含两个角色：
        - executor: 负责生成/改写答案（可调用工具）
        - reviewer(self.llms['llm']): 负责提出修改意见或给出 FINISHED

        Args:
            name: Agent 名称/标识
            system_prompt: 评审者提示词；默认使用内置 SYSTEM_PROMPT
            tools: 可用工具列表（会同时注入 executor）
            model_name/api_key/base_url/temperature: 评审者 LLM 的配置
            max_history: 内部历史最大条数（控制上下文长度）
        """
        if tools is None:
            tools = tool_list
        tools_info_list = []
        for tool in tools:
            tools_info_list.append({"tool_name": tool.name, "tool_description": tool.description, "tool_input_schema": tool.input_schema})
        executor_system_prompt = EXECUTOR_SYSTEM_PROMPT.format(tools=tools_info_list)
        if system_prompt is None:
            system_prompt = SYSTEM_PROMPT
            
        super().__init__(name, system_prompt, tools)
        self.executor = SimpleAgent(name = f"{name}_executor", system_prompt = executor_system_prompt, tools = tools)
        self.set_llm("llm", model_name or MODEL_NAME, api_key or API_KEY, base_url or BASE_URL, temperature or TEMPERATURE)
        self.history = []
        self.max_history = max_history

    

    def _build_history_messages(self, history: List[AgentMessage]) -> list:
        """构建对话历史消息列表"""
        history_messages = [f"SYSTEM\n{self.system_prompt}"]
        for hist in history:
            if hist.role in ("user"):
                history_messages.append(f"USER\n{hist.content}")
            elif hist.agent_name == self.executor.name:
                history_messages.append(f"ANSWER\n{hist.content}")
            elif hist.agent_name == self.name:
                history_messages.append(f"REFLECTION\n{hist.content}")
            else:
                raise RuntimeError(f"未知消息角色: {hist.role}")
        return history_messages

    def _build_executor_prompt(self) -> str:
        """
        构建“修改者/执行器”侧的输入 prompt。

        该 prompt 通常由三部分组成：
        - 用户原始问题
        - 上一版回答
        - 最新的修改意见（反思结果）

        执行器（SimpleAgent）据此生成改进后的回答。
        """
        history_messages = [self.history[0], self.history[-2], self.history[-1]]
        messages = []
        for hist in history_messages:
            if hist.role in ("user"):
                messages.append(f"USER\n{hist.content}")
            elif hist.agent_name == self.executor.name:
                messages.append(f"ANSWER\n{hist.content}")
            elif hist.agent_name == self.name:
                messages.append(f"REFLECTION\n{hist.content}")
            else:
                raise RuntimeError(f"未知消息角色: {hist.role}")
        prompt = "\n\n".join(messages)
        return prompt

    def run(self, message: Union[str, AgentMessage, dict]) -> AgentMessage:
        """
        执行“生成-反思-改写”的迭代流程。

        流程概览：
        1) 使用 executor 生成初版回答
        2) 作为“评审者”调用 llm 产出 FINISHED 或 MODIFICATION
        3) 若为 MODIFICATION，则把修改意见交给 executor 生成新版回答
        4) 循环直到 FINISHED 或达到最大轮次
        """
        self.reset()
        normalized_msg = self._normalize_message(message)
        self.history.append(normalized_msg)

        if MODE == "debug":
            print(f"INPUT:\n{normalized_msg.content}\n")

        executor_message = self.executor.run(normalized_msg)    
        self.history.append(executor_message)

        if MODE == "debug":
            print(f"初次回答:\n{executor_message.content}\n")

        for i in range(self.MAX_REFLECTION_ROUNDS):
            history_cur = [self.history[0], self.history[-1]]
            history_messages = self._build_history_messages(history_cur)
            prompt = "\n\n".join(history_messages)
            
            if MODE == "debug":
                print("="*100)
                print(f"REFLECTION_PROMPT:\n{prompt}\n")

            llm_content = self.llms["llm"].response(prompt)

            if MODE == "debug":
                    print(f"REFLECTION_LLM_CONTENT:\n{llm_content}\n")

            result_index1 = llm_content.find("FINISHED")
            result_index2 = llm_content.find("MODIFICATION")
            if result_index1 != -1:
                # 直接回答，提取结果
                result_content = llm_content[result_index1 + len("FINISHED"):].strip().strip('[]')
                result = AgentMessage(
                    role="assistant",
                    content=result_content,
                    agent_name=self.name,
                )
                if MODE == "debug":
                    print(f"RESULT:\n{result.content}\n")

                return result
            elif result_index2 != -1:
                # 提取反思结果
                reflection_content = llm_content[result_index2 + len("MODIFICATION"):].strip().strip('[]')
                reflection_message = AgentMessage(
                    role="assistant",
                    content=reflection_content,
                    agent_name=self.name,
                )
                self.history.append(reflection_message)
                executor_prompt = self._build_executor_prompt()
                if MODE == "debug":
                    print(f"EXECUTOR_PROMPT:\n{executor_prompt}\n")
                executor_message = self.executor.run(executor_prompt)
                if MODE == "debug":
                    print(f"EXECUTOR_LLM_CONTENT:\n{executor_message.content}\n")
                self.history.append(executor_message)
            else:
                raise RuntimeError("LLM 输出中未包含预期的 FINISHED 或 MODIFICATION 标签")

        result = AgentMessage(
            role="assistant",
            content=self.history[-1].content,
            agent_name=self.name,
        )
        if MODE == "debug":
            print(f"RESULT:\n{result.content}\n")

        return result

    def reset(self) -> None:
        """清空对话历史，重置 Agent 为初始状态。"""
        self.history.clear()

if __name__ == "__main__":
    agent = ReflectionAgent("TestAgent")
    result = agent.run("查找机器学习领域的论文，要求反映最新的研究趋势")
    print("FINAL RESULT:\n", result.content)
