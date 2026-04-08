"""
全局工作流状态定义。
WorkflowState 是 LangGraph 图中所有节点共享与传递的状态对象。
"""
from typing import TypedDict, List, Optional,Union,Any,Dict
from core.message import AgentMessage

class WorkflowState(TypedDict):
    """
    LangGraph 工作流全局状态。

    该 TypedDict 在 LangGraph StateGraph 中作为节点间传递的共享状态。
    每个节点接收完整的 state，返回需要更新的字段的部分字典。

    Fields:
        messages: Agent 消息历史列表（每条消息序列化为 dict）。
                  使用 operator.add 作为 Reducer，新消息自动追加而非替换。
        current_node: 当前正在执行的节点名称，由各节点自行更新。
        input: 用户的原始输入文本，在整个工作流中保持不变。
        output: 工作流的最终输出结果，由 execute 节点填充。
        error: 执行过程中的错误信息，None 表示正常执行。
        metadata: 扩展元数据字典，预留给多分支上下文、路由信息等未来功能。

    Notes:
        messages 字段的 operator.add Reducer：
        当节点返回 {"messages": [new_msg1, new_msg2]} 时，
        LangGraph 会将其追加到现有 messages 列表末尾，
        而非替换整个列表。这是实现消息历史积累的关键机制。

    TODO: 未来在此处增加 branch_id: str 字段，支持多分支上下文
    TODO: 未来在此处增加 context_tree_snapshot: dict 字段，存储分支状态快照

    RAG 集成说明：
        retrieved_context 由 workflow/nodes.py 的 retrieve_node 写入。
        当 build_graph(rag_pipeline=...) 未传入 RAG 管道时，
        该字段始终为 ""，不影响现有工作流逻辑。
    """
    messages: List[Union[Dict[str, Any], AgentMessage, str]]
    current_node: str
    input: str
    output: str
    error: Optional[str]
    metadata: dict
    retrieved_context: str  # RAG 检索结果，由 retrieve_node 写入；未启用 RAG 时为 ""
