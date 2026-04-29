"""
为 Web UI 提供「本地下载」能力：将已生成文件的绝对路径登记为短时 token，
输出 Markdown 链接（相对路径 /api/download/artifact?token=...），浏览器点击即可下载。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger
from utils.web_artifact_registry import register_file

logger = get_logger(__name__)


class OfferArtifactDownloadTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="offer_artifact_download",
            description=(
                "将已存在于本机的文件注册为 Web 下载链接。"
                "用于 pdf_comment 等工具生成 PDF 后，在 TeX Agent 网页中向用户提供可点击下载。"
            ),
            input_schema={
                "file_path": "必填，要提供下载的文件的绝对路径（通常为 pdf_comment 输出的 output_path）",
            },
        )

    def run(self, file_path: str = "", **kwargs: Any) -> ToolResult:
        fp = (file_path or kwargs.get("file_path") or "").strip()
        if not fp:
            return ToolResult(
                success=False,
                output="",
                error="缺少 file_path",
                metadata={},
            )
        try:
            p = Path(fp).expanduser().resolve(strict=False)
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"路径无效: {e}",
                metadata={},
            )
        if not p.is_file():
            return ToolResult(
                success=False,
                output="",
                error=f"文件不存在或不是普通文件: {p}",
                metadata={},
            )
        try:
            token = register_file(str(p))
        except Exception as e:
            logger.warning("register_file 失败: %s", e)
            return ToolResult(
                success=False,
                output="",
                error=str(e),
                metadata={},
            )
        fname = p.name
        rel = f"/api/download/artifact?token={token}"
        # 与 server._append_artifact_download_markdown 一致；前端同域相对路径即可
        md = (
            f"**下载已生成文件**：[{fname}]({rel})\n\n"
            f"点击链接即可像普通网页下载一样保存到本机（若被拦截请允许下载）。"
        )
        return ToolResult(
            success=True,
            output=md,
            metadata={
                "download_token": token,
                "download_filename": fname,
                "relative_url": rel,
                "absolute_path": str(p),
            },
        )
