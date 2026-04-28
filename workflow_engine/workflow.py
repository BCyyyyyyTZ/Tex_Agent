from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Any

from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage, MergedMessage, WorkflowMessage
from workflow_engine.nodes import BaseNode

@dataclass
class WorkflowContext:
    outputs: dict[str, WorkflowMessage] = field(default_factory=dict)
    status: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Edge:
    from_node: str
    to_node: str
    condition: Optional[Callable[[WorkflowMessage, WorkflowContext], bool]] = None


def _merge_message(messages: list[WorkflowMessage | None]) -> MergedMessage:
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
    def __init__(self):
        self.nodes: dict[str, BaseNode] = {}
        self.edges: list[Edge] = []
        self._outgoing: dict[str, list[Edge]] = {}
        self._incoming: dict[str, list[Edge]] = {}

    def add_node(self, node: BaseNode) -> None:
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
        if from_node not in self.nodes:
            raise KeyError(f"edge from_node not found: {from_node}")
        if to_node not in self.nodes:
            raise KeyError(f"edge to_node not found: {to_node}")
        e = Edge(from_node=from_node, to_node=to_node, condition=condition)
        self.edges.append(e)
        self._outgoing.setdefault(from_node, []).append(e)
        self._incoming.setdefault(to_node, []).append(e)

    def _topological_order(self) -> list[str]:
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

