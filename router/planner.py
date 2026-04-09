"""
[扩展] MASPlanner 多智能体系统规划器接口定义。
预留主控引擎的任务分解、Agent 分配与执行验证接口。

TODO: 开发者 D 负责实现此类（第二阶段任务，建议与 BaseRouter 配合使用）
"""
import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    # 仅用于类型提示，运行时不导入，避免与 workflow 层产生循环依赖
    from workflow.workflow_parser import NodeConfig, EdgeConfig
    from router.base_router import BaseRouter


@dataclass
class TaskPlan:
    """
    多 Agent 任务执行计划数据结构。

    Attributes:
        plan_id: 计划唯一标识符。
        original_task: 原始用户任务描述文本。
        subtasks: 分解后的子任务描述列表（自然语言）。
        assigned_agents: 子任务与 Agent 的分配映射
                         {subtask_index: agent_name}。
        status: 计划状态（"pending" / "running" / "done" / "failed"）。
        created_at: 计划创建的 UTC 时间戳。
        results: 各子任务的执行结果列表（与 subtasks 对应）。
    """

    plan_id: str
    original_task: str
    subtasks: List[str] = field(default_factory=list)
    assigned_agents: dict = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    results: List[str] = field(default_factory=list)


class MASPlanner(ABC):
    """
    [扩展] 多智能体系统规划器抽象基类。

    功能规划：
        1. 任务分解（Task Decomposition）：
           将用户的复杂任务分解为可并行或串行的子任务列表
        2. 任务分配（Task Assignment）：
           将子任务分配给最合适的 Agent（配合 BaseRouter 使用）
        3. 执行监控（Execution Monitoring）：
           追踪各子任务的执行状态，处理失败重试
        4. 结果验证（Result Validation）：
           验证子任务结果是否满足质量要求

    适用场景：复杂的多 Agent 协同任务，如：
        用户任务："帮我写论文的 Introduction 章节"
        分解为：
          - subtask_1 → DesignAgent：规划 Introduction 结构
          - subtask_2 → ArxivSearchTool：检索背景文献
          - subtask_3 → ExecuteAgent：撰写 Introduction 草稿
          - subtask_4 → ReflectionAgent：润色与优化

    TODO: 开发者 D 实现建议：
          - decompose() 使用 LLM 进行任务分解，输出结构化的子任务列表
          - assign() 配合 BaseRouter.evaluate_complexity() 选择合适 Agent
          - validate() 使用 LLM 评估结果质量，决定是否需要重试
    """

    @abstractmethod
    def decompose(self, task: str) -> TaskPlan:
        """
        将复杂任务分解为子任务计划。

        Args:
            task: 原始用户任务描述字符串。

        Returns:
            包含子任务列表的 TaskPlan 对象（subtasks 已填充，status="pending"）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def assign(self, plan: TaskPlan, available_agents: List[str]) -> TaskPlan:
        """
        为计划中的每个子任务分配合适的 Agent。

        Args:
            plan: 待分配的 TaskPlan（subtasks 已填充）。
            available_agents: 当前可用的 Agent 名称列表。

        Returns:
            填充了 assigned_agents 字典的 TaskPlan。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, plan: TaskPlan, results: List[str]) -> bool:
        """
        验证子任务执行结果是否满足质量要求。

        Args:
            plan: 原始任务计划（含任务描述和分配信息）。
            results: 各子任务的执行结果列表（与 plan.subtasks 对应）。

        Returns:
            True 表示所有结果满足要求，可进入整合阶段；
            False 表示结果不满足要求，需要重试或调整策略。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def to_graph_config(
        self,
        plan: "TaskPlan",
    ) -> "Tuple[List[NodeConfig], List[EdgeConfig]]":
        """
        [扩展] 将 MASPlanner 生成的 TaskPlan 翻译为图拓扑配置。

        这是 MASPlanner 与 WorkflowParser 之间的"协议转换器"，
        填补任务规划层与图构建层之间缺失的翻译环节。

        典型调用链（未来）：
            plan          = planner.decompose(task)
            plan          = planner.assign(plan, available_agents)
            nodes, edges  = planner.to_graph_config(plan)   ← 此方法
            app           = parser.build_graph(nodes, edges)

        翻译规则（实现建议）：
          - plan.subtasks[i]        → NodeConfig(node_id=f"step_{i}", ...)
          - plan.assigned_agents[i] → NodeConfig.agent_name
          - 串行依赖                → EdgeConfig(from_node="step_i",
                                                  to_node="step_{i+1}")
          - 含 "validate"/"reflect" → EdgeConfig(condition="state['validated']")
            的校验类子任务            带条件边，支持质量不达标时的回环重试

        Args:
            plan: 已填充 subtasks 和 assigned_agents 的 TaskPlan 实例。

        Returns:
            (nodes, edges) 元组，可直接传入 WorkflowParser.build_graph()。

        Raises:
            NotImplementedError: 子类实现前调用时抛出。
        """
        raise NotImplementedError(
            "to_graph_config() 尚未实现，"
            "请由开发者 D 在 MASPlanner 子类中完成此翻译逻辑。"
        )

    # TODO: 未来增加 monitor(plan_id) 接口，实时追踪计划执行状态
    # TODO: 未来增加 replan(plan, failed_subtask_idx) 接口，
    #       当子任务失败时动态调整执行计划
    # TODO: 未来增加 aggregate(plan, results) 接口，
    #       整合所有子任务结果生成最终答案


# ============================================================
# 从 config/planner_config.py 统一导入常量与工具函数
# 调参只需修改 config/planner_config.py，无需改动此业务文件
# ============================================================
from config.planner_config import (
    PLANNER_TEMPERATURE,
    MAX_PLAN_ROUNDS_DEFAULT,
    COMPLEXITY_AGENT_MAP,
    COMPLEXITY_COMPLEX_KEYWORDS,
    COMPLEXITY_MEDIUM_KEYWORDS,
    PLAN_OUTPUT_SCHEMA,
    SUPERVISOR_OUTPUT_SCHEMA,
    parse_llm_json,
)


# ============================================================
# [实现] AutoAgentsMASPlanner 具体类
# ============================================================

class AutoAgentsMASPlanner(MASPlanner):
    """
    基于 AutoAgents 论文思路的多智能体规划器具体实现。

    规划流程（PlanAgent + Supervisor 多轮迭代）：
        Round 1  : PlanAgent（LLM）生成初始专家 Agent 列表 + 图拓扑
        Round 2～N: Supervisor（LLM）审查并修订，直到 approved=true 或达到 max_plan_rounds

    与 BaseRouter 的集成（预留接口）：
        assign() 方法是 BaseRouter 的接入点：
          - router=None（当前）：使用 _infer_complexity() 关键词规则推断复杂度，
            再通过 COMPLEXITY_AGENT_MAP 映射到 Agent 类型，默认均为 SimpleAgent。
          - router 已实现（未来）：调用 router.evaluate_complexity() 获取复杂度标签，
            或升级为 router.route() 直接获取 RouteDecision（含 agent 实例）。
            届时只需修改 assign() 内部逻辑，planner 其余部分不受影响。

    NodeConfig.agent_name 字段约定：
        to_graph_config() 将 assigned_agents[node_id]["agent_type"] 写入
        NodeConfig.agent_name，build_dynamic_graph() 据此从 AGENT_REGISTRY
        实例化对应类型的 Agent（SimpleAgent / ReActAgent / PlanAndSolveAgent）。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_plan_rounds: int = MAX_PLAN_ROUNDS_DEFAULT,
        router: Optional["BaseRouter"] = None,
    ):
        """
        Args:
            model:           PlanAgent 和 Supervisor 使用的 LLM 模型名称。
                             None（默认）时自动读取 config/settings.py 的 settings.llm_model，
                             即 .env 文件中的 LLM_MODEL 变量，与全局其他 Agent 保持一致。
                             显式传入时覆盖全局设置（用于单独测试某个模型）。
            max_plan_rounds: PlanAgent ↔ Supervisor 最大迭代轮数（含第一轮生成）。
            router:          BaseRouter 实例（可选）。
                             ┌─ None（默认）：assign() 使用关键词规则推断复杂度。
                             └─ 已实现时传入：assign() 调用 router.evaluate_complexity()
                                评估每个节点子任务复杂度，再映射到 Agent 类型。
                             NOTE: BaseRouter 完整实现后建议始终传入此参数以启用
                                   智能路由，届时每个节点可获得最适合的 Agent 架构。
        """
        from langchain_openai import ChatOpenAI
        from config.settings import settings

        # model 未指定时，与全局 Agent 使用同一个模型（统一从 .env 的 LLM_MODEL 读取）
        self.model = model or settings.llm_model
        self.max_plan_rounds = max_plan_rounds
        # [BaseRouter 预留接口] 存储 router 实例，assign() 中按需调用
        self.router: Optional["BaseRouter"] = router
        self._llm = ChatOpenAI(
            model=self.model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=PLANNER_TEMPERATURE,
        )

    # ------------------------------------------------------------------
    # MASPlanner 抽象方法实现
    # ------------------------------------------------------------------

    def decompose(self, task: str) -> TaskPlan:
        """
        PlanAgent + Supervisor 多轮迭代生成 TaskPlan。

        执行步骤：
          1. PlanAgent LLM 调用 → 生成初始 agent 规格列表和图拓扑（JSON）
          2. 循环 max_plan_rounds-1 次：
             a. Supervisor LLM 调用 → 审查 agent 列表
             b. approved=True → 提前退出
             c. approved=False → 用 revised_agents 替换 agents，继续迭代
          3. 将最终 plan_json 打包为 TaskPlan 返回

        TaskPlan 字段约定（与抽象接口兼容）：
          subtasks       : List[str]，按执行顺序排列的 node_id 列表
          assigned_agents: Dict[node_id, agent_spec]，完整 agent 规格字典
                           （assign() 会在其中追加 agent_type / complexity 字段）
        """
        from utils.logger import get_logger
        logger = get_logger(__name__)

        logger.info(f"[AutoAgentsPlanner] 开始规划任务：{task[:80]}...")

        # Round 1：PlanAgent 生成初始方案
        plan_json = self._plan_agent_call(task)

        # Round 2～N：Supervisor 迭代审查
        for round_idx in range(1, self.max_plan_rounds):
            supervisor_result = self._supervisor_call(task, plan_json)
            if supervisor_result.get("approved", False):
                logger.info(f"[AutoAgentsPlanner] Supervisor 第 {round_idx} 轮审查通过 "
                            f"(score={supervisor_result.get('quality_score', '?')})")
                break
            logger.info(f"[AutoAgentsPlanner] Supervisor 第 {round_idx} 轮审查未通过，"
                        f"issues={supervisor_result.get('issues', [])}")
            revised = supervisor_result.get("revised_agents")
            if revised:
                plan_json["agents"] = revised

        agents: List[Dict] = plan_json.get("agents", [])
        # subtasks 保存有序 node_id 列表（执行顺序由 entry_node + edges 决定，
        # 此处简化为 agents 出现顺序，to_graph_config 会重建边）
        subtasks = [a["node_id"] for a in agents]
        # assigned_agents 存储完整规格，assign() 和 to_graph_config() 均读取此字段
        agent_specs: Dict[str, Any] = {a["node_id"]: dict(a) for a in agents}
        # 将顶层 edges 也存入，供 to_graph_config() 构建 EdgeConfig
        agent_specs["__edges__"] = plan_json.get("edges", [])
        agent_specs["__entry__"] = plan_json.get("entry_node", subtasks[0] if subtasks else "")

        return TaskPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            original_task=task,
            subtasks=subtasks,
            assigned_agents=agent_specs,
            status="pending",
        )

    def assign(self, plan: TaskPlan, available_agents: List[str]) -> TaskPlan:
        """
        为计划中每个节点确定 Agent 类型，并将结果写回 assigned_agents。

        [BaseRouter 预留接口] 路由优先级：
          1. self.router 已注入 → router.evaluate_complexity(msg) 评估复杂度
             （未来可升级为 router.route(msg) 直接返回 RouteDecision）
          2. self.router 为 None → _infer_complexity() 关键词规则推断
          3. 任何异常 → 兜底 "SimpleAgent"

        写入字段（追加到 assigned_agents[node_id]）：
          agent_type  : str  — Agent 类名（对应 build_dynamic_graph 中的 AGENT_REGISTRY）
          complexity  : str  — "simple" / "medium" / "complex"
          route_source: str  — "BaseRouter" / "rule" / "fallback"
        """
        from utils.logger import get_logger
        logger = get_logger(__name__)

        for node_id in plan.subtasks:
            spec = plan.assigned_agents.get(node_id)
            if spec is None:
                continue
            subtask_text = spec.get("subtask", node_id)

            # --- [BaseRouter 预留接口] ---
            # 当前阶段：仅 SimpleAgent 已实现，直接固定使用，跳过复杂度推断。
            # 待 ReActAgent / PlanAndSolveAgent 实现后：
            #   1. 若 self.router 已注入 → 调用 router.evaluate_complexity(msg) 评估复杂度
            #   2. 否则                  → 调用 _infer_complexity(subtask_text) 关键词推断
            #   3. 两者均通过 _resolve_agent_type(complexity) 映射到 Agent 类型
            if self.router is not None:
                # NOTE: 未来升级点——解注释以下代码以启用 BaseRouter 路由
                # try:
                #     from core.message import AgentMessage
                #     msg = AgentMessage(role="user", content=subtask_text)
                #     complexity = self.router.evaluate_complexity(msg)
                #     route_source = "BaseRouter"
                # except Exception as e:
                #     logger.warning(f"[Planner] BaseRouter 路由失败({e})，回退规则推断")
                #     complexity = self._infer_complexity(subtask_text)
                #     route_source = "fallback"
                agent_type = "SimpleAgent"
                complexity = "simple"
                route_source = "BaseRouter(暂用SimpleAgent)"
            else:
                # 当前唯一可用 Agent，待其他 Agent 实现后移除此硬编码
                agent_type = "SimpleAgent"
                complexity = "simple"
                route_source = "hardcoded"

            spec["agent_type"] = agent_type
            spec["complexity"] = complexity
            spec["route_source"] = route_source

            logger.info(
                f"[Planner] 节点 '{node_id}' → {agent_type} "
                f"(复杂度={complexity}, 来源={route_source})"
            )

        return plan

    def validate(self, plan: TaskPlan, results: List[str]) -> bool:
        """
        调用 LLM 对所有子任务结果进行整体质量验证。

        Returns:
            True  → 所有结果满足要求，可进入整合阶段。
            False → 结果不满足要求，需要重试或调整策略。
        """
        results_text = "\n".join(
            f"节点 {node_id}（{plan.assigned_agents.get(node_id, {}).get('role', '')}）："
            f"{result[:300]}..."
            for node_id, result in zip(plan.subtasks, results)
        )
        prompt = (
            f"你是质量审核专家。请评估以下多 Agent 任务执行结果是否整体满足原始需求。\n\n"
            f"原始任务：{plan.original_task}\n\n"
            f"各节点执行结果：\n{results_text}\n\n"
            f'必须且只能输出 JSON：{{"passed": true或false, "quality_score": 0.0到1.0, "reason": "..."}}'
        )
        raw = self._call_llm(prompt)
        parsed = parse_llm_json(raw, context="validate", fallback={"passed": False})
        return bool(parsed.get("passed", False))

    def to_graph_config(self, plan: TaskPlan) -> "Tuple[List[NodeConfig], List[EdgeConfig]]":
        """
        将 TaskPlan 翻译为 (List[NodeConfig], List[EdgeConfig])。

        翻译逻辑委托给 workflow/workflow_parser.py 中的独立函数
        _translate_plan_to_graph_config()，避免重复实现和循环依赖。
        本方法在翻译完成后额外执行持久化（写 dynamic_workflow.json）。

        副作用：
          同步将配置序列化到 config/dynamic_workflow.json（供调试 / 文件路径复用）。
        """
        # 局部导入避免循环依赖（调用时两模块均已完整加载）
        from workflow.workflow_parser import _translate_plan_to_graph_config
        from utils.logger import get_logger
        logger = get_logger(__name__)

        nodes, edges = _translate_plan_to_graph_config(plan)
        self._persist_config(plan, nodes, edges)
        logger.info(f"[Planner] to_graph_config 完成：{len(nodes)} 节点，{len(edges)} 条边")
        return nodes, edges

    # ------------------------------------------------------------------
    # [BaseRouter 预留接口] 复杂度推断 & Agent 类型解析
    # ------------------------------------------------------------------

    def _resolve_agent_type(self, complexity: str) -> str:
        """
        将复杂度标签映射为 Agent 类型名称。

        [BaseRouter 预留接口] 此方法是 BaseRouter → Agent 类型的"翻译层"：
          - 当前：由 _infer_complexity() 的关键词规则输出驱动。
          - 未来：由 router.evaluate_complexity() 或 router.route() 的输出驱动。
          若 COMPLEXITY_AGENT_MAP 中对应类型尚未实现，build_dynamic_graph()
          会在 AGENT_REGISTRY 中检测并自动降级为 SimpleAgent。

        对应关系（与 BaseRouter.evaluate_complexity() 返回值严格对齐）：
          "simple"  → SimpleAgent        （当前可运行）
          "medium"  → ReActAgent          （待 ReActAgent 完整实现后激活）
          "complex" → PlanAndSolveAgent   （待 PlanAndSolveAgent 完整实现后激活）
        """
        return COMPLEXITY_AGENT_MAP.get(complexity, "SimpleAgent")

    def _infer_complexity(self, subtask_text: str) -> str:
        """
        基于关键词规则推断子任务复杂度（router=None 时的规则兜底）。

        当 BaseRouter 实现并传入 self.router 后，此方法将被
        router.evaluate_complexity() 替代，但保留作为极端情况下的
        无 LLM / 无 Router 兜底，确保系统在任何环境下均可运行。

        Returns:
            "simple" / "medium" / "complex"（与 COMPLEXITY_AGENT_MAP 键对齐）
        """
        text = subtask_text.lower()
        if any(kw in text for kw in COMPLEXITY_COMPLEX_KEYWORDS):
            return "complex"
        if any(kw in text for kw in COMPLEXITY_MEDIUM_KEYWORDS):
            return "medium"
        return "simple"

    # ------------------------------------------------------------------
    # 内部 LLM 调用
    # ------------------------------------------------------------------

    def _plan_agent_call(self, task: str) -> Dict:
        """Round 1：PlanAgent LLM 调用，生成初始 agent 列表和图结构。"""
        prompt = (
            f"你是多智能体系统规划师（PlanAgent）。\n"
            f"给定以下任务，规划完成任务所需的专家 Agent 列表和执行图结构。\n\n"
            f"任务：{task}\n\n"
            f"要求：\n"
            f"1. 每个 Agent 职责明确、不重叠\n"
            f"2. system_prompt 详细描述角色、专长和行为准则（不含输出格式约束，由框架统一注入）\n"
            f"3. 节点数量控制在 2～6 个\n\n"
            f"【图结构强制约束 - 必须严格遵守】\n"
            f"- 图必须是严格的单链（线性序列）：A → B → C → ...\n"
            f"- 禁止并行分支：每个节点只能有最多一个后继节点\n"
            f"- edges 中每个 from 值只能出现一次\n"
            f"- depends_on 中每个节点只能依赖紧邻的上一个节点（最多一个前驱）\n"
            f"- edges 数量必须恰好等于节点数量减一（n 个节点对应 n-1 条边）\n\n"
            f"必须且只能输出如下 JSON 格式（不要任何其他内容）：\n{PLAN_OUTPUT_SCHEMA}"
        )
        raw = self._call_llm(prompt)
        return parse_llm_json(raw, context="PlanAgent",
                              fallback={"agents": [], "edges": [], "entry_node": ""})

    def _supervisor_call(self, task: str, plan_json: Dict) -> Dict:
        """Round 2～N：Supervisor LLM 调用，审查并修订 agent 列表。"""
        agents = plan_json.get("agents", [])
        edges  = plan_json.get("edges", [])
        n_nodes = len(agents)
        n_edges = len(edges)
        # 统计每个 from 节点出现次数，大于 1 则存在并行分支
        from_counts: Dict[str, int] = {}
        for e in edges:
            key = e.get("from", "")
            from_counts[key] = from_counts.get(key, 0) + 1
        parallel_nodes = [k for k, v in from_counts.items() if v > 1]

        topology_report = (
            f"\n【图结构自动检测报告】\n"
            f"  节点数：{n_nodes}，边数：{n_edges}，"
            f"线性链期望边数：{max(0, n_nodes - 1)}\n"
            f"  边数检查：{'✅ 正确' if n_edges == max(0, n_nodes - 1) else '❌ 不符（存在缺失或多余的边）'}\n"
            f"  并行分支：{'✅ 无' if not parallel_nodes else f'❌ 以下节点有多个后继（并行），必须修正：{parallel_nodes}'}\n"
        )

        prompt = (
            f"你是多智能体工作流审查员（Supervisor）。\n"
            f"请你严格审查以下多 Agent 规划方案是否合理完整。\n\n"
            f"原始任务：{task}\n\n"
            f"当前规划方案：\n{json.dumps(plan_json, ensure_ascii=False, indent=2)}\n"
            f"{topology_report}\n"
            f"审查要点（按优先级）：\n"
            f"1. 【最高优先 - 图结构】若上方检测报告有 ❌，必须返回 approved=false，\n"
            f"   并在 revised_agents 中提供修正方案（确保为单链、边数=节点数-1、无并行分支）\n"
            f"2. Agent 列表是否覆盖完成任务的所有关键环节？\n"
            f"3. 执行顺序（edges / depends_on）是否合理？\n"
            f"4. 是否存在冗余或职责不清的 Agent？\n"
            f"5. 每个 Agent 的 system_prompt 是否足够详细？\n\n"
            f"必须且只能输出如下 JSON 格式：\n{SUPERVISOR_OUTPUT_SCHEMA}"
        )
        raw = self._call_llm(prompt)
        return parse_llm_json(raw, context="Supervisor", fallback={"approved": True})

    def _call_llm(self, prompt: str) -> str:
        """统一 LLM 调用入口，返回纯文本响应字符串。"""
        from langchain_core.messages import HumanMessage
        response = self._llm.invoke([HumanMessage(content=prompt)])
        return response.content if hasattr(response, "content") else str(response)

    def _persist_config(self, plan: TaskPlan, nodes: List, edges: List) -> None:
        """
        将规划结果序列化到 config/dynamic_workflow.json（调试 / 文件路径复用）。
        写入失败不影响主流程（异常静默处理）。
        """
        import os
        from utils.logger import get_logger
        logger = get_logger(__name__)

        config_data: Dict = {
            "plan_id":      plan.plan_id,
            "original_task": plan.original_task,
            "entry_node":   plan.assigned_agents.get("__entry__",
                            plan.subtasks[0] if plan.subtasks else ""),
            "nodes": [
                {
                    "node_id":    n.node_id,
                    "node_type":  n.node_type,
                    "agent_name": n.agent_name,
                    "config":     n.config,
                }
                for n in nodes
            ],
            "edges": [
                {"from_node": e.from_node, "to_node": e.to_node, "condition": e.condition}
                for e in edges
            ],
        }
        try:
            config_path = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "..", "config", "dynamic_workflow.json")
            )
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            logger.info(f"[Planner] 规划结果已写入 {config_path}")
        except Exception as e:
            logger.warning(f"[Planner] 写入 dynamic_workflow.json 失败（不影响运行）: {e}")
