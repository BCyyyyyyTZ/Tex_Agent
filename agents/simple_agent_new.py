"""
SimpleAgent：最基础的可运行 Agent 实现。
接收输入消息 → 调用 LLM → 返回响应，支持工具列表注入与有界多轮对话历史维护。
"""
from typing import List, Optional, Union
import asyncio
from datetime import datetime
from pathlib import Path

#from langchain_openai import ChatOpenAI
#from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from agents.base_agent import BaseAgent
from core.message import AgentMessage
from core.exceptions import AgentError
from tools.base_tool import BaseTool
from config.settings import settings
from utils.logger import get_logger
from tools.tool_list import tool_list

logger = get_logger(__name__)
_LLM_TRACE_PATH = Path(__file__).resolve().parent.parent / "logs" / "llm_interactions_trace.txt"

#MODEL_NAME = "llama-3.3-70b-versatile"
MODEL_NAME = "gemini-3.1-flash-lite-preview"
API_KEY = ""
BASE_URL = "https://api.groq.com/openai/v1"
TEMPERATURE = 0.2

MODE = "release"

SYSTEM_PROMPT = """你是一个专业的助手，你的任务是根据用户的问题，使用工具列表中的工具来回答用户的问题。
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
   其中，工具名称必须字符串意义上匹配对应工具列表中工具的 tool_name 属性，工具输入参数必须符合工具列表中对应工具的 tool_input_schema 属性要求，且一定不要包含tool_input_schema中未定义的参数。
   下面给出几个例子，例子中的工具是虚构的，实际可用工具及使用方法以上面的工具列表为准。
   例如工具列表如下：[{{"tool_name": "arxiv_search", "tool_description": "搜索 arXiv 论文", "tool_input_schema": [{{"arg_name": "query", "arg_description": "可选，搜索查询词"}}, {{"arg_name": "author", "arg_description": "可选，论文作者"}}]}}，
                   {{"tool_name": "latex_parser", "tool_description": "解析 LaTeX 文档", "tool_input_schema": [{{"arg_name": "latex_path", "arg_description": "必填，LaTeX 文档路径"}}, {{"arg_name": "output_format", "arg_description": "可选，输出格式"}}]}}]
   如需调用工具arxiv_search查询机器学习领域的论文,作者为 Sam，则按照如下格式返回：
   TOOL_NAME [arxiv_search]
   TOOL_INPUT [{{"query": "机器学习", "author": "Sam"}}]
   如需调用工具latex_parser解析路径为 “~/data/latex_file.tex" 的 LaTeX 文档，且无需指定输出格式，则按照如下格式返回：
   TOOL_NAME [latex_parser]
   TOOL_INPUT [{{"latex_path": "~/data/latex_file.tex"}}]
不要给出除以上两种定义的格式外其他任何格式的回复。"""


class SimpleAgent_new(BaseAgent):
    """
    基础 Agent 实现，封装 LangChain ChatOpenAI 调用。

    特性：
    - 维护有界多轮对话历史，每次 run() 都将历史消息拼入 LLM 请求。
    - 支持工具列表注入（MVP 中工具结果需手动传入 prompt，后续可升级为 ToolCalling）。
    - 懒加载 LLM 实例，避免导入时因 API Key 未配置而报错。

    Args:
        name: Agent 唯一标识名（如 "DesignAgent"）。
        system_prompt: LLM 的 system 角色提示词。
        tools: 可用工具列表（BaseTool 子类实例），默认为空。
        temperature: LLM 温度，覆盖全局配置；None 则使用全局配置值。
        model: LLM 模型名，覆盖全局配置；None 则使用全局配置值。
        max_history: 对话历史最大保留条数（含用户和 AI 消息）。
                     None 表示不限制（慎用，长对话会超出 Token 限制）。
                     默认 100 条，约等于 50 轮对话。
    """

    def __init__(
        self,
        name: str,
        system_prompt: str = None,
        tools: Optional[List[BaseTool]] = None,
        model_name: str = MODEL_NAME,
        api_key: str = API_KEY,
        base_url: str = BASE_URL,
        temperature: float = TEMPERATURE,
        max_history: int = 100,
    ):
        if tools is None:
            tools = tool_list
        if system_prompt is None:
            tools_info_list = []
            for tool in tools:
                tools_info_list.append({"tool_name": tool.name, "tool_description": tool.description, "tool_input_schema": tool.input_schema})
            system_prompt = SYSTEM_PROMPT.format(tools=tools_info_list)
        super().__init__(name, system_prompt, tools)
        self.set_gemini("llm", model_name, api_key, temperature)
        self.history = []
        self.max_history = max_history

    def _build_history_messages(self) -> List[str]:
        """构建对话历史消息列表"""
        history_messages = [f"SYSTEM\n{self.system_prompt}"]
        for hist in self.history:
            if hist.role in ("user"):
                history_messages.append(f"USER\n{hist.content}")
            elif hist.role in ("assistant"):
                history_messages.append(f"ASSISTANT\n{hist.content}")
            elif hist.role in ("tool"):
                history_messages.append(f"TOOL:{hist.tool_name}\n{hist.content}")
            else:
                raise RuntimeError(f"未知消息角色: {hist.role}")
        return history_messages

    def _trim_history(self) -> None:
        """若历史超出 max_history 上限，丢弃最旧的消息（保持偶数对齐）。"""
        if self.max_history is None:
            return
        if len(self._history) > self.max_history:
            # 从头部裁剪，同时保持 user/assistant 消息对的完整性（步长 2）
            excess = len(self._history) - self.max_history
            # 向上取整到偶数，确保不破坏对话轮次边界
            excess = excess + (excess % 2)
            self._history = self._history[excess:]

    def _append_llm_trace(self, lc_messages: list, response_text: str) -> None:
        """
        统一记录所有模式下的 LLM 交互（默认/自定义/plan）。
        """
        try:
            _LLM_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().isoformat(timespec="seconds")

            serialized_messages = []
            for idx, msg in enumerate(lc_messages, start=1):
                role = getattr(msg, "type", msg.__class__.__name__)
                content = getattr(msg, "content", str(msg))
                serialized_messages.append(f"[{idx}] role={role}\n{content}\n")

            block = (
                "\n" + "=" * 88 + "\n"
                f"[{ts}] agent={self._name} model={self.model} temperature={self.temperature}\n"
                "\n[llm_messages]\n"
                + "\n".join(serialized_messages)
                + "\n[llm_response]\n"
                + str(response_text)
                + "\n"
                + "=" * 88 + "\n"
            )

            with _LLM_TRACE_PATH.open("a", encoding="utf-8") as f:
                f.write(block)
        except Exception as e:
            logger.error(f"[{self._name}] 写入 LLM 交互日志失败: {e}")

    def run(self, message: Union[str, AgentMessage, dict]) -> AgentMessage:
        """
        同步执行推理。

        Args:
            message: 用户/上游节点发送的消息，可以是：
                    - 字符串：自动转换为 AgentMessage
                    - AgentMessage 对象：直接使用
                    - 字典：根据字段转换为 AgentMessage

        Returns:
            LLM 生成的响应 AgentMessage（role="assistant"）。

        Raises:
            AgentError: LLM 调用失败或返回异常时抛出。
        """
        self.reset()
        # 1. 标准化输入消息
        normalized_msg = self._normalize_message(message)
        self.history.append(normalized_msg)
        attachment = normalized_msg.metadata.get("attachment", None)
        tool_args = normalized_msg.metadata.get("tool_args", None)
        if tool_args is not None:
            self.set_tool_args(tool_args)
        
        # 2. 日志记录（安全截取）
        content_preview = normalized_msg.content[:80] + "..." if len(normalized_msg.content) > 80 else normalized_msg.content
        logger.debug(f"[{self.name}] 接收消息: {content_preview}")
        
        try:
            # 3. 调用 LLM
            while True:
                history_messages = self._build_history_messages()
                # 构建完整的提示文本
                prompt = "\n\n".join(history_messages)

                if MODE == "debug":
                    print("="*100)
                    print(f"PROMPT:\n{prompt}")
                # 3. 调用 LLM  
                llm_content = self.llms["llm"].response(prompt = prompt, file_paths = attachment)
                if MODE == "debug":
                    print(f"LLM_CONTENT:\n{llm_content}")
                # 4. 解析 LLM 响应
                # 检查是否为直接回答
                result_index = llm_content.find("RESULT")
                if result_index != -1:
                    # 直接回答，提取结果
                    result_content = llm_content[result_index + len("RESULT"):].strip().strip('[]')
                    result = AgentMessage(
                        role="assistant",
                        content=result_content,
                        agent_name=self.name,
                    )
                     # 5. 更新对话历史（用于下一轮 run() 时构建上下文）并按上限裁剪
                    self.history.append(result)
                    #self._trim_history()
                    logger.debug(f"[{self.name}] 响应生成完毕，长度: {len(result.content)} 字符")

                    return result
                else:
                    # 检查是否为工具调用
                    lines = llm_content.strip().split('\n')
                    tool_name = None
                    tool_input = None
                    
                    for line in lines:
                        line = line.strip()
                        # 使用字符串匹配，不限制位置
                        tool_name_index = line.find("TOOL_NAME")
                        tool_input_index = line.find("TOOL_INPUT")
                        
                        if tool_name_index != -1:
                            tool_name = line[tool_name_index + len("TOOL_NAME"):].strip().strip('[]')
                        elif tool_input_index != -1:
                            tool_input_str = line[tool_input_index + len("TOOL_INPUT"):].strip().strip('[]')
                            # 解析工具输入参数
                            try:
                                import json
                                tool_input = json.loads(tool_input_str)
                                tool_input.update(self.tool_args.get(tool_name, {}))
                            except Exception as e:
                                logger.error(f"[{self.name}] 解析工具输入失败: {e}")
                                print(f"工具输入参数: {tool_input_str}")
                                raise RuntimeError(f"解析工具输入失败: {e}")
                    
                    if tool_name and tool_input:
                        # 工具调用逻辑
                        logger.debug(f"[{self.name}] 解析到工具调用: {tool_name}")
                        
                        # 查找工具
                        tool = None
                        for t in self.tools:
                            if t.name == tool_name:
                                tool = t
                                break
                        
                        if tool:
                            # 执行工具
                            logger.debug(f"[{self.name}] 执行工具: {tool_name}")
                            try:
                                tool_result = tool.run(**tool_input)
                                
                                # 构建工具执行结果消息
                                assistant_msg = AgentMessage(
                                    role="assistant",
                                    content=llm_content,
                                )

                                tool_result_msg = AgentMessage(
                                    role="tool",
                                    content=f"{tool_result.output}",
                                    tool_name=tool_name,
                                )
                                
                                # 将工具执行结果加入对话历史
                                self.history.append(assistant_msg)
                                self.history.append(tool_result_msg)

                            except Exception as e:
                                raise RuntimeError(f"工具 {tool_name} 执行失败: {str(e)}")
                        else:
                            # 工具未找到，构建错误响应
                            raise RuntimeError(f"工具 {tool_name} 未找到")
                            
                    else:
                        # 格式不符合预期，作为直接回答处理
                        raise RuntimeError(f"工具调用格式不符合预期: {llm_content}")

           

        except AgentError:
            # 已经是业务异常，直接向上传播，避免双重包装
            raise
        except Exception as e:
            logger.error(f"[{self.name}] LLM 调用失败: {e}")
            raise e

    async def ainvoke(self, message: Union[str, AgentMessage, dict]) -> AgentMessage:
        """异步执行推理（在线程池中运行同步 LLM 调用，不阻塞事件循环）。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, message)

    def reset(self) -> None:
        """清空对话历史，重置 Agent 为初始状态。"""
        self.history.clear()
        logger.debug(f"[{self.name}] 对话历史已清空")

    def get_history(self) -> List[AgentMessage]:
        """获取完整的对话历史副本。"""
        return list(self._history)

if __name__ == "__main__":
    agent = SimpleAgent_new("TestAgent")
    pdf_path = r""
    msg = AgentMessage(
        role="user",
        content="搜索与附件中论文相同主题的其他论文,并返回查找到的论文的标题和摘要",
        metadata={"attachment": pdf_path},
    )
    result = agent.run(msg)