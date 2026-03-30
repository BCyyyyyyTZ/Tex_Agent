# ============================================================
# scripts/setup_kb.py — 知识库初始化脚本
# ============================================================
# 在首次部署时运行此脚本，完成以下初始化工作：
#
# 1. 初始化向量数据库集合（ChromaDB / FAISS）
#    - papers: 论文知识库集合
#    - expert_kb: 专家知识集合
#    - user_docs: 用户文档默认集合
#
# 2. 加载预置专家知识（LaTeX 写作指南、会议评审规范等）
#    - 从 data/expert_knowledge/ 目录读取 JSON/Markdown 文件
#    - 调用 ExpertKnowledgeBase.load_builtin_knowledge()
#
# 3. 可选：预下载 arXiv 种子论文（提升冷启动体验）
#    - 从 data/seed_papers.json 读取初始化论文列表
#    - 调用 ArXivRetriever 批量下载并索引
#
# 使用方式：
#   python scripts/setup_kb.py
#   python scripts/setup_kb.py --skip-papers  # 跳过论文下载
#   python scripts/setup_kb.py --reset        # 重置所有集合
# ============================================================

import argparse
import asyncio
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def init_vector_collections(reset: bool = False) -> None:
    """
    初始化向量数据库集合。
    【需要实现】
    - 如 reset=True，先删除旧集合再重建
    - 创建 papers / expert_kb / user_docs 集合
    """
    print("📦 初始化向量数据库集合...")
    # 【需要实现】
    print("✅ 向量数据库集合创建完成")


async def load_expert_knowledge() -> None:
    """
    加载预置专家知识。
    【需要实现】
    - 遍历 data/expert_knowledge/ 目录
    - 调用 ExpertKnowledgeBase.load_builtin_knowledge()
    """
    print("📚 加载专家知识库...")
    # 【需要实现】
    print("✅ 专家知识加载完成")


async def download_seed_papers(paper_list_path: str = "data/seed_papers.json") -> None:
    """
    预下载种子论文。
    【需要实现】
    - 读取种子论文 ID 列表（arXiv ID 格式）
    - 调用 ArXivRetriever 批量获取摘要
    - 索引到 PaperKnowledgeBase
    """
    print("🔬 下载种子论文...")
    # 【需要实现】
    print("✅ 种子论文下载完成")


async def main(args: argparse.Namespace) -> None:
    print("🚀 NeuroTeX 知识库初始化开始...")
    await init_vector_collections(reset=args.reset)
    await load_expert_knowledge()
    if not args.skip_papers:
        await download_seed_papers()
    print("\n🎉 知识库初始化完成！现在可以启动 NeuroTeX 了。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroTeX 知识库初始化脚本")
    parser.add_argument("--reset", action="store_true", help="重置所有向量集合")
    parser.add_argument("--skip-papers", action="store_true", help="跳过种子论文下载")
    args = parser.parse_args()
    asyncio.run(main(args))
