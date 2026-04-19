"""
RAG 向量库删除命令行：按 chunk id、按 source（元数据）删除，或整库清空。

用法（在 Tex_Agent 包根目录，与 config/、rag/ 同级）：
  python rag/rag_delete_cli.py --ids <uuid> [<uuid> ...]
  python rag/rag_delete_cli.py --source <metadata中的source字符串>
  python rag/rag_delete_cli.py --clear-all --yes

向量库路径由 RAG_PERSIST_DIR / settings.rag_persist_directory 决定；未配置则为内存模式（删完进程结束即无意义）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rag.rag_pipeline import RAGPipeline  # noqa: E402
from config.settings import settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402
from rag.store_listing import StoreField  # noqa: E402

logger = get_logger(__name__)


def build_pipeline() -> RAGPipeline:
    return RAGPipeline()


def cmd_delete_ids(pipeline: RAGPipeline, ids: list[str]) -> int:
    n = pipeline.delete_chunks_by_ids(ids)
    print(f"已按 id 提交删除（去重后 {len({i.strip() for i in ids if i.strip()})} 个）；返回值 n={n}（含义与底层实现一致，参见文档）。")
    print(f"当前库中剩余片段数: {pipeline.document_count()}")
    return 0


def cmd_delete_source(pipeline: RAGPipeline, source: str) -> int:
    n = pipeline.delete_by_source(source)
    print(f"按 source={source!r} 删除，返回 n={n}。")
    print(f"当前库中剩余片段数: {pipeline.document_count()}")
    return 0


def cmd_clear_all(pipeline: RAGPipeline) -> int:
    pipeline.clear()
    print("已清空整个向量库。")
    return 0


def cmd_list_preview(pipeline: RAGPipeline, limit: int) -> int:
    page = pipeline.list_stored_page(offset=0, limit=limit, fetch_fields=StoreField.DEFAULT)
    print(
        f"collection={page.collection_name!r} total={page.total} "
        f"persist_directory={page.persist_directory!r}"
    )
    for rec in page.items:
        src = (rec.metadata or {}).get("source", "")
        print(f"  id={rec.id}  source={src!r}")
    if page.has_next:
        print("（还有更多条，请增大 --limit 或自行分页）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="RAG 向量库：按 id / 按 source 删除片段，或整库清空。",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="ID",
        help="要删除的一个或多个 chunk id（与 rag_list_cli 列举的 id 一致）",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="删除 metadata.source 等于该字符串的全部 chunk（须与索引时写入的 source 完全一致）",
    )
    parser.add_argument(
        "--clear-all",
        action="store_true",
        help="清空整个向量库（危险）",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="与 --clear-all 合用，确认执行清空",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="仅列举前若干条记录的 id 与 source，不删除",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="与 --list 合用，最多列出几条（默认 10，受底层 MAX_LIST_PAGE_SIZE 限制）",
    )

    args = parser.parse_args(argv)

    persist = settings.rag_persist_directory or "(未配置，内存模式)"
    print(f"RAG 持久化目录: {persist}")

    pipeline = build_pipeline()

    if args.list:
        return cmd_list_preview(pipeline, max(1, min(args.limit, 10)))

    if args.clear_all:
        if not args.yes:
            print("拒绝：整库清空需要同时传入 --yes", file=sys.stderr)
            return 2
        return cmd_clear_all(pipeline)

    if args.ids:
        return cmd_delete_ids(pipeline, list(args.ids))

    if args.source is not None:
        if args.source == "":
            print("拒绝：--source 不能为空字符串", file=sys.stderr)
            return 2
        return cmd_delete_source(pipeline, args.source)

    parser.print_help()
    print("\n提示：使用 --list 查看 id；使用 --ids / --source / --clear-all --yes 执行删除。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())