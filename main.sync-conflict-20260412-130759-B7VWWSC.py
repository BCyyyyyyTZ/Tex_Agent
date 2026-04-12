# # # main.py
# # """
# # TeX_Agent 程序主入口 - 增强版
# # 支持分支管理、异步执行、交互式命令行
# # """
# # import sys
# # import asyncio
# # import threading
# # from typing import Optional
# # from datetime import datetime

# # from utils.logger import get_logger
# # from workflow.graph_builder import build_graph
# # from core.state import WorkflowState
# # from context.context_manager import ContextManager
# # from memory.factory import MemoryFactory
# # from typing import Dict
# # logger = get_logger(__name__)

# # # MVP 示例任务
# # DEFAULT_TASK = (
# #     "请帮我检索关于 large language model 的最新论文，"
# #     "分析研究现状，并给出 Related Work 章节的写作框架建议。"
# # )


# # """TeX Agent 命令行交互界面"""
# # class TeXAgentCLI:
# #     def __init__(self, use_branch: bool = True):
# #         self.use_branch = use_branch
# #         # 使用字典存储每个分支的独立 Context
# #         self.contexts: Dict[str, ContextManager] = {}
# #         self.current_branch = "main"
# #         self.memory_system = self._init_memory_system()
# #         self.app = None
# #         self._build_workflow()
    
# #     def _get_context(self, branch: str = None) -> ContextManager:
# #         """获取指定分支的 Context，不存在则创建"""
# #         branch_name = branch or self.current_branch
        
# #         if branch_name not in self.contexts:
# #             self.contexts[branch_name] = ContextManager(max_messages=200, default_limit=20)
# #             logger.info(f"为分支 '{branch_name}' 创建新的上下文")
        
# #         return self.contexts[branch_name]
    
# #     def _switch_branch(self, branch_name: str):
# #         """切换分支"""
# #         if not self.use_branch:
# #             print("⚠️  分支功能未启用")
# #             return
        
# #         # 切换记忆分支
# #         for name, memory in self.memory_system.items():
# #             if hasattr(memory, 'switch_branch'):
# #                 memory.switch_branch(branch_name)
        
# #         # 切换当前分支
# #         self.current_branch = branch_name
        
# #         # 🔧 关键：重新构建工作流，使用新分支的 Context
# #         self._rebuild_workflow()
        
# #         print(f"✅ 已切换到分支: {branch_name}")
    
# #     def _rebuild_workflow(self):
# #         """使用当前分支的 Context 重新构建工作流"""
# #         current_ctx = self._get_context(self.current_branch)
        
# #         self.app = build_graph(
# #             context_manager=current_ctx,
# #             design_memory=self.memory_system.get("design"),
# #             think_memory=self.memory_system.get("think"),
# #             execute_memory=self.memory_system.get("execute"),
# #             shared_memory=self.memory_system.get("shared"),
# #         )
# #         logger.info(f"已为分支 '{self.current_branch}' 重建工作流")
        
# #     def _init_memory_system(self):
# #         """初始化记忆系统"""
# #         if self.use_branch:
# #             return {
# #                 "design": MemoryFactory.create_private_memory("design", branch_enabled=True),
# #                 "think": MemoryFactory.create_private_memory("think", branch_enabled=True),
# #                 "execute": MemoryFactory.create_private_memory("execute", branch_enabled=True),
# #                 "shared": MemoryFactory.create_shared_memory(branch_enabled=True),
# #             }
# #         else:
# #             return {
# #                 "design": MemoryFactory.create_memory("private", "design"),
# #                 "think": MemoryFactory.create_memory("private", "think"),
# #                 "execute": MemoryFactory.create_memory("private", "execute"),
# #                 "shared": MemoryFactory.create_memory("shared"),
# #             }
    
# #     def _build_workflow(self):
# #         """构建工作流"""
# #         self.app = build_graph(
# #             context_manager=self.context,
# #             design_memory=self.memory_system.get("design"),
# #             think_memory=self.memory_system.get("think"),
# #             execute_memory=self.memory_system.get("execute"),
# #             shared_memory=self.memory_system.get("shared"),
# #         )
# #         logger.info("工作流构建完成")
    
# #     def run_task(self, user_input: str, branch: str = None) -> dict:
# #         """
# #         执行任务（同步版本，带进度提示）
# #         """
# #         # 切换分支
# #         if branch and self.use_branch:
# #             self._switch_branch(branch)
        
# #         # 显示当前分支信息
# #         current_branch = self._get_current_branch()
# #         print(f"\n🔄 正在执行任务 [分支: {current_branch}]...")
# #         print("   (这可能需要 30-60 秒，请耐心等待...)\n")
        
# #         initial_state: WorkflowState = {
# #             "messages": [],
# #             "current_node": "",
# #             "input": user_input,
# #             "output": "",
# #             "error": None,
# #             "metadata": {"branch": current_branch, "timestamp": datetime.now().isoformat()},
# #             "retrieved_context": "",
# #         }
        
# #         try:
# #             result = self.app.invoke(initial_state)
# #             return result
# #         except Exception as e:
# #             logger.error(f"工作流执行失败: {e}")
# #             return {"output": f"执行失败: {e}", "error": str(e)}
    
# #     def _get_current_branch(self) -> str:
# #         """获取当前分支"""
# #         if not self.use_branch:
# #             return "main"
# #         shared_mem = self.memory_system.get("shared")
# #         if hasattr(shared_mem, 'current_branch'):
# #             return shared_mem.current_branch
# #         return "main"
    
# #     def _switch_branch(self, branch_name: str):
# #         """切换所有记忆的分支"""
# #         if not self.use_branch:
# #             print("⚠️  分支功能未启用")
# #             return
        
# #         for name, memory in self.memory_system.items():
# #             if hasattr(memory, 'switch_branch'):
# #                 memory.switch_branch(branch_name)
# #         print(f"✅ 已切换到分支: {branch_name}")
    
# #     def create_branch(self, branch_name: str, from_branch: str = "main"):
# #         """创建新分支"""
# #         if not self.use_branch:
# #             print("⚠️  分支功能未启用")
# #             return
        
# #         for name, memory in self.memory_system.items():
# #             if hasattr(memory, 'create_branch'):
# #                 memory.create_branch(branch_name, from_branch)
# #         print(f"✅ 创建分支: {branch_name} (基于 {from_branch})")
    
# #     def merge_branch(self, branch_name: str):
# #         """合并分支到主分支"""
# #         if not self.use_branch:
# #             print("⚠️  分支功能未启用")
# #             return
        
# #         results = {}
# #         for name, memory in self.memory_system.items():
# #             if hasattr(memory, 'merge_to_main'):
# #                 results[name] = memory.merge_to_main(branch_name)
        
# #         merged_total = sum(r.get('merged_count', 0) for r in results.values())
# #         print(f"✅ 分支 {branch_name} 已合并，共合并 {merged_total} 条记忆")
# #         return results
    
# #     def list_branches(self):
# #         """列出所有分支"""
# #         if not self.use_branch:
# #             print("⚠️  分支功能未启用")
# #             return
        
# #         shared_mem = self.memory_system.get("shared")
# #         if hasattr(shared_mem, 'list_branches'):
# #             branches = shared_mem.list_branches()
# #             current = self._get_current_branch()
            
# #             print(f"\n📋 可用分支:")
# #             for branch in branches:
# #                 if branch == current:
# #                     print(f"  ▶️  {branch} (当前)")
# #                 else:
# #                     print(f"     {branch}")
# #             print()
    
# #     def show_status(self):
# #         """显示系统状态"""
# #         print("\n" + "=" * 50)
# #         print("系统状态")
# #         print("=" * 50)
        
# #         # 分支信息
# #         if self.use_branch:
# #             print(f"\n🌿 当前分支: {self._get_current_branch()}")
# #             shared_mem = self.memory_system.get("shared")
# #             if hasattr(shared_mem, 'list_branches'):
# #                 branches = shared_mem.list_branches()
# #                 print(f"   可用分支: {', '.join(branches)}")
        
# #         # 记忆统计
# #         print(f"\n📚 记忆统计:")
# #         for name, memory in self.memory_system.items():
# #             size = memory.get_size()
# #             print(f"   {name}: {size} 条")
        
# #         # 上下文统计
# #         print(f"\n💬 上下文消息: {len(self.context)} 条")
# #         print("=" * 50 + "\n")
    
# #     def clear_memories(self):
# #         """清空所有记忆"""
# #         for memory in self.memory_system.values():
# #             memory.clear()
# #         print("✅ 已清空所有记忆")


# # def print_banner():
# #     """打印欢迎横幅"""
# #     print("\n" + "=" * 70)
# #     print("  TeX_Agent — LaTeX 论文写作增强系统")
# #     print("  基于 LangGraph 多智能体架构 + 分支记忆")
# #     print("=" * 70)
# #     print("\n💡 提示: LLM 响应需要 30-60 秒，请耐心等待")
# #     print("💡 输入 'help' 查看所有命令\n")


# # def print_help():
# #     """打印帮助信息"""
# #     print("""
# # ╔══════════════════════════════════════════════════════════════════
# # ║                        可用命令                                   
# # ╠══════════════════════════════════════════════════════════════════
# # ║  task <Prompt>          - 执行论文写作任务                                
# # ║  branch list            - 列出所有分支                                  
# # ║  branch create <name>   - 创建新分支                               
# # ║  branch switch <name>   - 切换分支                                 
# # ║  branch merge  <name>   - 合并分支到主分支                        
# # ║  status                 - 显示系统状态                                  
# # ║  clear                  - 清空所有记忆                                  
# # ║  help                   - 显示此帮助                                    
# # ║  exit, quit             - 退出程序                                      
# # ╚══════════════════════════════════════════════════════════════════
# #     """)


# # def main():
# #     """主函数 - 交互式命令行"""
# #     print_banner()
    
# #     # 初始化 CLI
# #     cli = TeXAgentCLI(use_branch=True)
    
# #     # 显示初始状态
# #     cli.show_status()
# #     print_help()
    
# #     # 交互式循环
# #     while True:
# #         try:
# #             # 获取用户输入
# #             user_input = input("\n📝 > ").strip()
            
# #             if not user_input:
# #                 continue
            
# #             # 处理命令
# #             if user_input.lower() in ['exit', 'quit', 'q']:
# #                 print("\n👋 再见！")
# #                 break
            
# #             elif user_input.lower() == 'help':
# #                 print_help()
            
# #             elif user_input.lower() == 'status':
# #                 cli.show_status()
            
# #             elif user_input.lower() == 'clear':
# #                 cli.clear_memories()
            
# #             elif user_input.lower() == 'branch list':
# #                 cli.list_branches()
            
# #             elif user_input.lower().startswith('branch create'):
# #                 parts = user_input.split()
# #                 if len(parts) >= 3:
# #                     branch_name = parts[2]
# #                     from_branch = parts[3] if len(parts) > 3 else "main"
# #                     cli.create_branch(branch_name, from_branch)
# #                 else:
# #                     print("❌ 用法: branch create <分支名> [源分支]")
            
# #             elif user_input.lower().startswith('branch switch'):
# #                 parts = user_input.split()
# #                 if len(parts) >= 3:
# #                     branch_name = parts[2]
# #                     cli._switch_branch(branch_name)
# #                 else:
# #                     print("❌ 用法: branch switch <分支名>")
            
# #             elif user_input.lower().startswith('branch merge'):
# #                 parts = user_input.split()
# #                 if len(parts) >= 3:
# #                     branch_name = parts[2]
# #                     cli.merge_branch(branch_name)
# #                 else:
# #                     print("❌ 用法: branch merge <分支名>")
            
# #             elif user_input.lower().startswith('task'):
# #                 # 提取任务描述
# #                 task = user_input[4:].strip()
# #                 if not task:
# #                     print("❌ 请提供任务描述")
# #                     print("   示例: task 请帮我写一篇关于 Transformer 的论文引言")
# #                     continue
                
# #                 # 执行任务（带进度提示）
# #                 print("\n" + "─" * 70)
# #                 result = cli.run_task(task)
# #                 print("─" * 70)
                
# #                 # 显示结果
# #                 if result.get("error"):
# #                     print(f"\n❌ 执行失败: {result['error']}")
# #                 else:
# #                     output = result.get("output", "")
# #                     if output:
# #                         # 限制输出长度
# #                         if len(output) > 1000:
# #                             print(f"\n📄 输出 (前1000字符):\n{output[:1000]}...")
# #                             print(f"\n💡 完整输出已保存，共 {len(output)} 字符")
# #                         else:
# #                             print(f"\n📄 输出:\n{output}")
# #                     else:
# #                         print("\n⚠️  未生成输出")
                
# #                 print("\n" + "─" * 70)
            
# #             else:
# #                 # 如果不是命令，当作任务处理
# #                 print("\n💡 提示: 直接输入文本会被当作任务执行")
# #                 print("   也可以使用 'task <描述>' 命令")
# #                 confirm = input("   是否执行此任务？(y/n): ").strip().lower()
# #                 if confirm == 'y':
# #                     print("\n" + "─" * 70)
# #                     result = cli.run_task(user_input)
# #                     print("─" * 70)
                    
# #                     output = result.get("output", "")
# #                     if output:
# #                         if len(output) > 1000:
# #                             print(f"\n📄 输出 (前1000字符):\n{output[:1000]}...")
# #                         else:
# #                             print(f"\n📄 输出:\n{output}")
# #                     print("\n" + "─" * 70)
        
# #         except KeyboardInterrupt:
# #             print("\n\n⚠️  使用 'exit' 退出程序")
# #             continue
# #         except EOFError:
# #             print("\n\n👋 再见！")
# #             break
# #         except Exception as e:
# #             print(f"\n❌ 错误: {e}")
# #             logger.error(f"Unexpected error: {e}", exc_info=True)


# # def quick_run():
# #     """快速运行模式 - 命令行直接传入任务"""
# #     if len(sys.argv) > 1:
# #         user_input = " ".join(sys.argv[1:]).strip()
# #         print(f"\n[快速模式] 执行任务: {user_input[:100]}...")
        
# #         cli = TeXAgentCLI(use_branch=True)
# #         result = cli.run_task(user_input)
        
# #         if result.get("error"):
# #             print(f"\n❌ 失败: {result['error']}")
# #         else:
# #             output = result.get("output", "")
# #             print(f"\n📄 结果:\n{output}")
# #     else:
# #         main()


# # if __name__ == "__main__":
# #     # 如果有命令行参数，使用快速模式
# #     if len(sys.argv) > 1:
# #         quick_run()
# #     else:
# #         main()
# # main.py
# """
# TeX_Agent 程序主入口 - 增强版
# 支持分支管理、独立上下文、交互式命令行
# """
# import sys
# import asyncio
# import threading
# from typing import Optional, Dict
# from datetime import datetime

# from utils.logger import get_logger
# from workflow.graph_builder import build_graph
# from core.state import WorkflowState
# from context.context_manager import ContextManager
# from memory.factory import MemoryFactory

# logger = get_logger(__name__)

# # MVP 示例任务
# DEFAULT_TASK = (
#     "请帮我检索关于 large language model 的最新论文，"
#     "分析研究现状，并给出 Related Work 章节的写作框架建议。"
# )


# class TeXAgentCLI:
#     """TeX Agent 命令行交互界面 - 支持分支独立上下文"""
    
#     def __init__(self, use_branch: bool = True):
#         """
#         初始化 CLI
        
#         Args:
#             use_branch: 是否启用分支记忆功能
#         """
#         self.use_branch = use_branch
#         self.current_branch = "main"
        
#         # 每个分支独立的上下文管理器
#         self.contexts: Dict[str, ContextManager] = {}
        
#         # 记忆系统
#         self.memory_system = self._init_memory_system()
        
#         # 当前使用的上下文（快捷引用）
#         self.context = None
        
#         # 工作流实例
#         self.app = None
        
#         # 构建工作流
#         self._rebuild_workflow()
    
#     def _init_memory_system(self):
#         """初始化记忆系统"""
#         if self.use_branch:
#             return {
#                 "design": MemoryFactory.create_private_memory("design", branch_enabled=True),
#                 "think": MemoryFactory.create_private_memory("think", branch_enabled=True),
#                 "execute": MemoryFactory.create_private_memory("execute", branch_enabled=True),
#                 "shared": MemoryFactory.create_shared_memory(branch_enabled=True),
#             }
#         else:
#             return {
#                 "design": MemoryFactory.create_memory("private", "design"),
#                 "think": MemoryFactory.create_memory("private", "think"),
#                 "execute": MemoryFactory.create_memory("private", "execute"),
#                 "shared": MemoryFactory.create_memory("shared"),
#             }
    
#     def _get_context(self, branch: str = None) -> ContextManager:
#         """获取指定分支的 Context，不存在则创建"""
#         branch_name = branch or self.current_branch
        
#         if branch_name not in self.contexts:
#             self.contexts[branch_name] = ContextManager(max_messages=200, default_limit=20)
#             logger.info(f"为分支 '{branch_name}' 创建新的上下文")
        
#         return self.contexts[branch_name]
    
#     def _rebuild_workflow(self):
#         """使用当前分支的 Context 重新构建工作流"""
#         # 获取当前分支的上下文
#         self.context = self._get_context(self.current_branch)
        
#         # 重新构建工作流
#         self.app = build_graph(
#             context_manager=self.context,
#             design_memory=self.memory_system.get("design"),
#             think_memory=self.memory_system.get("think"),
#             execute_memory=self.memory_system.get("execute"),
#             shared_memory=self.memory_system.get("shared"),
#         )
#         logger.info(f"已为分支 '{self.current_branch}' 重建工作流，上下文消息数: {len(self.context)}")
    
#     def run_task(self, user_input: str, branch: str = None) -> dict:
#         """
#         执行任务（同步版本，带进度提示）
#         """
#         target_branch = branch or self.current_branch
        
#         # 如果需要切换分支
#         if target_branch != self.current_branch:
#             self._switch_branch(target_branch)
        
#         # 显示当前分支信息
#         context_size = len(self.context) if self.context else 0
#         print(f"\n🔄 正在执行任务 [分支: {self.current_branch}]...")
#         print(f"   (对话历史: {context_size} 条消息)")
#         print("   (LLM 响应需要 30-60 秒，请耐心等待...)\n")
        
#         initial_state = {
#             "messages": [],
#             "current_node": "",
#             "input": user_input,
#             "output": "",
#             "error": None,
#             "metadata": {"branch": self.current_branch, "timestamp": datetime.now().isoformat()},
#             "retrieved_context": "",
#         }
        
#         try:
#             result = self.app.invoke(initial_state)
#             return result
#         except Exception as e:
#             logger.error(f"工作流执行失败: {e}")
#             return {"output": f"执行失败: {e}", "error": str(e)}
    
#     def _get_current_branch(self) -> str:
#         """获取当前分支"""
#         return self.current_branch
    
#     def _switch_branch(self, branch_name: str):
#         """切换所有记忆的分支"""
#         if not self.use_branch:
#             print("⚠️  分支功能未启用")
#             return
        
#         if branch_name == self.current_branch:
#             print(f"✅ 已经在分支 '{branch_name}'")
#             return
        
#         old_branch = self.current_branch
        
#         # 切换记忆分支
#         for name, memory in self.memory_system.items():
#             if hasattr(memory, 'switch_branch'):
#                 memory.switch_branch(branch_name)
        
#         # 更新当前分支
#         self.current_branch = branch_name
        
#         # 🔧 关键：重新构建工作流，使用新分支的 Context
#         self._rebuild_workflow()
        
#         print(f"✅ 已从分支 '{old_branch}' 切换到 '{branch_name}'")
#         print(f"   📝 对话历史已独立，新分支有 {len(self.context)} 条消息")
        
#         # 显示分支记忆统计
#         total_memories = sum(m.get_size() for m in self.memory_system.values())
#         print(f"   📚 当前分支总记忆数: {total_memories}")
    
#     def create_branch(self, branch_name: str, from_branch: str = "main"):
#         """创建新分支"""
#         if not self.use_branch:
#             print("⚠️  分支功能未启用")
#             return
        
#         # 检查分支是否已存在
#         shared_mem = self.memory_system.get("shared")
#         if hasattr(shared_mem, 'list_branches'):
#             existing = shared_mem.list_branches()
#             if branch_name in existing:
#                 print(f"❌ 分支 '{branch_name}' 已存在")
#                 return
        
#         # 创建记忆分支
#         for name, memory in self.memory_system.items():
#             if hasattr(memory, 'create_branch'):
#                 memory.create_branch(branch_name, from_branch)
        
#         # 创建独立的上下文（从源分支复制或新建）
#         if from_branch in self.contexts:
#             # 复制源分支的上下文（深拷贝）
#             from_context = self.contexts[from_branch]
#             new_context = ContextManager(max_messages=200, default_limit=20)
#             # 复制消息历史
#             for msg in from_context.load():
#                 new_context.save(msg)
#             self.contexts[branch_name] = new_context
#         else:
#             # 创建新上下文
#             self.contexts[branch_name] = ContextManager(max_messages=200, default_limit=20)
        
#         print(f"✅ 创建分支: {branch_name} (基于 {from_branch})")
#         print(f"   📝 上下文已复制，共 {len(self.contexts[branch_name])} 条消息")
    
#     def merge_branch(self, branch_name: str):
#         """合并分支到主分支"""
#         if not self.use_branch:
#             print("⚠️  分支功能未启用")
#             return
        
#         if branch_name == "main":
#             print("❌ 不能合并主分支到自身")
#             return
        
#         # 合并记忆
#         results = {}
#         for name, memory in self.memory_system.items():
#             if hasattr(memory, 'merge_to_main'):
#                 results[name] = memory.merge_to_main(branch_name)
        
#         merged_total = sum(r.get('merged_count', 0) for r in results.values())
        
#         # 合并上下文（可选：将分支的对话历史合并到主分支）
#         if branch_name in self.contexts:
#             branch_context = self.contexts[branch_name]
#             main_context = self.contexts.get("main")
#             if main_context:
#                 for msg in branch_context.load():
#                     main_context.save(msg)
#                 print(f"   📝 已合并 {len(branch_context)} 条对话历史到主分支")
        
#         print(f"✅ 分支 {branch_name} 已合并")
#         print(f"   📚 共合并 {merged_total} 条记忆")
        
#         # 如果当前在合并的分支上，切换到主分支
#         if self.current_branch == branch_name:
#             self._switch_branch("main")
    
#     def list_branches(self):
#         """列出所有分支"""
#         if not self.use_branch:
#             print("⚠️  分支功能未启用")
#             return
        
#         shared_mem = self.memory_system.get("shared")
#         if hasattr(shared_mem, 'list_branches'):
#             branches = shared_mem.list_branches()
            
#             print(f"\n📋 可用分支:")
#             for branch in branches:
#                 if branch == self.current_branch:
#                     # 显示当前分支的上下文信息
#                     ctx_size = len(self.contexts.get(branch, ContextManager()))
#                     print(f"  ▶️  {branch} (当前) - {ctx_size} 条对话")
#                 else:
#                     ctx_size = len(self.contexts.get(branch, ContextManager()))
#                     print(f"     {branch} - {ctx_size} 条对话")
#             print()
    
#     def show_status(self):
#         """显示系统状态"""
#         print("\n" + "=" * 50)
#         print("系统状态")
#         print("=" * 50)
        
#         # 分支信息
#         if self.use_branch:
#             print(f"\n🌿 当前分支: {self.current_branch}")
#             print(f"   对话历史: {len(self.context)} 条消息")
            
#             shared_mem = self.memory_system.get("shared")
#             if hasattr(shared_mem, 'list_branches'):
#                 branches = shared_mem.list_branches()
#                 print(f"   可用分支: {', '.join(branches)}")
        
#         # 记忆统计
#         print(f"\n📚 记忆统计:")
#         for name, memory in self.memory_system.items():
#             size = memory.get_size()
#             print(f"   {name}: {size} 条")
        
#         print("=" * 50 + "\n")
    
#     def clear_memories(self):
#         """清空所有记忆和上下文"""
#         for memory in self.memory_system.values():
#             memory.clear()
#         for ctx in self.contexts.values():
#             ctx.clear()
#         print("✅ 已清空所有记忆和对话历史")


# def print_banner():
#     """打印欢迎横幅"""
#     print("\n" + "=" * 70)
#     print("  TeX_Agent — LaTeX 论文写作增强系统")
#     print("  基于 LangGraph 多智能体架构 + 分支记忆")
#     print("=" * 70)
#     print("\n💡 提示: LLM 响应需要 30-60 秒，请耐心等待")
#     print("💡 每个分支有独立的对话历史，切换分支不会互相干扰")
#     print("💡 输入 'help' 查看所有命令\n")


# def print_help():
#     """打印帮助信息"""
#     print("""
# ╔══════════════════════════════════════════════════════════════════
# ║                        可用命令                                   
# ╠══════════════════════════════════════════════════════════════════
# ║  task <Prompt>          - 执行论文写作任务                                
# ║  branch list            - 列出所有分支                                  
# ║  branch create <name>   - 创建新分支                               
# ║  branch switch <name>   - 切换分支                                 
# ║  branch merge  <name>   - 合并分支到主分支                        
# ║  status                 - 显示系统状态                                  
# ║  clear                  - 清空所有记忆                                  
# ║  help                   - 显示此帮助                                    
# ║  exit, quit             - 退出程序                                      
# ╚══════════════════════════════════════════════════════════════════
#     """)


# def main():
#     """主函数 - 交互式命令行"""
#     print_banner()
    
#     # 初始化 CLI
#     cli = TeXAgentCLI(use_branch=True)
    
#     # 显示初始状态
#     cli.show_status()
#     print_help()
    
#     # 交互式循环
#     while True:
#         try:
#             # 获取用户输入
#             user_input = input("\n📝 > ").strip()
            
#             if not user_input:
#                 continue
            
#             # 处理命令
#             if user_input.lower() in ['exit', 'quit', 'q']:
#                 print("\n👋 再见！")
#                 break
            
#             elif user_input.lower() == 'help':
#                 print_help()
            
#             elif user_input.lower() == 'status':
#                 cli.show_status()
            
#             elif user_input.lower() == 'clear':
#                 cli.clear_memories()
            
#             elif user_input.lower() == 'branch list':
#                 cli.list_branches()
            
#             elif user_input.lower().startswith('branch create'):
#                 parts = user_input.split()
#                 if len(parts) >= 3:
#                     branch_name = parts[2]
#                     from_branch = parts[3] if len(parts) > 3 else "main"
#                     cli.create_branch(branch_name, from_branch)
#                 else:
#                     print("❌ 用法: branch create <分支名> [源分支]")
            
#             elif user_input.lower().startswith('branch switch'):
#                 parts = user_input.split()
#                 if len(parts) >= 3:
#                     branch_name = parts[2]
#                     cli._switch_branch(branch_name)
#                 else:
#                     print("❌ 用法: branch switch <分支名>")
            
#             elif user_input.lower().startswith('branch merge'):
#                 parts = user_input.split()
#                 if len(parts) >= 3:
#                     branch_name = parts[2]
#                     cli.merge_branch(branch_name)
#                 else:
#                     print("❌ 用法: branch merge <分支名>")
            
#             elif user_input.lower().startswith('task'):
#                 # 提取任务描述
#                 task = user_input[4:].strip()
#                 if not task:
#                     print("❌ 请提供任务描述")
#                     print("   示例: task 请帮我写一篇关于 Transformer 的论文引言")
#                     continue
                
#                 # 执行任务
#                 print("\n" + "─" * 70)
#                 result = cli.run_task(task)
#                 print("─" * 70)
                
#                 # 显示结果
#                 if result.get("error"):
#                     print(f"\n❌ 执行失败: {result['error']}")
#                 else:
#                     output = result.get("output", "")
#                     if output:
#                         if len(output) > 1000:
#                             print(f"\n📄 输出 (前1000字符):\n{output[:1000]}...")
#                             print(f"\n💡 完整输出共 {len(output)} 字符")
#                         else:
#                             print(f"\n📄 输出:\n{output}")
#                     else:
#                         print("\n⚠️  未生成输出")
                
#                 print("\n" + "─" * 70)
            
#             else:
#                 # 如果不是命令，当作任务处理
#                 print("\n💡 提示: 直接输入文本会被当作任务执行")
#                 print("   也可以使用 'task <描述>' 命令")
#                 confirm = input("   是否执行此任务？(y/n): ").strip().lower()
#                 if confirm == 'y':
#                     print("\n" + "─" * 70)
#                     result = cli.run_task(user_input)
#                     print("─" * 70)
                    
#                     output = result.get("output", "")
#                     if output:
#                         if len(output) > 1000:
#                             print(f"\n📄 输出 (前1000字符):\n{output[:1000]}...")
#                         else:
#                             print(f"\n📄 输出:\n{output}")
#                     print("\n" + "─" * 70)
        
#         except KeyboardInterrupt:
#             print("\n\n⚠️  使用 'exit' 退出程序")
#             continue
#         except EOFError:
#             print("\n\n👋 再见！")
#             break
#         except Exception as e:
#             print(f"\n❌ 错误: {e}")
#             logger.error(f"Unexpected error: {e}", exc_info=True)


# def quick_run():
#     """快速运行模式 - 命令行直接传入任务"""
#     if len(sys.argv) > 1:
#         user_input = " ".join(sys.argv[1:]).strip()
#         print(f"\n[快速模式] 执行任务: {user_input[:100]}...")
        
#         cli = TeXAgentCLI(use_branch=True)
#         result = cli.run_task(user_input)
        
#         if result.get("error"):
#             print(f"\n❌ 失败: {result['error']}")
#         else:
#             output = result.get("output", "")
#             print(f"\n📄 结果:\n{output}")
#     else:
#         main()


# if __name__ == "__main__":
#     # 如果有命令行参数，使用快速模式
#     if len(sys.argv) > 1:
#         quick_run()
#     else:
#         main()
# main.py
"""
TeX_Agent 程序主入口
"""
import sys
from core.agent_cli import TeXAgentCLI
from utils.display import display


def print_banner():
    """打印欢迎横幅"""
    print(display.banner(
        "TeX_Agent — LaTeX 论文写作增强系统",
        "基于 LangGraph 多智能体架构 + 分支记忆"
    ))
    print("\n💡 提示: LLM 响应需要 30-60 秒，请耐心等待")
    print("💡 输入 'help' 查看所有命令\n")


def print_help():
    """打印帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════════════
║                        可用命令                                   
╠══════════════════════════════════════════════════════════════════
║  task <Prompt>          - 执行论文写作任务                                
║  branch list            - 列出所有分支                                  
║  branch create <name>   - 创建新分支                               
║  branch switch <name>   - 切换分支                                 
║  branch merge  <name>   - 合并分支到主分支                        
║  status                 - 显示系统状态                                  
║  clear                  - 清空所有记忆                                  
║  help                   - 显示此帮助                                    
║  exit, quit             - 退出程序                                      
╚══════════════════════════════════════════════════════════════════
""")


def main():
    """主函数"""
    print_banner()
    
    cli = TeXAgentCLI(use_branch=True)
    cli.show_status()
    print_help()
    
    while True:
        try:
            user_input = input("\n📝 > ").strip()
            if not user_input:
                continue
            
            # 获取原始输入，不提前分割
            original_input = user_input
            parts = user_input.split()
            
            if not parts:
                continue
            
            first_word = parts[0].lower()
            
            # 退出命令
            if first_word in ['exit', 'quit', 'q']:
                print("\n👋 再见！")
                break
            
            # 帮助命令
            elif first_word in ['help', 'h', '?']:
                print_help()
            
            # 状态命令
            elif first_word in ['status', 'info']:
                cli.show_status()
            
            # 清空命令
            elif first_word in ['clear', 'clean', 'reset']:
                cli.clear_all()
            
            # 分支列表 - 支持 "branches", "branch list", "branch ls"
            elif first_word == 'branches' or (first_word == 'branch' and len(parts) > 1 and parts[1] in ['list', 'ls']):
                cli.list_branches()
            
            # 分支显示详情 - "branch show" 或 "branch-show"
            elif first_word == 'branch' and len(parts) > 1 and parts[1] == 'show':
                cli.show_branch_status()
            elif first_word in ['branch-show', 'branch-info']:
                cli.show_branch_status()
            
            # 创建分支 - "branch create" 或 "create"
            elif first_word == 'create' or (first_word == 'branch' and len(parts) > 1 and parts[1] == 'create'):
                # 提取分支名称
                if first_word == 'create':
                    # create <name> [from_branch]
                    if len(parts) >= 2:
                        branch_name = parts[1]
                        from_branch = parts[2] if len(parts) > 2 else "main"
                        cli.create_branch(branch_name, from_branch)
                    else:
                        print("❌ 请指定分支名称")
                        print("   用法: create <分支名> [源分支]")
                else:
                    # branch create <name> [from_branch]
                    if len(parts) >= 3:
                        branch_name = parts[2]
                        from_branch = parts[3] if len(parts) > 3 else "main"
                        cli.create_branch(branch_name, from_branch)
                    else:
                        print("❌ 请指定分支名称")
                        print("   用法: branch create <分支名> [源分支]")
            
            # 切换分支 - "branch switch" 或 "switch"
            elif first_word == 'switch' or (first_word == 'branch' and len(parts) > 1 and parts[1] == 'switch'):
                if first_word == 'switch':
                    branch_name = parts[1] if len(parts) > 1 else ""
                else:
                    branch_name = parts[2] if len(parts) > 2 else ""
                
                if not branch_name:
                    print("❌ 请指定分支名称")
                    print("   用法: switch <分支名>  或  branch switch <分支名>")
                else:
                    cli.switch_branch(branch_name)
            
            # 合并分支 - "branch merge" 或 "merge"
            elif first_word == 'merge' or (first_word == 'branch' and len(parts) > 1 and parts[1] == 'merge'):
                if first_word == 'merge':
                    branch_name = parts[1] if len(parts) > 1 else ""
                else:
                    branch_name = parts[2] if len(parts) > 2 else ""
                
                if not branch_name:
                    print("❌ 请指定分支名称")
                    print("   用法: merge <分支名>  或  branch merge <分支名>")
                else:
                    cli.merge_branch(branch_name)
            
            # 显式任务命令
            elif first_word in ['task', 'run', 'do']:
                task = ' '.join(parts[1:]) if len(parts) > 1 else ""
                if not task:
                    print("❌ 请提供任务描述")
                    print("   示例: task 请帮我写一篇关于 Transformer 的论文引言")
                else:
                    print("\n" + display.separator())
                    result = cli.run_task(task)
                    print(display.separator())
                    display.print_result(result)
            
            # 其他输入作为任务执行
            else:
                print("\n" + display.separator())
                result = cli.run_task(original_input)
                print(display.separator())
                display.print_result(result)
        
        except KeyboardInterrupt:
            print("\n\n⚠️ 使用 'exit' 退出程序")
            continue
        except EOFError:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()


def quick_run():
    """快速运行模式"""
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:]).strip()
        print(f"\n[快速模式] {user_input[:100]}...")
        
        cli = TeXAgentCLI(use_branch=True)
        result = cli.run_task(user_input)
        
        if result.get("error"):
            print(f"\n❌ 失败: {result['error']}")
        else:
            output = result.get("output", "")
            print(f"\n📄 结果:\n{display.truncate(output)}")
    else:
        main()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        quick_run()
    else:
        main()