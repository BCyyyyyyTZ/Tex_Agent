from __future__ import annotations

"""
工作流执行引擎（Workflow Engine）。

该模块提供一个轻量的 DAG 工作流实现：
- Workflow: 管理节点与边，并按拓扑序执行节点
- WorkflowContext: 运行时上下文，用于收集每个节点的输出、状态、错误与 trace
- Edge: 边定义，可携带条件函数实现分支/路由

消息模型采用 workflow_engine.messages 中的结构化消息类型，节点接口由
workflow_engine.nodes.BaseNode 约定。
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Any

from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage, MergedMessage, WorkflowMessage
from workflow_engine.nodes import BaseNode

@dataclass
class WorkflowContext:
    """
    工作流运行时上下文。

    - outputs: 每个节点的输出消息（按 node_id 索引）
    - status: 节点执行状态（executed/failed 等）
    - errors: 节点失败时的错误字符串
    - trace: 节点实际执行顺序（拓扑序下的执行 trace）
    - metadata: 运行期额外信息（由节点或外部调用方填充）
    """
    outputs: dict[str, WorkflowMessage] = field(default_factory=dict)
    status: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Edge:
    """
    工作流有向边。

    condition 为可选谓词，用于控制该边是否传播消息到下游节点：
    - 入参 1: 当前节点输出消息
    - 入参 2: 工作流上下文
    - 返回 True 表示该边被激活，消息会送达 to_node
    """
    from_node: str
    to_node: str
    condition: Optional[Callable[[WorkflowMessage, WorkflowContext], bool]] = None


def _merge_message(messages: list[WorkflowMessage | None]) -> MergedMessage:
    """
    将同一节点的多路输入消息合并为一个 MergedMessage。

    合并策略：
    - TextMessage: 文本按段落拼接
    - ToolCallMessage: 收集为 tool_calls 列表
    - ToolResultMessage: 聚合 tool_names 与 results
    - MergedMessage: 递归展开并继续聚合
    - metadata: 字典浅合并（后者覆盖前者同名键）
    """
    if not messages:
        return None

    merged_texts: list[str] = []
    merged_tool_calls: list[dict[str, Any]] = []
    merged_tool_results: dict[str, Any] = {"tool_names": set(), "results": []}
    merged_metadata: dict[str, Any] = {}

    for m in messages:
        meta = getattr(m, "metadata", None)
        if isinstance(meta, dict):
            merged_metadata.update(meta)

        if isinstance(m, TextMessage):
            merged_texts.append(m.text)
        elif isinstance(m, ToolCallMessage):
            merged_tool_calls.append({
                "tool_name": m.tool_name,
                "arguments": m.arguments,
            })
        elif isinstance(m, ToolResultMessage):
            merged_tool_results["tool_names"].update(m.tool_names)
            merged_tool_results["results"].extend(m.results)
        elif isinstance(m, MergedMessage):
            if m.text:
                merged_texts.append(m.text)
            merged_tool_calls.extend(m.tool_calls)
            merged_tool_results["tool_names"].update(m.tool_names)
            merged_tool_results["results"].extend(m.results)
        else:
            pass

    text = "\n\n".join(t for t in merged_texts if t)
    return MergedMessage(
        text=text,
        tool_calls=merged_tool_calls,
        tool_results=merged_tool_results,
        metadata=merged_metadata,
    )




class Workflow:
    """
    DAG 工作流。

    用法概览：
    1) add_node 注册节点（node_id 唯一）
    2) add_edge 注册依赖与路由（可选 condition 做分支）
    3) run 触发执行，按拓扑序运行所有节点

    设计约束：
    - 图必须是 DAG，否则 _topological_order 会抛错
    - 默认通过“入度为 0 的节点”推断 start_nodes
    - 节点 run 失败不会中断整个工作流；错误会写入 context
    """
    def __init__(self):
        """
        初始化空工作流。

        nodes: node_id -> BaseNode
        edges: 全量边列表
        _outgoing/_incoming: 邻接表缓存，加速运行期消息传播与起点推断
        """
        self.nodes: dict[str, BaseNode] = {}
        self.edges: list[Edge] = []
        self._outgoing: dict[str, list[Edge]] = {}
        self._incoming: dict[str, list[Edge]] = {}

    def add_node(self, node: BaseNode) -> None:
        """
        注册节点。

        Args:
            node: 需要加入工作流的节点对象（node.node_id 作为唯一标识）
        """
        if node.node_id in self.nodes:
            raise KeyError(f"duplicate node_id: {node.node_id}")
        self.nodes[node.node_id] = node
        self._outgoing.setdefault(node.node_id, [])
        self._incoming.setdefault(node.node_id, [])

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        *,
        condition: Optional[Callable[[WorkflowMessage, WorkflowContext], bool]] = None,
    ) -> None:
        """
        注册边（依赖/路由关系）。

        Args:
            from_node: 上游节点 id
            to_node: 下游节点 id
            condition: 可选谓词；返回 True 时才会把 from_node 的输出传给 to_node
        """
        if from_node not in self.nodes:
            raise KeyError(f"edge from_node not found: {from_node}")
        if to_node not in self.nodes:
            raise KeyError(f"edge to_node not found: {to_node}")
        e = Edge(from_node=from_node, to_node=to_node, condition=condition)
        self.edges.append(e)
        self._outgoing.setdefault(from_node, []).append(e)
        self._incoming.setdefault(to_node, []).append(e)

    def _topological_order(self) -> list[str]:
        """
        计算节点拓扑序。

        Returns:
            按拓扑顺序排列的 node_id 列表。

        Raises:
            ValueError: 图存在环或存在无法排序的结构（例如环形依赖）。
        """
        indegree: dict[str, int] = {n: 0 for n in self.nodes}
        for e in self.edges:
            indegree[e.to_node] += 1

        q = [n for n, d in indegree.items() if d == 0]
        order: list[str] = []
        outgoing = {k: list(v) for k, v in self._outgoing.items()}

        while q:
            n = q.pop(0)
            order.append(n)
            for e in outgoing.get(n, []):
                indegree[e.to_node] -= 1
                if indegree[e.to_node] == 0:
                    q.append(e.to_node)

        if len(order) != len(self.nodes):
            raise ValueError("workflow graph contains cycle or disconnected cycle")
        return order

    def _infer_start_nodes(self) -> list[str]:
        """
        推断工作流起始节点：所有入度为 0 的节点。

        Raises:
            ValueError: 不存在起点（通常意味着图包含环）。
        """
        starts = [n for n, incoming in self._incoming.items() if len(incoming) == 0]
        if not starts:
            raise ValueError("no start node found")
        return starts

    def run(
        self,
        initial_message: WorkflowMessage = None,
        *,
        start_nodes: Optional[list[str]] = None,
        context: Optional[WorkflowContext] = None,
        return_context: bool = False,
    ) -> Any:
        """
        执行工作流。

        Args:
            initial_message: 可选初始消息，会广播到 start_nodes 作为输入
            start_nodes: 显式指定起点节点列表；不传则自动推断
            context: 可选外部传入的上下文；不传则新建 WorkflowContext
            return_context: 是否同时返回上下文（用于调试/审计/可视化）

        Returns:
            - 若只有一个终止节点输出：返回该输出消息
            - 若存在多个终止节点输出：返回输出列表
            - 若 return_context=True：返回 (output, context)
        """
        if not self.nodes:
            raise ValueError("workflow has no nodes")

        start_nodes = list(start_nodes) if start_nodes is not None else self._infer_start_nodes()
        for n in start_nodes:
            if n not in self.nodes:
                raise KeyError(f"start node not found: {n}")

        order = self._topological_order()
        incoming_messages: dict[str, list[WorkflowMessage]] = {n: [] for n in self.nodes}
        
        if initial_message:
            for n in start_nodes:
                incoming_messages[n].append(initial_message)

        ctx = context or WorkflowContext()
        for node_id in order:
            node = self.nodes[node_id]
            inputs = incoming_messages.get(node_id, [])

            merged = _merge_message(inputs)
            try:
                out = node.run(merged, ctx)
                ctx.status[node_id] = "executed"
                ctx.outputs[node_id] = out
                ctx.trace.append(node_id)
            except Exception as e:
                print(f"Error in node {node_id}: {e}")
                ctx.status[node_id] = "failed"
                ctx.errors[node_id] = str(e)
                ctx.trace.append(node_id)
                out = None

            if out is not None:
                for e in self._outgoing.get(node_id, []):
                    if e.condition is None or e.condition(out, ctx):
                        incoming_messages[e.to_node].append(out)

        terminal_nodes = [n for n, outs in self._outgoing.items() if len(outs) == 0]
        results = [ctx.outputs[n] for n in terminal_nodes if n in ctx.outputs]
        if not results:
            executed = [ctx.outputs[n] for n in ctx.trace if n in ctx.outputs]
            if not executed:
                raise RuntimeError("workflow produced no output")
            result = executed[-1]
            return (result, ctx) if return_context else result
        if len(results) == 1:
            result = results[0]
            return (result, ctx) if return_context else result
        return (results, ctx) if return_context else results

