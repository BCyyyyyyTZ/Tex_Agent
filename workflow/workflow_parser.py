"""
[扩展] 用户自定义工作流解析器接口定义。
预留从 YAML/JSON 配置文件动态解析并组装 LangGraph 图节点的接口。

TODO: 开发者 A 负责实现此类（第三阶段任务）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    # 仅用于类型提示，运行时不导入，避免与 router 层产生循环依赖
    from router.planner import TaskPlan


@dataclass
class NodeConfig:
    """
    自定义节点配置数据结构。

    Attributes:
        node_id: 节点唯一标识符（在配置文件中引用时使用）。
        node_type: 节点类型（"agent" / "tool" / "condition" / "parallel"）。
        agent_name: 使用的 Agent 配置名（node_type="agent" 时有效）。
        tool_name: 使用的工具名（node_type="tool" 时有效）。
        config: 节点额外参数（如 system_prompt 覆盖、temperature 等）。
    """

    node_id: str
    node_type: str
    agent_name: str = ""
    tool_name: str = ""
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeConfig:
    """
    自定义边配置数据结构。

    Attributes:
        from_node: 起始节点 ID。
        to_node: 目标节点 ID（条件边时为默认目标）。
        condition: 条件表达式字符串（None 表示无条件线性边）。
                   条件边示例："state['error'] is None"
    """

    from_node: str
    to_node: str
    condition: Optional[str] = None


class WorkflowParser(ABC):
    """
    [扩展] 用户自定义工作流解析器抽象基类。

    功能规划：
        1. 解析 YAML/JSON 格式的工作流配置文件
        2. 将配置转换为 NodeConfig 和 EdgeConfig 对象列表
        3. 动态生成对应的 LangGraph 节点函数和边关系
        4. 支持配置校验，提供友好的错误提示

    用户自定义工作流配置示例（YAML 格式）：
        nodes:
          - id: research
            type: agent
            agent: ReActAgent
            config:
              system_prompt: "你是文献研究专家..."
          - id: write
            type: agent
            agent: SimpleAgent
        edges:
          - from: research
            to: write
          - from: write
            to: END
        entry: research

    TODO: 开发者 A 实现建议：
          - 使用 PyYAML / json 库解析配置文件
          - 实现配置 Schema 验证（推荐使用 Pydantic）
          - 支持节点类型注册表，方便扩展新节点类型
    """

    @abstractmethod
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        从文件加载工作流配置。

        Args:
            config_path: YAML 或 JSON 格式的工作流配置文件路径。

        Returns:
            解析后的配置字典（原始格式，未经 validate）。

        Raises:
            FileNotFoundError: 配置文件不存在时。
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def parse_nodes(self, config: Dict[str, Any]) -> List[NodeConfig]:
        """
        从配置字典中解析节点列表。

        Args:
            config: load_config() 返回的配置字典。

        Returns:
            NodeConfig 对象列表。

        Raises:
            ConfigError: 节点配置格式非法时。
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def parse_edges(self, config: Dict[str, Any]) -> List[EdgeConfig]:
        """
        从配置字典中解析边列表。

        Args:
            config: load_config() 返回的配置字典。

        Returns:
            EdgeConfig 对象列表。

        Raises:
            ConfigError: 边配置格式非法时。
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def build_graph(
        self, nodes: List[NodeConfig], edges: List[EdgeConfig]
    ) -> Any:
        """
        根据节点和边配置动态构建并编译 LangGraph 图。

        Args:
            nodes: NodeConfig 对象列表（由 parse_nodes() 返回）。
            edges: EdgeConfig 对象列表（由 parse_edges() 返回）。

        Returns:
            编译完成的 LangGraph CompiledGraph 实例，可直接 .invoke()。

        Raises:
            WorkflowError: 图构建失败时（节点引用不存在、循环依赖等）。
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def from_task_plan(
        self,
        plan: "TaskPlan",
    ) -> Tuple[List[NodeConfig], List[EdgeConfig]]:
        """
        [扩展] 直接从 TaskPlan 生成图拓扑配置（动态规划入口）。

        与 load_config() → parse_nodes() → parse_edges() 的静态文件解析路径不同，
        此方法接受 MASPlanner 动态生成的 TaskPlan，直接输出可被 build_graph()
        消费的 NodeConfig / EdgeConfig 列表，是两条路径的汇聚点：

            静态路径：YAML/JSON 文件 → load_config() → parse_nodes/edges()
                                                               ↓
            动态路径：MASPlanner.to_graph_config() ←→ from_task_plan()
                                                               ↓
                                                       build_graph()

        与 MASPlanner.to_graph_config() 的关系：
          - 两者描述同一翻译逻辑，调用方向相反：
              planner.to_graph_config(plan)  → 由任务层主动输出图配置
              parser.from_task_plan(plan)    → 由图层主动消费任务计划
          - 实现时选择其一即可，两者保持签名对称，方便替换。

        典型调用链（未来）：
            plan         = planner.decompose(task)
            plan         = planner.assign(plan, available_agents)
            nodes, edges = parser.from_task_plan(plan)   ← 此方法
            app          = parser.build_graph(nodes, edges)

        Args:
            plan: 已填充 subtasks 和 assigned_agents 的 TaskPlan 实例。

        Returns:
            (nodes, edges) 元组，可直接传入 build_graph()。

        Raises:
            NotImplementedError: 子类实现前调用时抛出。
        """
        raise NotImplementedError(
            "from_task_plan() 尚未实现，"
            "请由开发者 A 在 WorkflowParser 子类中完成此翻译逻辑。"
        )

    # TODO: 未来增加 validate_config(config) 接口，
    #       在 parse 前进行配置校验，提供详细的错误提示
    # TODO: 未来增加 export_config(graph) 接口，
    #       将现有图结构导出为 YAML/JSON 配置文件


# ============================================================
# 独立翻译函数：TaskPlan → (List[NodeConfig], List[EdgeConfig])
# ============================================================

def _translate_plan_to_graph_config(
    plan: "TaskPlan",
) -> Tuple[List[NodeConfig], List[EdgeConfig]]:
    """
    将 TaskPlan 翻译为 (List[NodeConfig], List[EdgeConfig])。

    这是 planner 层与 workflow 层之间的唯一翻译点，以独立函数形式存在以避免：
      1. AutoAgentsMASPlanner.to_graph_config() 与 YAMLWorkflowParser.from_task_plan()
         重复实现同一逻辑
      2. workflow_parser 通过 __new__ 绕过 planner 实例化的脆弱依赖

    翻译规则：
      assigned_agents[node_id] → NodeConfig：
        - agent_name = agent_type（供 build_dynamic_graph 查 AGENT_TYPE_NAMES）
        - config 包含 system_prompt / subtask / output_schema / depends_on / temperature
      优先读 assigned_agents["__edges__"] 构建 EdgeConfig；
      若无 __edges__ → 从各节点 depends_on 字段重建；
      仍为空 → 退回线性顺序兜底。

    Args:
        plan: 已填充 subtasks 和 assigned_agents 的 TaskPlan 实例。

    Returns:
        (nodes, edges) 元组，可直接传入 build_graph() 或 build_dynamic_graph()。
    """
    from config.planner_config import NODE_DEFAULT_TEMPERATURE

    nodes: List[NodeConfig] = []
    for node_id in plan.subtasks:
        spec = plan.assigned_agents.get(node_id, {})
        node = NodeConfig(
            node_id=node_id,
            node_type="agent",
            # agent_name 存 Agent 类型名，build_dynamic_graph 据此实例化对应 Agent
            agent_name=spec.get("agent_type", "SimpleAgent"),
            config={
                "system_prompt": spec.get(
                    "system_prompt", f"你是{spec.get('role', node_id)}专家。"
                ),
                "subtask":       spec.get("subtask", ""),
                "output_schema": spec.get("output_schema", {}),
                "role":          spec.get("role", node_id),
                "depends_on":    spec.get("depends_on", []),
                "temperature":   NODE_DEFAULT_TEMPERATURE,
            },
        )
        nodes.append(node)

    # 构建边：优先读 __edges__，其次从 depends_on 重建，最后线性兜底
    # 关键：每一步都验证连通性，LLM 生成的边不足时自动降级，确保所有节点都被执行
    all_node_ids: List[str] = plan.subtasks

    def _is_fully_connected(edge_list: List[Dict], node_ids: List[str]) -> bool:
        """BFS 验证所有节点从入口出发均可到达。"""
        if not node_ids:
            return True
        adj: Dict[str, List[str]] = {}
        to_nodes: set = set()
        for e in edge_list:
            adj.setdefault(e["from"], []).append(e["to"])
            to_nodes.add(e["to"])
        # 入口节点 = 没有任何入边的节点（按 subtasks 顺序取第一个）
        entry = next((n for n in node_ids if n not in to_nodes), node_ids[0])
        visited: set = set()
        queue = [entry]
        while queue:
            cur = queue.pop(0)
            visited.add(cur)
            for nxt in adj.get(cur, []):
                if nxt not in visited:
                    queue.append(nxt)
        return visited == set(node_ids)

    raw_edges: List[Dict[str, Any]] = list(plan.assigned_agents.get("__edges__", []))

    # 尝试1：__edges__（LLM 生成的边，但可能不覆盖全部节点）
    if raw_edges and not _is_fully_connected(raw_edges, all_node_ids):
        from utils.logger import get_logger as _get_logger
        _get_logger(__name__).warning(
            f"[WorkflowParser] __edges__ 中 {len(raw_edges)} 条边无法覆盖全部 "
            f"{len(all_node_ids)} 个节点，降级为 depends_on 重建"
        )
        raw_edges = []

    # 尝试2：从各节点 depends_on 字段重建边
    if not raw_edges:
        seen: set = set()
        for node_id in all_node_ids:
            for dep in plan.assigned_agents.get(node_id, {}).get("depends_on", []):
                key = (dep, node_id)
                if key not in seen:
                    raw_edges.append({"from": dep, "to": node_id, "condition": None})
                    seen.add(key)
        if raw_edges and not _is_fully_connected(raw_edges, all_node_ids):
            from utils.logger import get_logger as _get_logger
            _get_logger(__name__).warning(
                "[WorkflowParser] depends_on 重建的边仍不连通，降级为线性链"
            )
            raw_edges = []

    # 尝试3（最终兜底）：按 subtasks 顺序构建线性链，保证所有节点都被执行
    if not raw_edges:
        for i in range(len(all_node_ids) - 1):
            raw_edges.append({
                "from": all_node_ids[i],
                "to":   all_node_ids[i + 1],
                "condition": None,
            })

    edges: List[EdgeConfig] = [
        EdgeConfig(from_node=e["from"], to_node=e["to"], condition=e.get("condition"))
        for e in raw_edges
    ]
    return nodes, edges


# ============================================================
# [实现] YAMLWorkflowParser 具体类
# ============================================================

class YAMLWorkflowParser(WorkflowParser):
    """
    WorkflowParser 具体实现，支持两条图构建路径：

    路径 A（文件路径，静态 / 调试 / 重放）：
        load_config(path) → parse_nodes() → parse_edges() → build_graph()
        支持 JSON 格式（默认）和 YAML 格式（需安装 PyYAML）。
        config/dynamic_workflow.json 由 AutoAgentsMASPlanner._persist_config() 自动生成。

    路径 B（内存路径，动态规划主链路）：
        from_task_plan(plan) → build_graph()
        直接消费 MASPlanner 输出的 TaskPlan，无 I/O 开销。

    两条路径最终均汇聚到 build_graph(nodes, edges)，
    调用 workflow.graph_builder.build_dynamic_graph() 编译 LangGraph 图。
    """

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        从 JSON 或 YAML 文件加载工作流配置。

        自动根据文件后缀选择解析器：
          .json → json.load（无需额外依赖）
          .yaml / .yml → yaml.safe_load（需安装 PyYAML）

        Args:
            config_path: 配置文件路径（绝对或相对）。

        Returns:
            原始配置字典，包含 nodes / edges / entry_node 等键。

        Raises:
            FileNotFoundError: 文件不存在时。
            ImportError:       YAML 文件但未安装 PyYAML 时。
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
                    raise ImportError(
                        "解析 YAML 文件需要安装 PyYAML：pip install pyyaml"
                    )
            else:
                import json
                return json.load(f)

    def parse_nodes(self, config: Dict[str, Any]) -> List[NodeConfig]:
        """
        从配置字典解析节点列表。

        期望的配置格式（对应 dynamic_workflow.json）：
            {
              "nodes": [
                {
                  "node_id":    "literature_review",
                  "node_type":  "agent",
                  "agent_name": "SimpleAgent",
                  "config": {
                    "system_prompt": "...",
                    "subtask":       "...",
                    "depends_on":    [],
                    "temperature":   0.7
                  }
                }
              ]
            }
        """
        raw_nodes = config.get("nodes", [])
        nodes: List[NodeConfig] = []
        for raw in raw_nodes:
            nodes.append(NodeConfig(
                node_id=    raw.get("node_id", "unknown"),
                node_type=  raw.get("node_type", "agent"),
                agent_name= raw.get("agent_name", "SimpleAgent"),
                tool_name=  raw.get("tool_name", ""),
                config=     raw.get("config", {}),
            ))
        return nodes

    def parse_edges(self, config: Dict[str, Any]) -> List[EdgeConfig]:
        """
        从配置字典解析边列表。

        期望的配置格式：
            {
              "edges": [
                {"from_node": "a", "to_node": "b", "condition": null}
              ]
            }
        """
        raw_edges = config.get("edges", [])
        edges: List[EdgeConfig] = []
        for raw in raw_edges:
            edges.append(EdgeConfig(
                from_node= raw.get("from_node", raw.get("from", "")),
                to_node=   raw.get("to_node",   raw.get("to",   "")),
                condition= raw.get("condition"),
            ))
        return edges

    def build_graph(self, nodes: List[NodeConfig], edges: List[EdgeConfig]) -> Any:
        """
        调用 build_dynamic_graph() 编译 LangGraph 图。

        这是两条路径（文件 / 内存）的汇聚点。
        nodes / edges 为空时，build_dynamic_graph() 内部自动回退到硬编码图。
        """
        from workflow.graph_builder import build_dynamic_graph
        return build_dynamic_graph(nodes=nodes, edges=edges)

    def from_task_plan(
        self,
        plan: "TaskPlan",
    ) -> Tuple[List[NodeConfig], List[EdgeConfig]]:
        """
        内存路径：直接从 TaskPlan 生成 (nodes, edges)，无需文件 I/O。

        典型调用链（动态规划主链路）：
            planner = AutoAgentsMASPlanner()
            plan    = planner.decompose(task)
            plan    = planner.assign(plan, [])
            parser  = YAMLWorkflowParser()
            nodes, edges = parser.from_task_plan(plan)   ← 此方法
            app     = parser.build_graph(nodes, edges)

        实现委托给 AutoAgentsMASPlanner.to_graph_config()，
        保持单一翻译逻辑，避免重复实现。

        Args:
            plan: 已填充 subtasks 和 assigned_agents 的 TaskPlan 实例。

        Returns:
            (nodes, edges) 元组，可直接传入 build_graph()。
        """
        return _translate_plan_to_graph_config(plan)
