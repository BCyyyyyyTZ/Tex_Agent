# main_full.py
"""
TeX_Agent 完整功能演示
包含：Memory分支、RAG检索、多Agent协作
"""
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memory.factory import MemoryFactory
from context.context_manager import ContextManager
from workflow.graph_builder import build_graph
from core.state import WorkflowState
from utils.logger import get_logger

logger = get_logger(__name__)


class TeXAgentSystem:
    def __init__(self, use_rag: bool = False, use_branch_memory: bool = False):
        """
        初始化系统
        
        Args:
            use_rag: 是否启用 RAG 检索
            use_branch_memory: 是否启用分支记忆
        """
        # 1. 创建记忆系统
        self.memory_system = self._setup_memory(use_branch_memory)
        
        # 2. 创建上下文管理器
        self.context = ContextManager(max_messages=200, default_limit=20)
        
        # 3. 设置 RAG（可选）
        self.rag_pipeline = None
        if use_rag:
            self._setup_rag()
        
        # 4. 构建工作流
        self.app = build_graph(
            context_manager=self.context,
            rag_pipeline=self.rag_pipeline,
            design_memory=self.memory_system.get("design"),    # 传入 design 记忆
            think_memory=self.memory_system.get("think"),      # 传入 think 记忆
            execute_memory=self.memory_system.get("execute"),  # 传入 execute 记忆
            shared_memory=self.memory_system.get("shared"),    # 传入共享记忆
        )
        
        logger.info("TeX Agent 系统初始化完成")
    
    def _setup_memory(self, use_branch: bool):
        """设置记忆系统"""
        if use_branch:
            # 使用分支记忆（支持实验性探索）
            return {
                "design": MemoryFactory.create_private_memory("design", branch_enabled=True),
                "think": MemoryFactory.create_private_memory("think", branch_enabled=True),
                "execute": MemoryFactory.create_private_memory("execute", branch_enabled=True),
                "shared": MemoryFactory.create_shared_memory(branch_enabled=True),
            }
        else:
            # 使用简单记忆
            return {
                "design": MemoryFactory.create_memory("private", "design"),
                "think": MemoryFactory.create_memory("private", "think"),
                "execute": MemoryFactory.create_memory("private", "execute"),
                "shared": MemoryFactory.create_memory("shared"),
            }
    
    def _setup_rag(self):
        """设置 RAG 管道"""
        try:
            from rag.keyword_rag import KeywordRAGPipeline
            
            self.rag_pipeline = KeywordRAGPipeline()
            
            # 索引示例文档
            sample_docs = [
                "Transformer 架构是 Attention Is All You Need 论文中提出的，主要用于序列到序列的任务。",
                "BERT 是基于 Transformer 的预训练模型，通过掩码语言建模进行训练。",
                "GPT 系列模型使用自回归方式生成文本，适合对话和内容生成任务。",
                "对比学习是一种自监督学习方法，通过拉近正样本、推远负样本来学习表示。",
            ]
            
            for doc in sample_docs:
                self.rag_pipeline.index_document(doc, {"source": "sample"})
            
            logger.info(f"RAG 已启用，索引了 {len(sample_docs)} 个文档")
        except Exception as e:
            logger.warning(f"RAG 初始化失败: {e}")
            self.rag_pipeline = None
    
    def run_task(self, task: str, memory_branch: str = None) -> dict:
        """
        执行任务
        
        Args:
            task: 任务描述
            memory_branch: 使用的记忆分支（None 表示主分支）
        """
        # 切换记忆分支（如果启用）
        if memory_branch and self._is_branch_enabled():
            self._switch_memory_branch(memory_branch)
        
        # 准备初始状态
        initial_state: WorkflowState = {
            "messages": [],
            "current_node": "",
            "input": task,
            "output": "",
            "error": None,
            "metadata": {"memory_branch": memory_branch or "main"},
            "retrieved_context": "",
        }
        
        # 执行工作流
        logger.info(f"执行任务: {task[:50]}...")
        result = self.app.invoke(initial_state)
        
        return result
    
    def _is_branch_enabled(self) -> bool:
        """检查是否启用了分支记忆"""
        return any(
            hasattr(mem, 'branch_enabled') and mem.branch_enabled 
            for mem in self.memory_system.values()
        )
    
    def _switch_memory_branch(self, branch_name: str):
        """切换所有记忆的分支"""
        for name, memory in self.memory_system.items():
            if hasattr(memory, 'switch_branch'):
                memory.switch_branch(branch_name)
        logger.info(f"切换到记忆分支: {branch_name}")
    
    def create_memory_branch(self, branch_name: str, from_branch: str = "main"):
        """创建新的记忆分支"""
        for name, memory in self.memory_system.items():
            if hasattr(memory, 'create_branch'):
                memory.create_branch(branch_name, from_branch)
        logger.info(f"创建记忆分支: {branch_name} (从 {from_branch})")
    
    def merge_memory_branch(self, branch_name: str):
        """合并记忆分支到主分支"""
        results = {}
        for name, memory in self.memory_system.items():
            if hasattr(memory, 'merge_to_main'):
                results[name] = memory.merge_to_main(branch_name)
        logger.info(f"合并分支 {branch_name}: {results}")
        return results
    
    def show_memory_status(self):
        """显示记忆状态"""
        print("\n" + "="*60)
        print("记忆系统状态")
        print("="*60)
        
        for name, memory in self.memory_system.items():
            size = memory.get_size()
            print(f"\n📚 {name.upper()} 记忆:")
            print(f"  存储数量: {size}")
            
            if hasattr(memory, 'get_branch_info'):
                info = memory.get_branch_info()
                if info.get('enabled'):
                    print(f"  分支模式: 启用")
                    print(f"  当前分支: {info.get('current', 'main')}")
                    print(f"  可用分支: {info.get('branches', [])}")
                else:
                    print(f"  分支模式: 未启用")
            
            # 显示最近3条记忆
            if size > 0:
                recent = memory.load(limit=3)
                print(f"  最近记忆:")
                for item in recent:
                    if isinstance(item, dict):
                        content = str(item.get('value', ''))[:50]
                    else:
                        content = str(item)[:50]
                    print(f"    - {content}...")


def demo_branch_memory():
    """演示分支记忆功能"""
    print("\n" + "🔀 " * 20)
    print("演示 1: 分支记忆功能")
    print("🔀 " * 20)
    
    system = TeXAgentSystem(use_rag=False, use_branch_memory=True)
    
    # 1. 主分支执行任务
    print("\n📌 主分支: 执行论文写作任务")
    result1 = system.run_task(
        "请帮我写一篇关于 Transformer 的论文引言"
    )
    print(f"输出: {result1.get('output', '')[:100]}...")
    
    # 2. 创建实验分支
    print("\n📌 创建实验分支 'experiment_contrastive'")
    system.create_memory_branch("experiment_contrastive", from_branch="main")
    
    # 3. 实验分支执行不同任务
    print("\n📌 实验分支: 探索对比学习方向")
    system.run_task(
        "请分析对比学习在 NLP 中的应用前景",
        memory_branch="experiment_contrastive"
    )
    
    # 4. 查看分支状态
    system.show_memory_status()
    
    # 5. 合并实验分支
    print("\n📌 合并实验分支到主分支")
    system.merge_memory_branch("experiment_contrastive")
    
    # 6. 再次查看状态
    system.show_memory_status()


def demo_rag_integration():
    """演示 RAG 集成"""
    print("\n" + "🔍 " * 20)
    print("演示 2: RAG 检索增强")
    print("🔍 " * 20)
    
    system = TeXAgentSystem(use_rag=True, use_branch_memory=False)
    
    # 执行需要检索的任务
    tasks = [
        "Transformer 架构的核心思想是什么？",
        "BERT 和 GPT 有什么区别？",
        "什么是对比学习？"
    ]
    
    for task in tasks:
        print(f"\n📌 任务: {task}")
        result = system.run_task(task)
        output = result.get('output', '')
        
        # 显示是否使用了 RAG 上下文
        if result.get('retrieved_context'):
            print(f"  ✅ 使用了 RAG 检索")
            print(f"  检索到的上下文: {result['retrieved_context'][:100]}...")
        
        print(f"  输出: {output[:150]}...")
        print("-" * 40)


def demo_memory_isolation():
    """演示记忆隔离"""
    print("\n" + "🔒 " * 20)
    print("演示 3: 多 Agent 记忆隔离")
    print("🔒 " * 20)
    
    # 不使用分支，只使用私有记忆
    system = TeXAgentSystem(use_rag=False, use_branch_memory=False)
    
    # 执行多个不同领域的任务
    tasks = [
        "讨论机器学习中的监督学习",
        "讨论深度学习的优化算法",
        "讨论自然语言处理的 tokenization"
    ]
    
    for task in tasks:
        print(f"\n📌 执行: {task[:40]}...")
        system.run_task(task)
    
    # 查看各 Agent 的记忆隔离情况
    print("\n📊 记忆隔离验证:")
    for agent_name, memory in system.memory_system.items():
        size = memory.get_size()
        # 每个 Agent 应该只看到自己的记忆
        all_memories = memory.load()
        print(f"  {agent_name}: {size} 条记忆")
        
        # 验证数据隔离
        if agent_name == "design":
            # Design Agent 不应该有 execute 的内容
            for mem in all_memories:
                content = str(mem) if isinstance(mem, str) else str(mem.get('value', ''))
                if 'optimization' in content.lower():
                    print(f"    ⚠️  发现跨 Agent 数据污染!")
    
    print("\n✅ 记忆隔离验证完成")


def demo_workflow_complete():
    """完整工作流演示"""
    print("\n" + "🚀 " * 20)
    print("演示 4: 完整工作流")
    print("🚀 " * 20)
    
    system = TeXAgentSystem(use_rag=True, use_branch_memory=True)
    
    # 创建实验分支
    system.create_memory_branch("paper_writing")
    
    # 完整的研究论文写作流程
    tasks = [
        "分析当前 LLM 研究的热点方向",
        "设计一个针对代码生成任务的实验方案",
        "总结研究的创新点和潜在问题"
    ]
    
    for i, task in enumerate(tasks, 1):
        print(f"\n{'='*60}")
        print(f"步骤 {i}: {task}")
        print('='*60)
        
        result = system.run_task(task, memory_branch="paper_writing")
        
        print(f"\n输出:\n{result.get('output', '')[:200]}...")
        print(f"\n执行节点: {result.get('current_node')}")
        
        if result.get('error'):
            print(f"错误: {result['error']}")
    
    # 展示整个过程的记忆
    system.show_memory_status()
    
    # 合并回主分支
    print("\n📌 合并论文写作经验到主分支")
    system.merge_memory_branch("paper_writing")


def main():
    """主函数"""
    print("\n" + "="*70)
    print(" TeX_Agent 完整功能演示")
    print("="*70)
    
    demonstrations = [
        ("分支记忆功能", demo_branch_memory),
        ("RAG 检索增强", demo_rag_integration),
        ("记忆隔离验证", demo_memory_isolation),
        ("完整工作流", demo_workflow_complete),
    ]
    
    print("\n请选择演示模式:")
    for i, (name, _) in enumerate(demonstrations, 1):
        print(f"  {i}. {name}")
    print("  0. 运行全部")
    
    try:
        choice = input("\n请输入选择 (0-4): ").strip()
        
        if choice == "0":
            for name, func in demonstrations:
                func()
                input("\n按 Enter 继续...")
        elif choice.isdigit() and 1 <= int(choice) <= len(demonstrations):
            demonstrations[int(choice)-1][1]()
        else:
            print("运行默认演示...")
            demo_workflow_complete()
            
    except KeyboardInterrupt:
        print("\n\n演示中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()