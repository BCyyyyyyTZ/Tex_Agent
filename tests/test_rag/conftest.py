"""
test_rag 目录级 pytest 配置：注册本目录专用命令行选项。
"""
from __future__ import annotations


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--rag-db-mode",
        action="store",
        default="tmp",
        choices=["tmp", "real"],
        help=(
            "Background.tex RAG 集成测试："
            "tmp=临时目录内索引+检索+清空（默认）；"
            "real=使用项目根下 knowledge_base（仅检索+清空，不自动索引；会清空整库）"
        ),
    )