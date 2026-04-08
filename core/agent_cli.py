# core/agent_cli.py
"""
TeX Agent CLI 核心类
"""
from typing import Dict, Optional
from datetime import datetime

from utils.logger import get_logger
from utils.loading_spinner import run_with_loading
from utils.display import display
from workflow.graph_builder import build_graph
from context.context_manager import ContextManager
from memory.factory import MemoryFactory
from cli.commands import CommandRegistry
from cli.branch_commands import BRANCH_COMMANDS, BRANCH_ALIASES
from cli.task_commands import get_task_commands

logger = get_logger(__name__)


class TeXAgentCLI:
    """TeX Agent CLI 核心类"""
    
    def __init__(self, use_branch: bool = True):
        self.use_branch = use_branch
        self.current_branch = "main"
        
        # 每个分支独立的上下文
        self.contexts: Dict[str, ContextManager] = {}
        self.memory_system = self._init_memory_system()
        self.context = None
        self.app = None
        
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
        """重建工作流"""
        self.context = self._get_context(self.current_branch)
        self.app = build_graph(
            context_manager=self.context,
            design_memory=self.memory_system.get("design"),
            think_memory=self.memory_system.get("think"),
            execute_memory=self.memory_system.get("execute"),
            shared_memory=self.memory_system.get("shared"),
        )
        logger.info(f"已为分支 '{self.current_branch}' 重建工作流")
    
    # core/agent_cli.py - 修复 run_task 方法

    def run_task(self, user_input: str, branch: str = None) -> dict:
        """执行任务（带加载动画）"""
        target_branch = branch or self.current_branch
        
        if target_branch != self.current_branch:
            self.switch_branch(target_branch)
        
        context_size = len(self.context) if self.context else 0
        print(f"\n🔄 执行任务 [分支: {self.current_branch}] (对话: {context_size}条)")
        
        # 🔧 关键修复：从当前分支的 Context 加载历史消息
        history_messages = []
        if self.context:
            # 将 Context 中的历史消息转换为字典格式
            for msg in self.context.load():
                if hasattr(msg, 'to_dict'):
                    history_messages.append(msg.to_dict())
                else:
                    history_messages.append({
                        "role": getattr(msg, 'role', 'assistant'),
                        "content": getattr(msg, 'content', ''),
                        "agent_name": getattr(msg, 'agent_name', 'system')
                    })
        
        initial_state = {
            "messages": history_messages,  # 🔧 使用历史消息，而不是空列表
            "current_node": "",
            "input": user_input,
            "output": "",
            "error": None,
            "metadata": {"branch": self.current_branch, "timestamp": datetime.now().isoformat()},
            "retrieved_context": "",
        }
        
        def _invoke():
            return self.app.invoke(initial_state)
        
        result = run_with_loading(_invoke, message="🤖 LLM 生成中", style="braille")
        
        # 🔧 执行完成后，将新消息保存到 Context
        if result and 'messages' in result:
            for msg_dict in result['messages']:
                # 转换为 AgentMessage 并保存
                from core.message import AgentMessage
                msg = AgentMessage(
                    role=msg_dict.get('role', 'assistant'),
                    content=msg_dict.get('content', ''),
                    agent_name=msg_dict.get('agent_name', 'system')
                )
                self.context.save(msg)
        
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
        print()
    
    def clear_all(self):
        """清空所有"""
        for memory in self.memory_system.values():
            memory.clear()
        for ctx in self.contexts.values():
            ctx.clear()
        print("✅ 已清空所有记忆和对话")
    
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