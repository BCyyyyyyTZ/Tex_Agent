# core/agent_cli.py
"""
TeX Agent CLI 核心类
"""
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime

from utils.logger import get_logger
from utils.loading_spinner import run_with_loading
from utils.display import display
from workflow.graph_builder import build_app_from_workflow
from workflow.run_dump import create_run_output_dir
from context.context_manager import ContextManager
from core.message import ensure_message
from core.state import normalize_messages_for_state
from memory.factory import MemoryFactory
from memory.persona_memory import get_shared_user_persona_memory
from cli.commands import CommandRegistry
from cli.branch_commands import BRANCH_COMMANDS
from cli.task_commands import get_task_commands
from workflow.workflow_parser import EdgeConfig, NodeConfig

logger = get_logger(__name__)


def _serialize_plan_graph_for_ui(nodes: List[Any], edges: List[Any]) -> Dict[str, Any]:
    """将规划得到的 NodeConfig/EdgeConfig 转为可 JSON 序列化的 dict，供 Web 图示。"""
    out_nodes: List[Dict[str, Any]] = []
    for n in nodes:
        if isinstance(n, NodeConfig):
            out_nodes.append(
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "agent_name": n.agent_name,
                    "tool_name": n.tool_name,
                    "config": dict(n.config or {}),
                    "parallel_branches": list(n.parallel_branches or []),
                    "join_policy": n.join_policy,
                    "source_branches": list(n.source_branches or []),
                }
            )
    out_edges: List[Dict[str, Any]] = []
    for e in edges:
        if isinstance(e, EdgeConfig):
            cond = None
            if e.condition is not None:
                cond = e.condition.to_dict()
            out_edges.append(
                {
                    "from_node": e.from_node,
                    "to_node": e.to_node,
                    "condition": cond,
                    "priority": e.priority,
                }
            )
    return {"nodes": out_nodes, "edges": out_edges}


class TeXAgentCLI:
    """TeX Agent CLI 核心类"""
    DEFAULT_WORKFLOW = "default"
    
    def __init__(self, use_branch: bool = True):
        self.use_branch = use_branch
        self.current_branch = "main"
        
        # 每个分支独立的上下文
        self.contexts: Dict[str, ContextManager] = {}
        self.memory_system = self._init_memory_system()
        # 全局用户画像：与对话分支、工作流节点解耦；持久化见 memory_store/user_persona.json
        self.persona_memory = get_shared_user_persona_memory()
        self.context = None
        
        # 命令注册表
        self.command_registry = CommandRegistry()
        self._register_commands()
        
        # 构建工作流
        self._rebuild_workflow()
    
    def _init_memory_system(self) -> Dict:
        """初始化记忆系统"""
        if self.use_branch:
            return {
                "design": MemoryFactory.create_private_memory("design", branch_enabled=True),
                "think": MemoryFactory.create_private_memory("think", branch_enabled=True),
                "execute": MemoryFactory.create_private_memory("execute", branch_enabled=True),
                "shared": MemoryFactory.create_shared_memory(branch_enabled=True),
            }
        else:
            return {
                "design": MemoryFactory.create_memory("private", "design"),
                "think": MemoryFactory.create_memory("private", "think"),
                "execute": MemoryFactory.create_memory("private", "execute"),
                # 会话落盘仍走 shared.jsonl；与 use_branch=True 时一致使用 BranchMemory
                "shared": MemoryFactory.create_shared_memory(branch_enabled=False),
            }
    
    def _register_commands(self):
        """注册所有命令"""
        # 注册分支命令
        for cmd in BRANCH_COMMANDS:
            self.command_registry.register(cmd)
        
        # 注册任务命令
        for cmd in get_task_commands(self.command_registry):
            self.command_registry.register(cmd)
    
    def _get_context(self, branch: str = None) -> ContextManager:
        """获取指定分支的上下文"""
        branch_name = branch or self.current_branch
        if branch_name not in self.contexts:
            self.contexts[branch_name] = ContextManager(max_messages=200, default_limit=20)
            logger.info(f"为分支 '{branch_name}' 创建新上下文")
        return self.contexts[branch_name]
    
    def _rebuild_workflow(self):
        """重建运行上下文（按分支切换）。"""
        self.context = self._get_context(self.current_branch)
        logger.info(f"已为分支 '{self.current_branch}' 重建工作流")

    def _build_app_for_workflow(self, workflow_name: Optional[str]) -> Any:
        """
        统一通过 build_graph 构建工作流（默认/自定义共一路径）。
        """
        target_name = workflow_name or self.DEFAULT_WORKFLOW
        # 与 messages 同生命周期：ctx.build 的 memory 检索走当前分支会话，不用持久化 shared jsonl
        return build_app_from_workflow(
            workflow_name=target_name,
            context_manager=self.context,
            persona_memory=self.persona_memory,
            runtime_memory=self.context,
            human_input_provider=self._human_input_provider,
        )

    def _human_input_provider(self, prompt: str, schema: Dict[str, Any], rules: Dict[str, Any]) -> Any:
        """
        默认的人类输入提供器，可被替换/注入以支持 GUI、Web、测试桩。
        """
        _ = rules
        print(f"\n🙋 用户节点请求: {prompt}")
        options = schema.get("options", []) if isinstance(schema, dict) else []
        if isinstance(options, list) and options:
            print(f"   可选项: {options}")
        return input("   请输入反馈: ")

    def _persist_new_messages_to_shared_memory_store(
        self, new_messages_raw: List[Any], workflow_label: str
    ) -> None:
        """
        将本轮追加到会话的消息同步写入 shared BranchMemory（memory_store/*.jsonl）。

        说明：ctx.build 的检索仍走 ContextManager + state.messages（会话级）；
        此处仅做与对话同语义的持久化，便于跨重启检索与 show_status 统计。
        """
        shared = self.memory_system.get("shared")
        if shared is None or not hasattr(shared, "save"):
            return
        for raw in new_messages_raw:
            msg = ensure_message(
                raw,
                default_role="assistant",
                default_source_type="system",
                default_source_id="workflow",
            )
            body = str(msg.content or "").strip()
            if not body:
                continue
            key = f"session:{self.current_branch}:{uuid.uuid4().hex}"
            meta: Dict[str, Any] = {
                "role": msg.role,
                "source_type": msg.source_type,
                "source_id": msg.source_id,
                "workflow": workflow_label,
                "branch": self.current_branch,
            }
            if isinstance(msg.metadata, dict):
                for k in ("node_id", "node_type"):
                    if k in msg.metadata:
                        meta[k] = msg.metadata[k]
            try:
                shared.save(key, body, metadata=meta)
            except Exception as e:
                logger.warning("会话记忆落盘失败: %s", e)

    def _execute_with_app(
        self,
        user_input: str,
        app: Any,
        workflow_label: str,
        *,
        use_loading: bool = True,
        on_graph_progress: Optional[Callable[[List[str]], None]] = None,
    ) -> dict:
        """
        统一执行器：给定 app 后执行任务，负责状态装配、invoke 与上下文回写。

        on_graph_progress：若提供且底层图支持 .stream，则在每个 updates 批次回调
        本批刚写入的节点 node_id 列表（与 LangGraph stream_mode=updates 一致；
        节点耗时的推理过程中可能无回调，直至该节点返回）。
        此时会忽略 use_loading 的旋转条（与 Web 流式进度二选一）。
        """
        # 从当前分支 Context 加载历史消息
        history_messages = []
        if self.context:
            for msg in self.context.load():
                if hasattr(msg, "to_dict"):
                    history_messages.append(msg.to_dict())
                else:
                    history_messages.append(
                        ensure_message(
                            msg,
                            default_role="assistant",
                            default_source_type="system",
                            default_source_id="context",
                        ).to_dict()
                    )

        run_output_dir = create_run_output_dir()
        initial_state = {
            "messages": normalize_messages_for_state(history_messages),
            "current_node": "",
            "input": user_input,
            "output": "",
            "error": None,
            "metadata": {
                "branch": self.current_branch,
                "workflow": workflow_label,
                "timestamp": datetime.now().isoformat(),
                "__run_output_dir__": str(run_output_dir),
            },
            "retrieved_context": "",
        }
        logger.info(f"本轮节点 I/O 将写入: {run_output_dir}")

        def _graph_node_keys_from_update(u: Any) -> List[str]:
            if not isinstance(u, dict):
                return []
            return [
                str(k)
                for k in u
                if isinstance(k, str) and not k.startswith("__")
            ]

        def _invoke() -> dict:
            return app.invoke(initial_state)

        def _invoke_streaming() -> dict:
            stream_fn = getattr(app, "stream", None)
            if stream_fn is None or on_graph_progress is None:
                return _invoke()
            result: Optional[dict] = None
            try:
                for event in stream_fn(
                    initial_state, stream_mode=["updates", "values"]
                ):
                    pairs = []
                    if isinstance(event, tuple) and len(event) == 2:
                        pairs = [(event[0], event[1])]
                    elif isinstance(event, dict):
                        pairs = list(event.items())
                    for mode, payload in pairs:
                        if mode == "values" and isinstance(payload, dict):
                            result = payload
                        elif (
                            mode == "updates"
                            and isinstance(payload, dict)
                            and on_graph_progress
                        ):
                            ids = _graph_node_keys_from_update(payload)
                            if ids:
                                on_graph_progress(ids)
            except TypeError:
                try:
                    for payload in stream_fn(initial_state, stream_mode="values"):
                        if isinstance(payload, dict):
                            result = payload
                except Exception as ex:  # noqa: BLE001
                    logger.warning("graph.stream(values) 不可用，回退 invoke: %s", ex)
                    return _invoke()
            except Exception as ex:  # noqa: BLE001
                logger.warning("graph.stream 失败，回退 invoke: %s", ex)
                return _invoke()
            if not isinstance(result, dict):
                return _invoke()
            return result

        if on_graph_progress is not None:
            result = _invoke_streaming()
        elif use_loading:
            result = run_with_loading(_invoke, message="🤖 LLM 生成中", style="braille")
        else:
            result = _invoke()

        # 执行后回写消息到 Context（仅追加本轮新增消息，避免重复写入历史）
        if result and "messages" in result:
            existed_count = len(history_messages)
            new_messages = result["messages"][existed_count:]
            for msg_dict in new_messages:
                msg = ensure_message(
                    msg_dict,
                    default_role="assistant",
                    default_source_type="system",
                    default_source_id="workflow",
                )
                self.context.save(msg)
            self._persist_new_messages_to_shared_memory_store(new_messages, workflow_label)

        return result
    
    # core/agent_cli.py - 修复 run_task 方法

    def run_task(
        self,
        user_input: str,
        branch: str = None,
        workflow_name: str = None,
        *,
        use_loading: bool = True,
    ) -> dict:
        """执行任务。use_loading=False 时不在终端显示旋转动画（供 Web/API 使用）。"""
        target_branch = branch or self.current_branch
        
        if target_branch != self.current_branch:
            self.switch_branch(target_branch)
        
        context_size = len(self.context) if self.context else 0
        workflow_label = workflow_name or self.DEFAULT_WORKFLOW
        print(f"\n🔄 执行任务 [分支: {self.current_branch} | 工作流: {workflow_label}] (对话: {context_size}条)")

        try:
            app = self._build_app_for_workflow(workflow_name)
        except Exception as e:
            err = f"加载工作流失败: {e}"
            logger.error(err)
            return {
                "messages": [],
                "current_node": "",
                "input": user_input,
                "output": "",
                "error": err,
                "metadata": {"branch": self.current_branch, "workflow": workflow_label},
                "retrieved_context": "",
            }

        return self._execute_with_app(
            user_input, app, workflow_label, use_loading=use_loading
        )

    def build_plan_graph_and_app(
        self, user_input: str, branch: Optional[str] = None
    ) -> Tuple[List[Any], List[Any], Any]:
        """
        仅完成规划与构图，不执行 invoke。
        供 Web 在流式响应中先发 plan_graph，再单独调用 _execute_with_app。
        """
        target_branch = branch or self.current_branch
        if target_branch != self.current_branch:
            self.switch_branch(target_branch)

        from router.planner import AutoAgentsMASPlanner
        from workflow.workflow_parser import YAMLWorkflowParser
        from config.planner_config import MAX_PLAN_ROUNDS_DEFAULT

        print("\n🧠 [1/4] 初始化规划器...")
        planner = AutoAgentsMASPlanner(max_plan_rounds=MAX_PLAN_ROUNDS_DEFAULT)
        parser = YAMLWorkflowParser()

        print("   [2/4] PlanAgent + Supervisor 规划中（需 10~30 秒）...")
        plan = planner.decompose(user_input)

        print("   [3/4] 为各节点分配 Agent 类型...")
        plan = planner.assign(plan, [])

        nodes, edges = parser.from_task_plan(plan)
        print(f"   规划完成：{len(nodes)} 个专家节点，{len(edges)} 条边")
        for n in nodes:
            print(f"      - [{n.agent_name}] {n.node_id}")

        print("   [4/4] 构建动态图（即将执行）...")
        app = parser.build_graph(
            nodes,
            edges,
            context_manager=self.context,
            persona_memory=self.persona_memory,
            runtime_memory=self.context,
            human_input_provider=self._human_input_provider,
        )
        return nodes, edges, app

    def run_plan_task(
        self, user_input: str, branch: str = None, *, use_loading: bool = True
    ) -> dict:
        """
        统一的 plan 任务入口：
        规划 -> 解析图 -> 构图 -> 复用统一执行器 _execute_with_app。
        """
        nodes, edges, app = self.build_plan_graph_and_app(user_input, branch)
        result = self._execute_with_app(
            user_input, app, workflow_label="plan_dynamic", use_loading=use_loading
        )

        try:
            result.setdefault("metadata", {})["__plan_graph__"] = _serialize_plan_graph_for_ui(
                nodes, edges
            )
        except Exception as ex:  # noqa: BLE001
            logger.warning("[run_plan_task] 无法序列化规划图供 UI：%s", ex)

        if result.get("error") is None:
            node_ids = [n.node_id for n in nodes]
            hit = [nid for nid in node_ids if nid in result.get("metadata", {})]
            print(f"\n   节点结构化输出已写入 metadata：{hit}")

        return result
    
    def switch_branch(self, branch_name: str) -> bool:
        """切换分支；未知分支时返回 False。"""
        if branch_name == self.current_branch:
            print(f"✅ 已经在分支 '{branch_name}'")
            return True

        sh = self.memory_system.get("shared")
        if self.use_branch and sh is not None and hasattr(sh, "list_branches"):
            if branch_name not in sh.list_branches():
                print(f"❌ 无此分支: {branch_name!r}")
                return False

        old_branch = self.current_branch
        self.current_branch = branch_name
        for memory in self.memory_system.values():
            if getattr(memory, "branch_enabled", False) and hasattr(memory, "switch_branch"):
                ok = memory.switch_branch(branch_name)
                if not ok:
                    logger.warning(
                        "记忆系统未能切换到分支 %r（若为新分支请先创建）",
                        branch_name,
                    )
        self._rebuild_workflow()

        print(f"✅ 从 '{old_branch}' 切换到 '{branch_name}'")
        print(f"   📝 对话历史: {len(self.context)} 条")
        return True

    def create_branch(self, branch_name: str, from_branch: str = "main") -> bool:
        """
        创建分支；各记忆模块须全部成功才复制上下文。名称已存在或 from 非法时返回 False。
        """
        if not str(branch_name or "").strip() or str(branch_name).strip() == "main":
            return False
        branch_name = str(branch_name).strip()
        from_b = str(from_branch or "main").strip() or "main"
        flags: List[bool] = []
        for memory in self.memory_system.values():
            if hasattr(memory, "create_branch"):
                flags.append(bool(memory.create_branch(branch_name, from_b)))
        if not flags or not all(flags):
            return False

        if from_b in self.contexts:
            from_ctx = self.contexts[from_b]
            new_ctx = ContextManager(max_messages=200, default_limit=20)
            for msg in from_ctx.load():
                new_ctx.save(msg)
            self.contexts[branch_name] = new_ctx
        else:
            self.contexts[branch_name] = ContextManager(max_messages=200, default_limit=20)

        print(f"✅ 创建分支: {branch_name} (基于 {from_b})")
        return True

    def get_branch_tree_for_api(self) -> Dict[str, Any]:
        """
        供 Web：当前活动分支、树节点 id/parent/记忆条数/对话条数。
        """
        shared = self.memory_system.get("shared")
        if not self.use_branch or not shared or not getattr(shared, "branch_enabled", False):
            ctx = self.contexts.get(self.current_branch) or self.context
            msg_n = len(ctx) if ctx is not None else 0
            return {
                "current": self.current_branch,
                "nodes": [
                    {
                        "id": "main",
                        "parent": None,
                        "size": 0,
                        "messages": msg_n,
                    }
                ],
            }
        info = shared.get_branch_info()
        details = info.get("branch_details") or {}
        names: List[str] = list(
            (info.get("branches") or list(details.keys()) or ["main"])
        )
        if "main" in names:
            names.remove("main")
            names = ["main"] + sorted(names)
        else:
            names = sorted(names)
        out: List[Dict[str, Any]] = []
        for name in names:
            d = details.get(name) or {}
            ctx = self.contexts.get(name)
            msg_n = len(ctx) if ctx is not None else 0
            p = d.get("parent")
            if name == "main":
                p = None
            out.append(
                {
                    "id": name,
                    "parent": p,
                    "size": int(d.get("size", 0) or 0),
                    "messages": msg_n,
                }
            )
        return {
            "current": self.current_branch,
            "nodes": out,
        }
    
    def merge_branch(self, branch_name: str):
        """合并分支"""
        if branch_name == "main":
            print("❌ 不能合并主分支")
            return
        
        results = {}
        for name, memory in self.memory_system.items():
            if hasattr(memory, 'merge_to_main'):
                results[name] = memory.merge_to_main(branch_name)
        
        merged_total = sum(r.get('merged_count', 0) for r in results.values())
        print(f"✅ 分支 {branch_name} 已合并，共 {merged_total} 条记忆")
        
        if self.current_branch == branch_name:
            self.switch_branch("main")
    
    def list_branches(self):
        """列出分支"""
        shared_mem = self.memory_system.get("shared")
        if hasattr(shared_mem, 'list_branches'):
            branches = shared_mem.list_branches()
            print(f"\n📋 分支列表:")
            for branch in branches:
                ctx_size = len(self.contexts.get(branch, ContextManager()))
                marker = "▶️" if branch == self.current_branch else "  "
                print(f"  {marker} {branch} - {ctx_size} 条对话")
            print()
    
    def show_status(self):
        """显示状态"""
        print(display.banner("系统状态", width=50))
        print(f"\n🌿 当前分支: {self.current_branch}")
        print(f"   对话历史: {len(self.context)} 条")
        
        print(f"\n📚 记忆统计:")
        for name, memory in self.memory_system.items():
            print(f"   {name}: {memory.get_size()} 条")
        print(f"   用户画像文件: {self.persona_memory.path}")
        print()
    
    def clear_all(self):
        """清空所有"""
        for memory in self.memory_system.values():
            memory.clear()
        self.persona_memory.reset_to_default()
        for ctx in self.contexts.values():
            ctx.clear()
        print("✅ 已清空所有记忆、用户画像与对话")
    
    def show_branch_status(self):
        """显示分支状态"""
        shared_mem = self.memory_system.get("shared")
        if hasattr(shared_mem, 'get_branch_info'):
            info = shared_mem.get_branch_info()
            print(f"\n📊 分支系统状态:")
            print(f"   启用: {info.get('enabled')}")
            print(f"   当前: {info.get('current')}")
            print(f"   分支: {', '.join(info.get('branches', []))}")
            if info.get('branch_details'):
                print(f"\n   分支详情:")
                for name, details in info.get('branch_details', {}).items():
                    print(f"     📁 {name}: {details.get('size', 0)} 条记忆")
            print()
    
    def process_input(self, input_line: str) -> bool:
        """处理用户输入"""
        return self.command_registry.execute(input_line, self)