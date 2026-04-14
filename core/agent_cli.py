# core/agent_cli.py
"""
TeX Agent CLI 核心类
"""
from typing import Any, Dict, Optional
from datetime import datetime

from utils.logger import get_logger
from utils.loading_spinner import run_with_loading
from utils.display import display
from workflow.graph_builder import build_app_from_workflow
from workflow.run_dump import create_run_output_dir
from context.context_manager import ContextManager
from memory.factory import MemoryFactory
from memory.persona_memory import UserPersonaMemory
from cli.commands import CommandRegistry
from cli.branch_commands import BRANCH_COMMANDS
from cli.task_commands import get_task_commands

logger = get_logger(__name__)


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
        self.persona_memory = UserPersonaMemory()
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
                "shared": MemoryFactory.create_memory("shared"),
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
        return build_app_from_workflow(
            workflow_name=target_name,
            context_manager=self.context,
            persona_memory=self.persona_memory,
        )

    def _execute_with_app(self, user_input: str, app: Any, workflow_label: str) -> dict:
        """
        统一执行器：给定 app 后执行任务，负责状态装配、invoke 与上下文回写。
        """
        # 从当前分支 Context 加载历史消息
        history_messages = []
        if self.context:
            for msg in self.context.load():
                if hasattr(msg, "to_dict"):
                    history_messages.append(msg.to_dict())
                else:
                    history_messages.append({
                        "role": getattr(msg, "role", "assistant"),
                        "content": getattr(msg, "content", ""),
                        "agent_name": getattr(msg, "agent_name", "system")
                    })

        run_output_dir = create_run_output_dir()
        initial_state = {
            "messages": history_messages,
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

        def _invoke():
            return app.invoke(initial_state)

        result = run_with_loading(_invoke, message="🤖 LLM 生成中", style="braille")

        # 执行后回写消息到 Context（仅追加本轮新增消息，避免重复写入历史）
        if result and "messages" in result:
            from core.message import AgentMessage
            existed_count = len(history_messages)
            new_messages = result["messages"][existed_count:]
            for msg_dict in new_messages:
                msg = AgentMessage(
                    role=msg_dict.get("role", "assistant"),
                    content=msg_dict.get("content", ""),
                    agent_name=msg_dict.get("agent_name", "system")
                )
                self.context.save(msg)

        return result
    
    # core/agent_cli.py - 修复 run_task 方法

    def run_task(self, user_input: str, branch: str = None, workflow_name: str = None) -> dict:
        """执行任务（带加载动画）"""
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

        return self._execute_with_app(user_input, app, workflow_label)

    def run_plan_task(self, user_input: str, branch: str = None) -> dict:
        """
        统一的 plan 任务入口：
        规划 -> 解析图 -> 构图 -> 复用统一执行器 _execute_with_app。
        """
        target_branch = branch or self.current_branch
        if target_branch != self.current_branch:
            self.switch_branch(target_branch)

        from router.planner import AutoAgentsMASPlanner
        from workflow.workflow_parser import YAMLWorkflowParser

        print("\n🧠 [1/4] 初始化规划器...")
        planner = AutoAgentsMASPlanner(max_plan_rounds=2)
        parser = YAMLWorkflowParser()

        print("   [2/4] PlanAgent + Supervisor 规划中（需 10~30 秒）...")
        plan = planner.decompose(user_input)

        print("   [3/4] 为各节点分配 Agent 类型...")
        plan = planner.assign(plan, [])

        nodes, edges = parser.from_task_plan(plan)
        print(f"   规划完成：{len(nodes)} 个专家节点，{len(edges)} 条边")
        for n in nodes:
            print(f"      - [{n.agent_name}] {n.node_id}")

        print("   [4/4] 构建并运行动态图...")
        app = parser.build_graph(nodes, edges, persona_memory=self.persona_memory)
        result = self._execute_with_app(user_input, app, workflow_label="plan_dynamic")

        if result.get("error") is None:
            node_ids = [n.node_id for n in nodes]
            hit = [nid for nid in node_ids if nid in result.get("metadata", {})]
            print(f"\n   节点结构化输出已写入 metadata：{hit}")

        return result
    
    def switch_branch(self, branch_name: str):
        """切换分支"""
        if branch_name == self.current_branch:
            print(f"✅ 已经在分支 '{branch_name}'")
            return
        
        old_branch = self.current_branch
        self.current_branch = branch_name
        self._rebuild_workflow()
        
        print(f"✅ 从 '{old_branch}' 切换到 '{branch_name}'")
        print(f"   📝 对话历史: {len(self.context)} 条")
    
    def create_branch(self, branch_name: str, from_branch: str = "main"):
        """创建分支"""
        for memory in self.memory_system.values():
            if hasattr(memory, 'create_branch'):
                memory.create_branch(branch_name, from_branch)
        
        # 复制上下文
        if from_branch in self.contexts:
            from_ctx = self.contexts[from_branch]
            new_ctx = ContextManager(max_messages=200, default_limit=20)
            for msg in from_ctx.load():
                new_ctx.save(msg)
            self.contexts[branch_name] = new_ctx
        else:
            self.contexts[branch_name] = ContextManager(max_messages=200, default_limit=20)
        
        print(f"✅ 创建分支: {branch_name} (基于 {from_branch})")
    
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