"""
列举当前 RAG 向量库中的记录。

在包根目录执行:
  python -m rag.rag_list_cli              # 交互翻页（默认每页 5 条）
  python -m rag.rag_list_cli --dump       # 只打一页后退出
  python -m rag.rag_list_cli --dump --full

交互键：w 上一页，s 下一页，e / Esc 退出（q 也可退出）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rag.rag_pipeline import RAGPipeline  # noqa: E402
from rag.store_listing import (  # noqa: E402
    DEFAULT_LIST_PAGE_SIZE,
    MAX_LIST_PAGE_SIZE,
    StoreField,
    format_stored_chunks_page,
)


def _parse_fields(args: argparse.Namespace) -> StoreField:
    if args.full:
        return StoreField.FULL
    bits = StoreField.ID
    if args.metadata:
        bits |= StoreField.METADATA
    if args.document:
        bits |= StoreField.DOCUMENT
    if args.embedding:
        bits |= StoreField.EMBEDDING
    return bits


def _read_command_key() -> str:
    if sys.platform == "win32":
        import msvcrt

        b = msvcrt.getch()
        if b in (b"\x1b",):
            return "esc"
        if b in (b"\xe0", b"\x00"):
            msvcrt.getch()
            return "unknown"
        if b in (b"\x03",):
            raise KeyboardInterrupt
        return b.decode("utf-8", errors="replace").lower()

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = b""
    try:
        tty.setraw(fd)
        buf = os.read(fd, 1)
        if buf == b"\x1b":
            if select.select([fd], [], [], 0.05)[0]:
                buf += os.read(fd, 64)
            if len(buf) == 1:
                return "esc"
            return "unknown"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return buf.decode("utf-8", errors="replace").lower()


def _run_interactive(pipeline: RAGPipeline, fetch: StoreField, page_size: int, doc_max: int) -> None:
    offset = 0
    page_size = max(1, min(page_size, MAX_LIST_PAGE_SIZE))
    print(
        "\n=== RAG 向量库浏览 ===\n"
        f"每页 {page_size} 条 | [w] 上一页  [s] 下一页  [e]/[Esc]/[q] 退出\n",
        flush=True,
    )
    while True:
        page = pipeline.list_stored_page(offset=offset, limit=page_size, fetch_fields=fetch)
        sys.stdout.write(
            format_stored_chunks_page(page, fetch, document_max_chars=doc_max)
        )
        sys.stdout.flush()
        print(
            f"--- offset={page.offset} 本页 {len(page.items)} 条 / 共 {page.total} 条 ---",
            flush=True,
        )
        if not sys.stdin.isatty():
            print("(非交互终端，结束)", flush=True)
            return
        try:
            key = _read_command_key()
        except KeyboardInterrupt:
            print("\n(已中断)", flush=True)
            return
        if key in ("e", "q", "esc"):
            print("再见。", flush=True)
            return
        if key == "w":
            offset = max(0, offset - page_size)
        elif key == "s":
            if page.has_next:
                offset += page_size
            else:
                print("(已是最后一页)", flush=True)
        else:
            print(f"(未识别按键 {key!r}，请用 w/s/e)", flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="浏览 RAG / Chroma 持久化库中的 chunk（分页）。")
    p.add_argument("--dump", action="store_true", help="只输出一页后退出（非交互）")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_PAGE_SIZE,
        help=f"每页条数，最大 {MAX_LIST_PAGE_SIZE}（默认 {DEFAULT_LIST_PAGE_SIZE}）",
    )
    p.add_argument("--full", action="store_true")
    p.add_argument("--metadata", action="store_true")
    p.add_argument("--document", action="store_true")
    p.add_argument("--embedding", action="store_true")
    p.add_argument("--doc-max-chars", type=int, default=2000)
    args = p.parse_args(argv)

    fetch = StoreField.FULL if args.full else _parse_fields(args)
    page_size = min(int(args.limit), MAX_LIST_PAGE_SIZE)
    pipeline = RAGPipeline()

    if args.dump or not sys.stdin.isatty():
        page = pipeline.list_stored_page(
            offset=args.offset, limit=page_size, fetch_fields=fetch
        )
        sys.stdout.write(
            format_stored_chunks_page(page, fetch, document_max_chars=args.doc_max_chars)
        )
        return 0

    _run_interactive(pipeline, fetch, page_size, args.doc_max_chars)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())