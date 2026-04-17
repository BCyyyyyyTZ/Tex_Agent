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
