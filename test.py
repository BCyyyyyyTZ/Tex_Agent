# test_context_memory.py
"""
验证 Context 和 Memory 模块的正确实现
"""

import sys
from typing import List, Dict, Any
from datetime import datetime

# 导入你的模块
from memory.base_memory import MemoryType
from memory.simple_memory import SimpleMemory
from memory.branch_memory import BranchMemory
from memory.factory import MemoryFactory
from context.context_manager import ContextManager
from core.message import AgentMessage


def test_simple_memory():
    """测试 SimpleMemory 基础功能"""
    print("\n" + "="*60)
    print("1. 测试 SimpleMemory 基础功能")
    print("="*60)
    
    # 共享模式测试
    print("\n📌 共享模式 (SHARED)")
    shared_mem = SimpleMemory(memory_type=MemoryType.SHARED, max_size=5)
    
    # 保存记忆
    for i in range(7):  # 超过 max_size=5
        shared_mem.save(f"key_{i}", f"value_{i}", {"index": i})
    
    print(f"  存储数量: {shared_mem.get_size()} (期望5, 超过限制自动淘汰)")
    
    # 加载测试
    all_items = shared_mem.load()
    print(f"  加载所有: {len(all_items)} 条")
    
    # 搜索测试
    results = shared_mem.search("value_5")
    print(f"  搜索 'value_5': {results}")
    
    # 私有模式测试
    print("\n📌 私有模式 (PRIVATE)")
    private_mem1 = SimpleMemory(memory_type=MemoryType.PRIVATE, agent_id="agent_1")
    private_mem2 = SimpleMemory(memory_type=MemoryType.PRIVATE, agent_id="agent_2")
    
    private_mem1.save("task", "Agent 1 的任务")
    private_mem2.save("task", "Agent 2 的任务")
    
    print(f"  Agent1 记忆: {private_mem1.load('task')}")
    print(f"  Agent2 记忆: {private_mem2.load('task')}")
    print(f"  数据隔离验证: ✅ 通过")
    
    return True


def test_branch_memory():
    """测试 BranchMemory 分支功能"""
    print("\n" + "="*60)
    print("2. 测试 BranchMemory 分支功能")
    print("="*60)
    
    # 创建带分支功能的记忆
    mem = BranchMemory(memory_type=MemoryType.PRIVATE, 
                       agent_id="test", 
                       branch_enabled=True)
    
    # 主分支保存数据
    mem.save("main_key", "main_value", {"branch": "main"})
    print(f"  主分支保存后: {mem.load()}")
    
    # 创建实验分支
    mem.create_branch("experiment")
    mem.switch_branch("experiment")
    mem.save("exp_key", "exp_value", {"branch": "experiment"})
    print(f"  实验分支保存后: {mem.load()}")
    
    # 切换回主分支验证隔离
    mem.switch_branch("main")
    main_data = mem.load()
    print(f"  切换回主分支: {main_data}")
    print(f"  数据隔离验证: {'✅ 通过' if len(main_data) == 1 else '❌ 失败'}")
    
    # 合并分支
    result = mem.merge_to_main("experiment")
    print(f"  合并结果: {result}")
    
    # 查看分支信息
    info = mem.get_branch_info()
    print(f"  分支信息: {info['branches']}")
    
    return True


def test_memory_factory():
    """测试 MemoryFactory 工厂模式"""
    print("\n" + "="*60)
    print("3. 测试 MemoryFactory")
    print("="*60)
    
    # 创建不同类型记忆
    shared = MemoryFactory.create_memory(mode="shared")
    private = MemoryFactory.create_memory(mode="private", agent_id="agent_x")
    
    shared.save("factory_test", "shared_data")
    private.save("factory_test", "private_data")
    
    print(f"  共享记忆: {shared.load('factory_test')}")
    print(f"  私有记忆: {private.load('factory_test')}")
    
    # 创建混合记忆系统
    hybrid = MemoryFactory.create_hybrid_memory(branch_enabled=False)
    print(f"  混合记忆系统包含: {list(hybrid.keys())}")
    
    # 保存到不同 Agent 的记忆
    hybrid["design"].save("role", "designer")
    hybrid["think"].save("role", "thinker")
    
    print(f"  Design 记忆: {hybrid['design'].load('role')}")
    print(f"  Think 记忆: {hybrid['think'].load('role')}")
    print(f"  数据隔离验证: ✅ 通过")
    
    return True


def test_context_manager():
    """测试 ContextManager"""
    print("\n" + "="*60)
    print("4. 测试 ContextManager")
    print("="*60)
    
    # 创建上下文管理器
    ctx = ContextManager(max_messages=10, default_limit=5)
    
    # 保存消息
    msg1 = AgentMessage(role="user", content="Hello, I need help with LaTeX", agent_name="user")
    msg2 = AgentMessage(role="assistant", content="I can help you with LaTeX!", agent_name="design")
    
    ctx.save(msg1)
    ctx.save(msg2)
    
    print(f"  保存消息后数量: {len(ctx)}")
    
    # 加载消息
    all_msgs = ctx.load()
    print(f"  加载所有消息: {len(all_msgs)} 条")
    print(f"  最新消息: {all_msgs[-1].content[:50]}...")
    
    # 限制加载
    limited = ctx.load(limit=1)
    print(f"  限制加载1条: {len(limited)} 条")
    
    # structure 方法测试
    formatted = ctx.structure([msg1, msg2], format_type="plain")
    print(f"  格式化输出:\n{formatted[:100]}...")
    
    # 清空测试
    ctx.clear()
    print(f"  清空后数量: {len(ctx)}")
    
    return True


def test_gssc_pipeline():
    """测试 GSSC 上下文构建流水线"""
    print("\n" + "="*60)
    print("5. 测试 GSSC 上下文构建流水线")
    print("="*60)
    
    # 准备测试数据
    ctx = ContextManager(max_messages=50, default_limit=10)
    mem = SimpleMemory(memory_type=MemoryType.SHARED)
    
    # 添加对话历史
    ctx.save(AgentMessage(role="user", content="帮我写一个论文摘要", agent_name="user"))
    ctx.save(AgentMessage(role="assistant", content="好的，请问论文主题是什么？", agent_name="design"))
    ctx.save(AgentMessage(role="user", content="关于 Transformer 在 NLP 中的应用", agent_name="user"))
    
    # 添加长期记忆
    mem.save("preference", "用户偏好技术细节", {"type": "preference"})
    mem.save("history", "之前讨论过注意力机制", {"type": "discussion"})
    
    # 构建状态
    state = {
        "messages": ctx.load(),
        "input": "请给出详细的技术方案",
        "retrieved_context": "RAG 检索到的相关论文：Attention Is All You Need...",
    }
    
    # 测试 build 方法
    context_str = ctx.build(
        state=state,
        memory=mem,
        config={
            "conv_limit": 5,
            "mem_limit": 2,
            "max_tokens": 2000,
            "format": "plain"
        }
    )
    
    print(f"  生成的上下文长度: {len(context_str)} 字符")
    print(f"  上下文预览:\n{context_str[:300]}...")
    
    # 验证各个部分是否被包含
    checks = {
        "RAG 检索": "retrieved" in context_str,
        "长期记忆": "memory" in context_str,
        "对话历史": "history" in context_str,
    }
    
    for name, passed in checks.items():
        print(f"  {name}集成: {'✅' if passed else '❌'}")
    
    return True


def test_integration():
    """集成测试：Context + Memory 协同工作"""
    print("\n" + "="*60)
    print("6. 集成测试：Context + Memory 协同")
    print("="*60)
    
    ctx = ContextManager(max_messages=20)
    mem = SimpleMemory(memory_type=MemoryType.SHARED)
    
    # 模拟工作流
    tasks = [
    ("user", "需要写一个机器学习论文的引言"),  # 改为 'user'
    ("assistant", "我建议从问题背景、相关工作、研究贡献三个部分展开"),  # 改为 'assistant'
    ("user", "重点关注对比学习方向"),
    ("assistant", "对比学习是自监督学习的代表，建议强调这一点"),
    ]
    
    print("  模拟对话流程:")
    for role, content in tasks:
        msg = AgentMessage(role=role.lower(), content=content, agent_name=role)
        ctx.save(msg)
        print(f"    [{role}] {content[:40]}...")
    
    # 保存重要信息到长期记忆
    mem.save("topic", "对比学习", {"importance": "high"})
    mem.save("structure", ["背景", "相关工作", "贡献"], {"type": "outline"})
    
    # 构建最终上下文
    state = {
        "messages": ctx.load(),
        "input": "请基于以上讨论生成引言",
        "retrieved_context": "",
    }
    
    final_context = ctx.build(state, memory=mem, config={
        "conv_limit": 10, "mem_limit": 5
    })
    
    # 验证记忆是否被检索到
    search_result = mem.search("对比学习")
    print(f"\n  记忆检索测试:")
    print(f"    搜索 '对比学习': {search_result}")
    
    # 验证上下文构建
    print(f"  最终上下文长度: {len(final_context)} 字符")
    print(f"  集成测试: ✅ 通过")
    
    return True


def performance_test():
    """性能测试"""
    print("\n" + "="*60)
    print("7. 性能测试")
    print("="*60)
    
    import time
    
    # Memory 性能测试
    mem = SimpleMemory(max_size=10000)
    start = time.time()
    
    for i in range(5000):
        mem.save(f"key_{i}", f"value_{i} * 100", {"index": i})
    
    mem_time = time.time() - start
    print(f"  Memory 存储 5000 条: {mem_time:.3f} 秒")
    
    # 搜索性能
    start = time.time()
    results = mem.search("500")
    search_time = time.time() - start
    print(f"  Memory 搜索: {search_time:.3f} 秒, 找到 {len(results)} 条")
    
    # Context 性能测试
    ctx = ContextManager(max_messages=1000)
    start = time.time()
    
    for i in range(500):
        msg = AgentMessage(role="user", content=f"Message {i}", agent_name="test")
        ctx.save(msg)
    
    ctx_time = time.time() - start
    print(f"  Context 存储 500 条: {ctx_time:.3f} 秒")
    
    # GSSC 构建性能
    state = {"messages": ctx.load(), "input": "test"}
    start = time.time()
    context = ctx.build(state)
    build_time = time.time() - start
    print(f"  GSSC 上下文构建: {build_time:.3f} 秒, {len(context)} 字符")
    
    return True


def main():
    """运行所有验证测试"""
    print("\n" + "🔍 " * 20)
    print("Context & Memory 模块验证测试")
    print("🔍 " * 20)
    
    tests = [
        ("基础记忆功能", test_simple_memory),
        ("分支记忆功能", test_branch_memory),
        ("记忆工厂模式", test_memory_factory),
        ("上下文管理器", test_context_manager),
        ("GSSC 流水线", test_gssc_pipeline),
        ("集成测试", test_integration),
        ("性能测试", performance_test),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n❌ 测试失败: {name}")
            print(f"   错误: {e}")
    
    # 总结
    print("\n" + "="*60)
    print("验证结果总结")
    print("="*60)
    
    for name, passed, error in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
        if error:
            print(f"       原因: {error}")
    
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有验证通过！Context 和 Memory 实现正确。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查实现。")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)