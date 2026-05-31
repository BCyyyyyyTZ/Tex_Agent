"""
MASPlanner 多智能体系统规划器（v2）。

Breaking Change v2：
  - 移除 PlanAgent prompt 中"图必须是严格单链/禁止并行"约束
  - _analyze_plan_topology 支持并行拓扑（parallel_fork/join 节点不计入"非法分支"）
  - _local_topology_issues 允许合法的并行分叉
  - Supervisor 审查规则覆盖并行 / 条件边有效性检查
  - PLAN_OUTPUT_SCHEMA 从 planner_config 导入（v2 版本支持并行）
"""
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from workflow.workflow_parser import NodeConfig, EdgeConfig
    from router.base_router import BaseRouter


@dataclass
class TaskPlan:
    """
    多 Agent 任务执行计划数据结构。

    Attributes:
        plan_id:        计划唯一标识符
        original_task:  原始用户任务描述
        subtasks:       分解后的 node_id 有序列表
        assigned_agents:{node_id: agent_spec} + "__edges__" + "__entry__" 特殊键
        status:         计划状态（pending / running / done / failed）
        created_at:     创建时间
        results:        各子任务执行结果
    """

    plan_id: str
    original_task: str
    subtasks: List[str] = field(default_factory=list)
    assigned_agents: dict = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    results: List[str] = field(default_factory=list)


class MASPlanner(ABC):
    """多智能体系统规划器抽象基类。"""

    @abstractmethod
    def decompose(self, task: str) -> TaskPlan:
        raise NotImplementedError

    @abstractmethod
    def assign(self, plan: TaskPlan, available_agents: List[str]) -> TaskPlan:
        raise NotImplementedError

    @abstractmethod
    def validate(self, plan: TaskPlan, results: List[str]) -> bool:
        raise NotImplementedError

    def to_graph_config(
        self,
        plan: "TaskPlan",
    ) -> "Tuple[List[NodeConfig], List[EdgeConfig]]":
        raise NotImplementedError(
            "to_graph_config() 尚未实现，请在 MASPlanner 子类中完成。"
        )


# ============================================================
# 从 config/planner_config.py 统一导入常量与工具函数
# ============================================================
from config.context_settings import (
    PROFILE_DIALOGUE,
    get_planner_extra_principles,
    get_planner_local_config,
    match_intent,
)
from config.context_settings import should_persona_file_write
from config.planner_config import (
    PLANNER_TEMPERATURE,
    MAX_PLAN_ROUNDS_DEFAULT,
    SUPERVISOR_MIN_QUALITY_SCORE,
    PLAN_OUTPUT_SCHEMA,
    SUPERVISOR_OUTPUT_SCHEMA,
    SINGLE_TURN_NODE_CONTRACT,
    parse_llm_json,
)

_PLAN_FALLBACK: Dict[str, Any] = {"agents": [], "edges": [], "entry_node": ""}
_SUPERVISOR_FALLBACK: Dict[str, Any] = {
    "approved": False,
    "quality_score": 0.0,
    "issues": ["Supervisor 输出不可解析"],
    "suggestions": "请按要求返回严格 JSON，并给出 revised_agents。",
    "revised_agents": [],
    "revised_edges": [],
    "revised_entry_node": "",
}

# 合法的 node_type 集合（v2 新增 parallel_fork / parallel_join）
_VALID_NODE_TYPES = frozenset({
    "agent", "tool", "user", "parallel_fork", "parallel_join"
})


class AutoAgentsMASPlanner(MASPlanner):
    """
    基于 AutoAgents 论文思路的多智能体规划器（v2）。

    规划流程：
        Round 1  : PlanAgent（LLM）生成初始 Agent 列表 + 图拓扑
        Round 2～N: Supervisor（LLM）审查并修订，直到通过或达到 max_plan_rounds
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_plan_rounds: int = MAX_PLAN_ROUNDS_DEFAULT,
        router: Optional["BaseRouter"] = None,
    ):
        from langchain_openai import ChatOpenAI
        from config.settings import settings

        self.model = model or settings.llm_model
        self.max_plan_rounds = max_plan_rounds
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
        """
        from utils.logger import get_logger
        logger = get_logger(__name__)

        logger.info(f"[AutoAgentsPlanner] 开始规划任务：{task[:80]}...")

        plan_json = self._plan_agent_call(task)

        prev_supervisor: Optional[Dict[str, Any]] = None
        for round_idx in range(1, self.max_plan_rounds):
            supervisor_result = self._supervisor_call(
                task, plan_json, round_idx=round_idx, prev_supervisor=prev_supervisor,
            )
            prev_supervisor = supervisor_result
            reject_reasons = self._collect_supervisor_reject_reasons(
                task=task, plan_json=plan_json, supervisor_result=supervisor_result,
            )
            if not reject_reasons:
                logger.info(
                    f"[AutoAgentsPlanner] Supervisor 第 {round_idx} 轮审查通过 "
                    f"(score={supervisor_result.get('quality_score', '?')})"
                )
                break
            logger.info(
                f"[AutoAgentsPlanner] 第 {round_idx} 轮未通过: {reject_reasons}"
            )
            supervisor_result["issues"] = reject_reasons
            self._apply_supervisor_revisions(plan_json, supervisor_result)

        agents: List[Dict] = plan_json.get("agents", [])
        subtasks = [a["node_id"] for a in agents]
        agent_specs: Dict[str, Any] = {a["node_id"]: dict(a) for a in agents}
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
        为计划中每个节点确定 Agent 类型，写回 assigned_agents。
        """
        from utils.logger import get_logger
        logger = get_logger(__name__)

        for node_id in plan.subtasks:
            spec = plan.assigned_agents.get(node_id)
            if spec is None:
                continue
            node_type = str(spec.get("node_type", "agent")).strip().lower()
            if node_type in ("tool", "user", "parallel_fork"):
                spec["route_source"] = f"{node_type}_node"
                continue

            agent_type = "SimpleAgent"
            complexity = "simple"
            route_source = "hardcoded"

            if self.router is not None:
                route_source = "BaseRouter(暂用SimpleAgent)"

            spec["agent_type"] = agent_type
            spec["complexity"] = complexity
            spec["route_source"] = route_source
            logger.info(
                f"[Planner] 节点 '{node_id}' → {agent_type} "
                f"(复杂度={complexity}, 来源={route_source})"
            )

        return plan

    def validate(self, plan: TaskPlan, results: List[str]) -> bool:
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
        翻译逻辑委托给 _translate_plan_to_graph_config。
        """
        from workflow.workflow_parser import _translate_plan_to_graph_config
        from utils.logger import get_logger
        logger = get_logger(__name__)

        nodes, edges = _translate_plan_to_graph_config(plan)
        self._persist_config(plan, nodes, edges)
        logger.info(f"[Planner] to_graph_config 完成：{len(nodes)} 节点，{len(edges)} 条边")
        return nodes, edges

    # ------------------------------------------------------------------
    # 内部 LLM 调用
    # ------------------------------------------------------------------

    def _plan_agent_call(self, task: str) -> Dict:
        """Round 1：PlanAgent LLM 调用。"""
        tool_catalog = self._build_tool_catalog_prompt()
        prompt = (
            f"你是多智能体系统规划师（PlanAgent）。\n"
            f"给定以下任务，请输出一个高质量的执行方案。\n\n"
            f"任务：{task}\n\n"
            f"可用工具目录（仅可使用以下工具，不得虚构）：\n"
            f"{tool_catalog}\n\n"
            f"规划原则：\n"
            f"1) 默认按[指导型任务]处理：讲清概念 + 给可执行步骤。\n"
            f"2) 节点数控制在 2~10 个，根据任务复杂程度选择。\n"
            f"2.1) node_type='tool' 与 node_type='user' 都是可选能力，默认不强制使用。\n"
            f"2.2) 仅当[确实能提升结果质量]时才使用 tool 节点；否则使用 agent 节点直接完成。\n"
            f"2.3) 若使用 tool 节点，必须包含 node_type='tool'、tool_name、tool_input；"
            f"tool_input 不能为空字符串，优先引用 ${'{metadata.<上游节点>.result}'}，否则使用 ${'{input}'}。\n"
            f"2.4) 仅当任务存在真实的人类决策点时，才允许插入 user 节点；"
            f"不得把原本应由 agent 完成的分析任务转嫁给用户。\n"
            f"2.5) 最终交付节点必须是 agent 节点，不得设置为 user/tool。\n"
            f"3) 图结构支持以下模式（可组合）：\n"
            f"   A) 线性链（默认）：A → B → C，简单任务推荐。\n"
            f"   B) 并行分叉：使用 parallel_fork + 多条出边 + parallel_join，"
            f"适合可并行独立分析的子任务（如同时检索文献 + 分析风险）。\n"
            f"   C) 条件路由：从一个节点出发，根据 metadata 字段值选择不同后继，"
            f"适合[如果质量够高就直接交付，否则走 review]类场景。\n"
            f"   并行节点中：parallel_fork 必须包含 parallel_branches 列表；"
            f"parallel_join 必须包含 source_branches 和 join_policy。\n"
            f"   条件边格式：edges 中 condition 字段为 "
            f'{{\"field\": \"metadata.<node_id>.<key>\", \"op\": \"gte\", \"value\": 0.7}}。\n'
            f"4) 必须包含[最终交付节点]（整合并输出最终可执行步骤给用户）。\n"
            f"5) 每个节点 subtask 必须可执行，避免空泛描述。\n"
            f"6) 每个节点必须满足[单次流水线执行契约]：禁止等待式追问用户。\n"
        )
        for i, line in enumerate(get_planner_extra_principles(), start=7):
            prompt += f"{i}) {line}\n"
        prompt += (
            "\n"
            f"单次流水线执行契约：\n{SINGLE_TURN_NODE_CONTRACT}\n\n"
            f"【输出规范（硬约束）】\n"
            f"- 必须且只能输出一个合法 JSON 对象，禁止任何解释、前言、后记。\n"
            f"- 绝对禁止 Markdown 代码块标记（例如 ```json / ```）。\n"
            f"- 输出首字符必须是 '{{'，末字符必须是 '}}'。\n"
            f"- 所有键必须使用双引号，禁止尾随逗号，禁止注释。\n"
            f"- 严格遵循以下 schema：\n{PLAN_OUTPUT_SCHEMA}"
        )
        raw = self._call_llm(prompt)
        return parse_llm_json(raw, context="PlanAgent", fallback=dict(_PLAN_FALLBACK))

    def _build_tool_catalog_prompt(self) -> str:
        from tools.tool_list import tool_list
        lines = []
        for tool in tool_list:
            schema = getattr(tool, "input_schema", {}) or {}
            lines.append(
                f"- tool_name: {getattr(tool, 'name', '')}\n"
                f"  description: {getattr(tool, 'description', '')}\n"
                f"  input_schema: {json.dumps(schema, ensure_ascii=False)}"
            )
        return "\n".join(lines) if lines else "（当前无可用工具）"

    def _supervisor_call(
        self,
        task: str,
        plan_json: Dict,
        round_idx: int,
        prev_supervisor: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Round 2～N：Supervisor LLM 调用。"""
        agents = plan_json.get("agents", [])
        topology = self._analyze_plan_topology(plan_json)
        topology_report = self._format_topology_report(topology)
        prev_score = ""
        prev_issues = ""
        if isinstance(prev_supervisor, dict):
            s = prev_supervisor.get("quality_score")
            if s is not None:
                prev_score = str(s)
            prev_iss = prev_supervisor.get("issues")
            if isinstance(prev_iss, list) and prev_iss:
                prev_issues = "\n".join(f"- {x}" for x in prev_iss)

        prompt = (
            f"你是多智能体工作流审查员（Supervisor）。\n"
            f"请审查以下规划方案。目标是：不降低质量前提下，减少无效打回并持续改进评分。\n\n"
            f"当前轮次：第 {round_idx} 轮\n"
            f"原始任务：{task}\n\n"
            f"当前规划方案：\n{json.dumps(plan_json, ensure_ascii=False, indent=2)}\n"
            f"{topology_report}\n"
            f"上一轮参考（若有）：\n"
            f"- 上一轮评分：{prev_score or '无'}\n"
            f"- 上一轮 issues：\n{prev_issues or '无'}\n\n"
            f"审查规则（仅拦截关键硬问题）：\n"
            f"1) 只有在以下情况才拒绝（approved=false）：\n"
            f"   - 图结构不合法（节点引用错误、孤立节点、无法到达所有节点）\n"
            f"   - parallel_fork 缺少 parallel_branches 或 parallel_branches 为空\n"
            f"   - parallel_join 缺少 source_branches 或 source_branches 为空\n"
            f"   - 条件边 condition 字段格式非法（必须是 {{field, op, value}} 对象或 null）\n"
            f"   - 条件边组缺少 fallback（无 condition=null 的兜底边）\n"
            f"   - 与用户意图明显相反\n"
            f"   - 任一节点出现等待式追问用户\n"
            f"   - 最终交付节点（图中最后一个 agent 节点）的 subtask 未要求生成充分详细内容（subtask 应明确要求生成结构化报告/完整答案/可执行方案）\n"
            f"2) 【软约束 - 影响 quality_score 但不强制拒绝】：\n"
            f"   - 最终交付节点 subtask 应明确要求 result 包含：完整结构化输出、各章节标题、至少300字内容\n"
            f"   - 上游若有并行分析节点，最终节点应明确整合所有分支产出\n"
            f"3) 轻微优化建议不能作为拒绝理由。\n"
            f"4) 若 approved=false，必须同时提供 revised_agents + revised_edges + revised_entry_node。\n"
            f"5) quality_score 使用 1~10 分制。\n"
            f"6) 当评分 >= {SUPERVISOR_MIN_QUALITY_SCORE:.2f} 且不存在关键硬问题时，优先 approved=true。\n\n"
            f"【输出规范（硬约束）】\n"
            f"- 必须且只能输出一个合法 JSON 对象，禁止任何解释、前言、后记。\n"
            f"- 严格遵循以下 schema：\n{SUPERVISOR_OUTPUT_SCHEMA}"
        )
        raw = self._call_llm(prompt)
        return parse_llm_json(raw, context="Supervisor", fallback=dict(_SUPERVISOR_FALLBACK))

    def _collect_supervisor_reject_reasons(
        self,
        task: str,
        plan_json: Dict[str, Any],
        supervisor_result: Dict[str, Any],
    ) -> List[str]:
        reasons: List[str] = []
        approved = bool(supervisor_result.get("approved", False))
        if not approved:
            reasons.append("Supervisor 未批准该方案")

        score_val = self._normalize_quality_score(supervisor_result.get("quality_score", 0.0))
        if score_val < SUPERVISOR_MIN_QUALITY_SCORE:
            reasons.append(
                f"Supervisor 分数过低({score_val:.2f} < {SUPERVISOR_MIN_QUALITY_SCORE:.2f})"
            )

        if not approved:
            issues = supervisor_result.get("issues", [])
            if isinstance(issues, list):
                for issue in issues:
                    txt = str(issue).strip()
                    if txt:
                        reasons.append(txt)

        reasons.extend(self._local_topology_issues(plan_json))
        reasons.extend(self._local_intent_issues(task, plan_json))
        reasons.extend(self._local_single_turn_contract_issues(plan_json))
        reasons.extend(self._local_plan_persona_issues(task, plan_json))
        reasons.extend(self._local_plan_echo_issues(task, plan_json))

        out: List[str] = []
        seen: set = set()
        for r in reasons:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    def _local_topology_issues(self, plan_json: Dict[str, Any]) -> List[str]:
        """
        本地拓扑校验（v2）：
        - 允许并行分叉（parallel_fork 节点可有多个后继）
        - 检查 parallel_fork / parallel_join 必填字段
        - 检查条件边 fallback
        """
        issues: List[str] = []
        topology = self._analyze_plan_topology(plan_json)

        if not topology["has_valid_agents"]:
            issues.append("规划中 agents 为空或格式错误")
            return issues
        if not topology["has_valid_edges"]:
            issues.append("规划中 edges 不是数组")
            return issues

        # 孤立节点（无法到达）
        unreachable = topology.get("unreachable_nodes", [])
        if unreachable:
            issues.append(f"存在无法从入口到达的孤立节点：{unreachable}")

        # 非法并行节点缺字段
        for msg in topology.get("parallel_issues", []):
            issues.append(msg)

        # 条件边组缺 fallback
        for msg in topology.get("condition_issues", []):
            issues.append(msg)

        # 孤悬节点引用
        dangling = topology.get("dangling_nodes", [])
        if dangling:
            issues.append(f"edges 引用了不存在节点：{dangling}")

        return issues

    def _local_intent_issues(self, task: str, plan_json: Dict[str, Any]) -> List[str]:
        """拦截意图偏移（答疑任务 → 实现+测试流水线）。"""
        issues: List[str] = []
        task_l = task.lower()
        consult_like = any(k in task for k in ["解答", "讲解", "说明", "分析", "怎么做", "如何", "步骤"]) or any(
            k in task_l for k in ["explain", "analysis", "answer", "how to", "steps"]
        )
        implement_like = any(k in task for k in ["实现", "编码", "写代码", "测试"]) or any(
            k in task_l for k in ["implement", "code", "test"]
        )
        if not consult_like or implement_like:
            return issues

        agents = plan_json.get("agents", [])
        risky_tokens = (
            "tester", "test", "unit test", "integration test",
            "测试", "单元测试", "集成测试", "回归测试",
        )
        if isinstance(agents, list):
            for agent in agents:
                if not isinstance(agent, dict):
                    continue
                text = " ".join(
                    str(agent.get(k, "")) for k in ("node_id", "role", "subtask", "expertise")
                ).lower()
                if any(tok in text for tok in risky_tokens):
                    issues.append(
                        "任务偏答疑/指导，但规划中出现明显测试/验收型节点，存在意图偏移"
                    )
                    break
        return issues

    def _local_plan_echo_issues(self, task: str, plan_json: Dict[str, Any]) -> List[str]:
        issues: List[str] = []
        if not match_intent("echo", task):
            return issues
        agents = plan_json.get("agents", [])
        if not isinstance(agents, list):
            return issues
        agent_nodes = [
            a for a in agents
            if isinstance(a, dict) and str(a.get("node_type", "agent")).lower() == "agent"
        ]
        if len(agent_nodes) != 1:
            issues.append("echo 意图任务应仅为 1 个 agent 终节点（见 context_config intent_patterns.echo）")
        return issues

    def _local_plan_persona_issues(self, task: str, plan_json: Dict[str, Any]) -> List[str]:
        issues: List[str] = []
        if should_persona_file_write(task, PROFILE_DIALOGUE):
            return issues
        pcfg = get_planner_local_config()
        persona_tools = [str(x).lower() for x in (pcfg.get("forbidden_persona_tool_names") or [])]
        sub_markers = list(pcfg.get("persona_subtask_markers") or [])
        task_markers = list(pcfg.get("persona_task_markers") or [])
        agents = plan_json.get("agents", [])
        if not isinstance(agents, list):
            return issues
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            if str(agent.get("node_type", "")).lower() == "tool":
                tname = str(agent.get("tool_name", "")).lower()
                if any(p in tname for p in persona_tools):
                    issues.append(
                        f"非画像任务不应规划画像工具节点: {agent.get('node_id', '?')}"
                    )
            sub = str(agent.get("subtask", "")) + str(agent.get("role", ""))
            if any(m in sub for m in sub_markers):
                if not any(k in task for k in task_markers):
                    issues.append(
                        f"节点 {agent.get('node_id', '?')} subtask 偏离任务，疑似画像复述"
                    )
        return issues

    def _local_single_turn_contract_issues(self, plan_json: Dict[str, Any]) -> List[str]:
        """拦截违反单次流水线契约的节点文案。"""
        issues: List[str] = []
        agents = plan_json.get("agents", [])
        if not isinstance(agents, list):
            return issues

        waiting_tokens = (
            "请先回答", "请先告诉我", "等你回复", "等你回答", "先确认后再",
            "please answer first", "wait for your reply", "after you reply",
        )
        handoff_tokens = (
            "下一节点", "下一个节点", "交给下一步", "由下游处理",
            "next node", "downstream node",
        )
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            node_id = str(agent.get("node_id", "")).strip() or "unknown_node"
            node_type = str(agent.get("node_type", "agent")).lower()
            if node_type in ("parallel_fork",):
                continue  # fork 节点无业务文案，跳过契约检查
            text = " ".join(
                str(agent.get(k, "")) for k in ("system_prompt", "subtask", "role")
            ).lower()
            if any(tok.lower() in text for tok in waiting_tokens):
                issues.append(f"节点 {node_id} 存在等待式追问用户，违反单次流水线契约")
            if any(tok.lower() in text for tok in handoff_tokens):
                issues.append(f"节点 {node_id} 存在任务外抛给下游/用户的描述，违反单次流水线契约")
        return issues

    def _normalize_quality_score(self, score: Any) -> float:
        try:
            score_val = float(score)
        except (TypeError, ValueError):
            return 0.0
        if 0.0 <= score_val <= 1.0:
            return score_val * 10.0
        return score_val

    def _apply_supervisor_revisions(
        self,
        plan_json: Dict[str, Any],
        supervisor_result: Dict[str, Any],
    ) -> None:
        revised_agents = supervisor_result.get("revised_agents")
        if isinstance(revised_agents, list) and revised_agents:
            plan_json["agents"] = revised_agents
        revised_edges = supervisor_result.get("revised_edges")
        if isinstance(revised_edges, list):
            plan_json["edges"] = revised_edges
        revised_entry = str(supervisor_result.get("revised_entry_node", "")).strip()
        if revised_entry:
            plan_json["entry_node"] = revised_entry

    def _analyze_plan_topology(self, plan_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析规划拓扑（v2：支持并行 / 条件边）。

        Breaking Change v2：
          - parallel_fork 节点允许多个后继（不算"非法并行"）
          - 检查 parallel_fork / parallel_join 必填字段
          - 检查条件边组是否有 fallback（condition=null 的边）
        """
        agents = plan_json.get("agents", [])
        edges = plan_json.get("edges", [])
        has_valid_agents = isinstance(agents, list) and bool(agents)
        has_valid_edges = isinstance(edges, list)

        node_ids: set = set()
        node_types: Dict[str, str] = {}
        parallel_forks: set = set()
        parallel_joins: set = set()

        if isinstance(agents, list):
            for a in agents:
                if isinstance(a, dict):
                    nid = str(a.get("node_id", "")).strip()
                    if nid:
                        node_ids.add(nid)
                        nt = str(a.get("node_type", "agent")).lower()
                        node_types[nid] = nt
                        if nt == "parallel_fork":
                            parallel_forks.add(nid)
                        elif nt == "parallel_join":
                            parallel_joins.add(nid)

        from_counts: Dict[str, int] = {}
        dangling_nodes: set = set()
        condition_groups: Dict[str, List[Any]] = {}  # from_node → list of edge dicts

        if isinstance(edges, list):
            for e in edges:
                if not isinstance(e, dict):
                    continue
                frm = str(e.get("from", "")).strip()
                to = str(e.get("to", "")).strip()
                if frm:
                    from_counts[frm] = from_counts.get(frm, 0) + 1
                    if node_ids and frm not in node_ids:
                        dangling_nodes.add(frm)
                    condition_groups.setdefault(frm, []).append(e)
                if to and node_ids and to not in node_ids:
                    dangling_nodes.add(to)

        # 非法并行：非 parallel_fork 节点有多个后继
        illegal_parallel: List[str] = [
            k for k, v in from_counts.items()
            if v > 1 and k not in parallel_forks
        ]

        # BFS 可达性检查
        entry_node = plan_json.get("entry_node", "")
        if not entry_node and node_ids:
            to_nodes: set = set()
            if isinstance(edges, list):
                for e in edges:
                    if isinstance(e, dict):
                        to_nodes.add(str(e.get("to", "")))
            entry_candidates = [n for n in (list(node_ids)) if n not in to_nodes]
            entry_node = entry_candidates[0] if entry_candidates else next(iter(node_ids))

        adj: Dict[str, List[str]] = {}
        if isinstance(edges, list):
            for e in edges:
                if isinstance(e, dict):
                    frm = str(e.get("from", ""))
                    to = str(e.get("to", ""))
                    if frm and to:
                        adj.setdefault(frm, []).append(to)

        visited: set = set()
        queue = [entry_node] if entry_node else []
        while queue:
            cur = queue.pop(0)
            visited.add(cur)
            for nxt in adj.get(cur, []):
                if nxt not in visited:
                    queue.append(nxt)
        unreachable = sorted(node_ids - visited)

        # parallel_fork / parallel_join 必填字段检查
        parallel_issues: List[str] = []
        if isinstance(agents, list):
            for a in agents:
                if not isinstance(a, dict):
                    continue
                nid = str(a.get("node_id", ""))
                nt = str(a.get("node_type", "agent")).lower()
                if nt == "parallel_fork":
                    branches = a.get("parallel_branches", [])
                    if not isinstance(branches, list) or not branches:
                        parallel_issues.append(
                            f"parallel_fork 节点 '{nid}' 缺少非空 parallel_branches 列表"
                        )
                elif nt == "parallel_join":
                    src = a.get("source_branches", [])
                    if not isinstance(src, list) or not src:
                        parallel_issues.append(
                            f"parallel_join 节点 '{nid}' 缺少非空 source_branches 列表"
                        )
                    jp = str(a.get("join_policy", "all_success"))
                    from config.planner_config import JOIN_POLICY_VALUES
                    if jp not in JOIN_POLICY_VALUES:
                        parallel_issues.append(
                            f"parallel_join 节点 '{nid}' 的 join_policy='{jp}' 非法，"
                            f"合法值: {JOIN_POLICY_VALUES}"
                        )

        # 条件边组 fallback 检查
        condition_issues: List[str] = []
        for frm, group in condition_groups.items():
            has_any_condition = any(
                isinstance(e.get("condition"), dict) for e in group
            )
            if has_any_condition:
                has_fallback = any(
                    e.get("condition") is None or e.get("condition") == "" for e in group
                )
                if not has_fallback:
                    condition_issues.append(
                        f"节点 '{frm}' 的条件边组缺少 fallback（需要一条 condition=null 的边）"
                    )

        return {
            "has_valid_agents": has_valid_agents,
            "has_valid_edges": has_valid_edges,
            "n_nodes": len(node_ids),
            "n_edges": len(edges) if isinstance(edges, list) else 0,
            "illegal_parallel_nodes": illegal_parallel,
            "dangling_nodes": sorted(dangling_nodes),
            "unreachable_nodes": unreachable,
            "parallel_issues": parallel_issues,
            "condition_issues": condition_issues,
            "parallel_forks": sorted(parallel_forks),
            "parallel_joins": sorted(parallel_joins),
        }

    def _format_topology_report(self, topology: Dict[str, Any]) -> str:
        illegal = topology.get("illegal_parallel_nodes", [])
        dangling = topology.get("dangling_nodes", [])
        unreachable = topology.get("unreachable_nodes", [])
        parallel_forks = topology.get("parallel_forks", [])
        parallel_joins = topology.get("parallel_joins", [])
        parallel_issues = topology.get("parallel_issues", [])
        condition_issues = topology.get("condition_issues", [])

        lines = [
            f"\n【图结构自动检测报告】",
            f"  节点数：{topology['n_nodes']}，边数：{topology['n_edges']}",
            f"  并行分叉节点：{parallel_forks or '无'}",
            f"  并行汇聚节点：{parallel_joins or '无'}",
            f"  非法多后继（非 parallel_fork）：{'✅ 无' if not illegal else '❌ ' + str(illegal)}",
            f"  孤悬节点引用：{'✅ 合法' if not dangling else '❌ ' + str(dangling)}",
            f"  不可达节点：{'✅ 无' if not unreachable else '❌ ' + str(unreachable)}",
        ]
        if parallel_issues:
            lines.append(f"  并行节点缺字段：❌ {parallel_issues}")
        if condition_issues:
            lines.append(f"  条件边缺 fallback：❌ {condition_issues}")
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage
        response = self._llm.invoke([HumanMessage(content=prompt)])
        return response.content if hasattr(response, "content") else str(response)

    def _persist_config(self, plan: TaskPlan, nodes: List, edges: List) -> None:
        """将规划结果序列化到 config/dynamic_workflow.json（调试用）。"""
        import os
        from utils.logger import get_logger
        logger = get_logger(__name__)

        config_data: Dict = {
            "plan_id": plan.plan_id,
            "original_task": plan.original_task,
            "entry_node": plan.assigned_agents.get(
                "__entry__", plan.subtasks[0] if plan.subtasks else ""
            ),
            "nodes": [
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "agent_name": n.agent_name,
                    "tool_name": n.tool_name,
                    "config": n.config,
                    "parallel_branches": n.parallel_branches,
                    "join_policy": n.join_policy,
                    "source_branches": n.source_branches,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "from_node": e.from_node,
                    "to_node": e.to_node,
                    "condition": e.condition.to_dict() if e.condition else None,
                    "priority": e.priority,
                }
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
