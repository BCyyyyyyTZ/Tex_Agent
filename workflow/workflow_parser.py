"""
工作流解析器：将 JSON/YAML 配置文件或 TaskPlan 转换为
(List[NodeConfig], List[EdgeConfig])，供 graph_builder 构图。

Breaking Change v2:
  - EdgeConfig.condition 类型从 Optional[str]（裸 Python 表达式）改为
    Optional[ConditionExpr]（结构化条件对象），由 condition_evaluator 执行
  - EdgeConfig 新增 priority 字段，用于条件边优先级排序
  - NodeConfig 新增 parallel_branches / join_policy / source_branches 字段，
    支持 node_type="parallel_fork" 和 "parallel_join"
  - parse_edges 读取条件时不再接受字符串，只接受 dict（ConditionExpr 格式）
  - _translate_plan_to_graph_config 支持从 LLM 输出解析条件边与并行边
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from utils.logger import get_logger
from workflow.condition_evaluator import ConditionExpr

if TYPE_CHECKING:
    from router.planner import TaskPlan

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 数据类定义
# ---------------------------------------------------------------------------

@dataclass
class NodeConfig:
    """
    节点配置数据结构。

    node_type 合法值：
        "agent"         - LLM agent 节点（默认）
        "tool"          - 工具节点，需配合 tool_name
        "user"          - 人机反馈节点（HITL）
        "parallel_fork" - 并行分叉节点（无业务逻辑，将流转发到 parallel_branches）
        "parallel_join" - 并行汇聚节点（等待 source_branches 完成后执行 agent 整合）

    Attributes:
        node_id:          节点唯一标识
        node_type:        节点类型（见上）
        agent_name:       Agent 类型名（node_type="agent"/"parallel_join" 时有效）
        tool_name:        工具名（node_type="tool" 时必填）
        config:           节点额外配置字典
        parallel_branches:并行分支节点 ID 列表（node_type="parallel_fork" 时必填）
        join_policy:      汇聚策略（node_type="parallel_join" 时有效）
        source_branches:  被汇聚的分支节点 ID 列表（node_type="parallel_join" 时必填）
    """

    node_id: str
    node_type: str
    agent_name: str = ""
    tool_name: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    parallel_branches: List[str] = field(default_factory=list)
    join_policy: str = "all_success"
    source_branches: List[str] = field(default_factory=list)


@dataclass
class EdgeConfig:
    """
    边配置数据结构。

    Attributes:
        from_node: 起始节点 ID
        to_node:   目标节点 ID（条件边为"此条件为 True 时"的目标）
        condition: 条件表达式（None 表示无条件线性/并行边）
        priority:  条件边优先级（值越大越先评估；无条件边 priority 无意义）
    """

    from_node: str
    to_node: str
    condition: Optional[ConditionExpr] = None
    priority: int = 0


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------

class WorkflowParser(ABC):
    """
    工作流解析器抽象基类。
    """

    @abstractmethod
    def load_config(self, config_path: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def parse_nodes(self, config: Dict[str, Any]) -> List[NodeConfig]:
        raise NotImplementedError

    @abstractmethod
    def parse_edges(self, config: Dict[str, Any]) -> List[EdgeConfig]:
        raise NotImplementedError

    @abstractmethod
    def build_graph(
        self,
        nodes: List[NodeConfig],
        edges: List[EdgeConfig],
        context_manager: Optional[Any] = None,
        default_history_mode: Optional[str] = None,
        persona_memory: Optional[Any] = None,
        runtime_memory: Optional[Any] = None,
        human_input_provider: Optional[Any] = None,
    ) -> Any:
        raise NotImplementedError

    def from_task_plan(
        self,
        plan: "TaskPlan",
    ) -> Tuple[List[NodeConfig], List[EdgeConfig]]:
        raise NotImplementedError(
            "from_task_plan() 尚未实现，请在子类中完成。"
        )


# ---------------------------------------------------------------------------
# 独立翻译函数：TaskPlan → (List[NodeConfig], List[EdgeConfig])
# ---------------------------------------------------------------------------

def _translate_plan_to_graph_config(
    plan: "TaskPlan",
) -> Tuple[List[NodeConfig], List[EdgeConfig]]:
    """
    将 TaskPlan 翻译为 (List[NodeConfig], List[EdgeConfig])。

    翻译规则：
      assigned_agents[node_id] → NodeConfig
      优先读 assigned_agents["__edges__"] 构建 EdgeConfig（支持条件边）；
      若 __edges__ 不连通 → 从 depends_on 重建；
      仍为空 → 线性链兜底。

    Breaking Change v2:
      - __edges__ 中的 "condition" 字段若为 dict，解析为 ConditionExpr
      - 支持 node_type="parallel_fork" / "parallel_join"
    """
    from config.planner_config import NODE_DEFAULT_TEMPERATURE

    nodes: List[NodeConfig] = []
    for node_id in plan.subtasks:
        spec = plan.assigned_agents.get(node_id, {})
        node_type = str(spec.get("node_type", "agent")).strip().lower()

        if node_type == "tool":
            node = NodeConfig(
                node_id=node_id,
                node_type="tool",
                tool_name=str(spec.get("tool_name", "arxiv_search")),
                config={
                    "tool_input": spec.get("tool_input", "${input}"),
                    "depends_on": spec.get("depends_on", []),
                    "history_mode": spec.get("history_mode", "minimal"),
                },
            )
        elif node_type == "user":
            node = NodeConfig(
                node_id=node_id,
                node_type="user",
                config={
                    "prompt_template": spec.get("prompt_template", "请根据当前上下文提供反馈。"),
                    "input_schema": spec.get("input_schema", {"type": "text"}),
                    "validation": spec.get("validation", {"required": True}),
                    "default_value": spec.get("default_value", ""),
                    "write_to": spec.get("write_to", f"user_feedback.{node_id}"),
                    "depends_on": spec.get("depends_on", []),
                    "history_mode": spec.get("history_mode", "minimal"),
                },
            )
        elif node_type == "parallel_fork":
            branches = spec.get("parallel_branches", [])
            node = NodeConfig(
                node_id=node_id,
                node_type="parallel_fork",
                parallel_branches=branches,
                config={},
            )
        elif node_type == "parallel_join":
            src_branches = spec.get("source_branches", [])
            jp = spec.get("join_policy", "all_success")
            node = NodeConfig(
                node_id=node_id,
                node_type="parallel_join",
                agent_name=spec.get("agent_type", "SimpleAgent"),
                join_policy=jp,
                source_branches=src_branches,
                config={
                    "system_prompt": spec.get(
                        "system_prompt", f"你是{spec.get('role', node_id)}整合专家。"
                    ),
                    "subtask": spec.get("subtask", "整合所有并行分支的输出，给出综合结论。"),
                    "depends_on": src_branches,
                    "history_mode": spec.get("history_mode", "minimal"),
                },
            )
        else:
            node = NodeConfig(
                node_id=node_id,
                node_type="agent",
                agent_name=spec.get("agent_type", "SimpleAgent"),
                config={
                    "system_prompt": spec.get(
                        "system_prompt", f"你是{spec.get('role', node_id)}专家。"
                    ),
                    "subtask": spec.get("subtask", ""),
                    "output_schema": spec.get("output_schema", {}),
                    "role": spec.get("role", node_id),
                    "depends_on": spec.get("depends_on", []),
                    "temperature": NODE_DEFAULT_TEMPERATURE,
                    "history_mode": spec.get("history_mode", "minimal"),
                    "context_profile": spec.get("context_profile", "dialogue"),
                },
            )
        nodes.append(node)

    all_node_ids: List[str] = plan.subtasks

    def _is_fully_connected(edge_list: List[Dict[str, Any]], node_ids: List[str]) -> bool:
        """BFS 验证所有节点从入口出发均可到达。"""
        if not node_ids:
            return True
        adj: Dict[str, List[str]] = {}
        to_nodes: set = set()
        for e in edge_list:
            adj.setdefault(e["from"], []).append(e["to"])
            to_nodes.add(e["to"])
        entry = next((n for n in node_ids if n not in to_nodes), node_ids[0])
        visited: set = set()
        queue = deque([entry])
        while queue:
            cur = queue.popleft()
            visited.add(cur)
            for nxt in adj.get(cur, []):
                if nxt not in visited:
                    queue.append(nxt)
        return visited == set(node_ids)

    raw_edges: List[Dict[str, Any]] = list(plan.assigned_agents.get("__edges__", []))

    # 尝试1：__edges__（LLM 生成）
    if raw_edges and not _is_fully_connected(raw_edges, all_node_ids):
        logger.warning(
            f"[WorkflowParser] __edges__ 中 {len(raw_edges)} 条边无法覆盖全部 "
            f"{len(all_node_ids)} 个节点，降级为 depends_on 重建"
        )
        raw_edges = []

    # 尝试2：从 depends_on 重建
    if not raw_edges:
        seen: set = set()
        for nid in all_node_ids:
            for dep in plan.assigned_agents.get(nid, {}).get("depends_on", []):
                key = (dep, nid)
                if key not in seen:
                    raw_edges.append({"from": dep, "to": nid, "condition": None})
                    seen.add(key)
        if raw_edges and not _is_fully_connected(raw_edges, all_node_ids):
            logger.warning(
                "[WorkflowParser] depends_on 重建的边仍不连通，降级为线性链"
            )
            raw_edges = []

    # 尝试3（最终兜底）：线性链
    if not raw_edges:
        for i in range(len(all_node_ids) - 1):
            raw_edges.append({
                "from": all_node_ids[i],
                "to": all_node_ids[i + 1],
                "condition": None,
            })

    edges: List[EdgeConfig] = []
    for e in raw_edges:
        raw_cond = e.get("condition")
        cond: Optional[ConditionExpr] = None
        if isinstance(raw_cond, dict):
            try:
                cond = ConditionExpr.from_dict(raw_cond)
            except (ValueError, KeyError) as exc:
                logger.warning(
                    f"[WorkflowParser] 边 {e.get('from')}→{e.get('to')} "
                    f"条件解析失败（{exc}），降级为无条件边"
                )
        edges.append(
            EdgeConfig(
                from_node=str(e.get("from", "")),
                to_node=str(e.get("to", "")),
                condition=cond,
                priority=int(e.get("priority", 0)),
            )
        )

    return nodes, edges


# ---------------------------------------------------------------------------
# YAMLWorkflowParser 具体实现
# ---------------------------------------------------------------------------

class YAMLWorkflowParser(WorkflowParser):
    """
    WorkflowParser 具体实现，支持两条图构建路径：

    路径 A（文件路径，静态 workflow JSON）：
        load_config(path) → parse_nodes() → parse_edges() → build_graph()

    路径 B（内存路径，动态规划主链路）：
        from_task_plan(plan) → build_graph()

    两条路径汇聚到 build_graph(nodes, edges)。
    """

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        从 JSON 或 YAML 文件加载工作流配置。

        .json → json.load
        .yaml / .yml → yaml.safe_load（需安装 PyYAML）
        """
        import os
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"工作流配置文件不存在: {config_path}")

        ext = os.path.splitext(config_path)[1].lower()
        with open(config_path, "r", encoding="utf-8") as f:
            if ext in (".yaml", ".yml"):
                try:
                    import yaml
                    return yaml.safe_load(f)
                except ImportError:
                    raise ImportError("解析 YAML 文件需要安装 PyYAML：pip install pyyaml")
            else:
                return json.load(f)

    def parse_nodes(self, config: Dict[str, Any]) -> List[NodeConfig]:
        """
        从配置字典解析节点列表。

        期望格式（新增 parallel_fork / parallel_join 支持）：
            {
              "nodes": [
                {
                  "node_id":    "parallel_fork",
                  "node_type":  "parallel_fork",
                  "parallel_branches": ["branch_a", "branch_b"]
                },
                {
                  "node_id":    "join_node",
                  "node_type":  "parallel_join",
                  "agent_name": "SimpleAgent",
                  "join_policy": "all_success",
                  "source_branches": ["branch_a", "branch_b"],
                  "config": {"system_prompt": "...", "subtask": "..."}
                }
              ]
            }
        """
        raw_nodes = config.get("nodes", [])
        parsed: List[NodeConfig] = []

        for raw in raw_nodes:
            node_id = str(raw.get("node_id", "unknown"))    
            node_type = str(raw.get("node_type", "agent")).strip().lower()
            agent_name = str(raw.get("agent_name", "SimpleAgent"))
            tool_name = str(raw.get("tool_name", ""))
            node_cfg = raw.get("config", {})
            if not isinstance(node_cfg, dict):
                logger.warning(
                    f"[WorkflowParser] 节点 '{node_id}' 的 config 不是对象，已回退为空字典"
                )
                node_cfg = {}

            # 校验
            if node_type == "tool" and not tool_name:
                raise ValueError(
                    f"[WorkflowParser] 工具节点 '{node_id}' 缺少 tool_name 配置"
                )
            if node_type == "user":
                pt = node_cfg.get("prompt_template")
                if not isinstance(pt, str) or not pt.strip():
                    raise ValueError(
                        f"[WorkflowParser] 用户节点 '{node_id}' 缺少 config.prompt_template"
                    )
                if not isinstance(node_cfg.get("input_schema", {}), dict):
                    raise ValueError(
                        f"[WorkflowParser] 用户节点 '{node_id}' 的 input_schema 必须是对象"
                    )
            if node_type == "parallel_fork":
                branches = raw.get("parallel_branches", [])
                if not isinstance(branches, list) or not branches:
                    raise ValueError(
                        f"[WorkflowParser] parallel_fork 节点 '{node_id}' "
                        f"缺少 parallel_branches 列表"
                    )
            if node_type == "parallel_join":
                src = raw.get("source_branches", [])
                if not isinstance(src, list) or not src:
                    raise ValueError(
                        f"[WorkflowParser] parallel_join 节点 '{node_id}' "
                        f"缺少 source_branches 列表"
                    )

            parsed.append(
                NodeConfig(
                    node_id=node_id,
                    node_type=node_type,
                    agent_name=agent_name,
                    tool_name=tool_name,
                    config=node_cfg,
                    parallel_branches=raw.get("parallel_branches", []),
                    join_policy=str(raw.get("join_policy", "all_success")),
                    source_branches=raw.get("source_branches", []),
                )
            )
        return parsed

    def parse_edges(self, config: Dict[str, Any]) -> List[EdgeConfig]:
        """
        从配置字典解析边列表。

        期望格式（Breaking Change v2：condition 为 dict 或 null）：
            {
              "edges": [
                {
                  "from_node": "risk_assessor",
                  "to_node":   "high_risk_handler",
                  "condition": {
                    "field": "metadata.risk_assessor.confidence",
                    "op":    "lt",
                    "value": 0.6
                  },
                  "priority": 1
                },
                {
                  "from_node": "risk_assessor",
                  "to_node":   "normal_handler"
                }
              ]
            }
        """
        raw_edges = config.get("edges", [])
        edges: List[EdgeConfig] = []

        for raw in raw_edges:
            from_node = str(raw.get("from_node", raw.get("from", "")))
            to_node = str(raw.get("to_node", raw.get("to", "")))
            raw_cond = raw.get("condition")
            priority = int(raw.get("priority", 0))

            cond: Optional[ConditionExpr] = None
            if isinstance(raw_cond, dict):
                try:
                    cond = ConditionExpr.from_dict(raw_cond)
                except (ValueError, KeyError) as exc:
                    logger.warning(
                        f"[WorkflowParser] 边 {from_node}→{to_node} "
                        f"条件解析失败（{exc}），降级为无条件边"
                    )
            elif raw_cond is not None and raw_cond != "":
                # 旧格式：裸字符串条件（Breaking Change：不再支持，记录错误）
                logger.error(
                    f"[WorkflowParser] 边 {from_node}→{to_node} 的 condition "
                    f"是字符串 {raw_cond!r}，v2 不再支持裸字符串条件。"
                    f"请改为 dict 格式：{{\"field\": \"...\", \"op\": \"...\", \"value\": ...}}"
                )

            edges.append(
                EdgeConfig(
                    from_node=from_node,
                    to_node=to_node,
                    condition=cond,
                    priority=priority,
                )
            )
        return edges

    def build_graph(
        self,
        nodes: List[NodeConfig],
        edges: List[EdgeConfig],
        context_manager: Optional[Any] = None,
        default_history_mode: Optional[str] = None,
        default_context_profile: Optional[str] = None,
        persona_memory: Optional[Any] = None,
        runtime_memory: Optional[Any] = None,
        human_input_provider: Optional[Any] = None,
        default_workflow_name: str = "plan_dynamic",
    ) -> Any:
        """调用 build_dynamic_graph() 编译 LangGraph 图。"""
        from workflow.graph_builder import build_dynamic_graph
        return build_dynamic_graph(
            nodes=nodes,
            edges=edges,
            context_manager=context_manager,
            default_history_mode=default_history_mode,
            default_context_profile=default_context_profile or "dialogue",
            persona_memory=persona_memory,
            runtime_memory=runtime_memory,
            human_input_provider=human_input_provider,
            default_workflow_name=default_workflow_name,
        )

    def from_task_plan(
        self,
        plan: "TaskPlan",
    ) -> Tuple[List[NodeConfig], List[EdgeConfig]]:
        """内存路径：直接从 TaskPlan 生成 (nodes, edges)。"""
        return _translate_plan_to_graph_config(plan)


def apply_depends_on_from_edges(config: Dict[str, Any]) -> None:
    """
    根据 edges 为各节点 config.depends_on 写入直接上游节点 ID 列表。

    Web 工作流编辑器只维护 edges；agent/tool 节点通过 depends_on 从 metadata
    读取上游输出。构图或保存草稿前调用，兼容 depends_on 为空但已有连线的旧草稿。
    """
    edges = config.get("edges") or []
    upstream: Dict[str, List[str]] = defaultdict(list)
    for e in edges:
        if not isinstance(e, dict):
            continue
        frm = e.get("from_node") if e.get("from_node") is not None else e.get("from")
        to = e.get("to_node") if e.get("to_node") is not None else e.get("to")
        if frm is None or to is None:
            continue
        upstream[str(to)].append(str(frm))

    nodes = config.get("nodes") or []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("node_id")
        if not nid:
            continue
        raw_cfg = node.get("config")
        if raw_cfg is None:
            cfg: Dict[str, Any] = {}
            node["config"] = cfg
        elif isinstance(raw_cfg, dict):
            cfg = raw_cfg
        else:
            continue
        deps_in = upstream.get(str(nid), [])
        seen: set = set()
        ordered: List[str] = []
        for d in deps_in:
            if d not in seen:
                seen.add(d)
                ordered.append(d)
        cfg["depends_on"] = ordered
