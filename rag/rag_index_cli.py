"""
RAG 文件索引命令行入口：从标准输入或命令行参数收集文件路径，调用 RAGPipeline 分块与向量化。

用法（在 Tex_Agent 包根目录下，与 config/、rag/ 同级）：
  python rag/rag_index_cli.py              # 交互输入路径
  python rag/rag_index_cli.py a.md b.tex   # 直接指定文件

路径规则：
  - 相对路径：相对于当前工作目录（启动命令时的 cwd）
  - 绝对路径：直接使用
向量库位置由环境变量 RAG_PERSIST_DIR（或 .env）与 config.settings 决定；未配置则为内存模式。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 包根目录：.../Tex_Agent（内含 config、rag）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rag.rag_pipeline import RAGPipeline  # noqa: E402
from config.settings import settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

_QUIT_TOKENS = frozenset({"quit", "exit", "q"})


def resolve_user_file_path(line: str) -> Path:
    """用户输入的一行路径：去空白与引号；相对路径按 cwd 解析。"""
    s = line.strip().strip('"').strip("'")
    if not s:
        return Path()
    p = Path(s)
    if p.is_absolute():
        return p.resolve()
    return (Path.cwd() / p).resolve()


def collect_paths_interactive() -> list[Path]:
    print(
        "请输入要索引的文件路径（每行一个）。\n"
        "  - 相对路径相对于当前工作目录\n"
        "  - 绝对路径可直接粘贴\n"
        "输入空行或 quit / exit 结束并开始索引。\n"
    )
    paths: list[Path] = []
    while True:
        try:
            line = input("文件路径> ").rstrip("\n")
        except EOFError:
            break
        if not line.strip():
            break
        if line.strip().lower() in _QUIT_TOKENS:
            break
        p = resolve_user_file_path(line)
        if not str(p):
            continue
        paths.append(p)
    return paths


def index_paths(pipeline: RAGPipeline, paths: list[Path]) -> int:
    """索引多个文件；返回失败文件数。"""
    errors = 0
    for p in paths:
        if not p.is_file():
            logger.error(f"跳过（不是文件或不存在）: {p}")
            errors += 1
            continue
        try:
            n = pipeline.index_file(str(p))
            print(f" [OK] {p}  ->  {n} 个片段已写入")
        except Exception as e:
            logger.exception("索引失败: %s", p)
            print(f"  [FAIL] {p}: {e}")
            errors += 1
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="将本地文件索引到 RAG 向量库（Chroma）。")
    parser.add_argument(
        "files",
        nargs="*",
        help="待索引文件（可多个）；不传则进入交互模式",
    )
    args = parser.parse_args(argv)

    persist = settings.rag_persist_directory
    if persist:
        print(f"向量库持久化目录: {persist}")
    else:
        print("未配置 RAG_PERSIST_DIR：使用内存模式（进程退出后数据不保留）")

    pipeline = RAGPipeline()

    if args.files:
        paths = [resolve_user_file_path(f) for f in args.files]
        paths = [p for p in paths if str(p)]
    else:
        paths = collect_paths_interactive()

    if not paths:
        print("未提供任何文件路径，退出。")
        return 0

    print(f"共 {len(paths)} 个路径待处理…")
    err_count = index_paths(pipeline, paths)
    total = pipeline.document_count()
    print(f"当前向量库片段总数: {total}")
    return 1 if err_count else 0


if __name__ == "__main__":
    raise SystemExit(main())