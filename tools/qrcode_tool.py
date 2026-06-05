import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.message import ToolResult
from tools.base_tool import BaseTool
from tools.web_tool_utils import unique_output_path
from utils.logger import get_logger

logger = get_logger(__name__)


class QrcodeTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="qrcode",
            description="根据文本或 URL 生成 QR 码 PNG 图片。",
            input_schema={
                "content": "要编码的内容（URL、文本等）",
                "output_path": "可选输出路径",
            },
        )

    def run(self, content: str = "", output_path: str = "") -> ToolResult:
        try:
            if not (content or "").strip():
                return ToolResult(success=False, output="", error="content 不能为空")
            try:
                import qrcode
            except ImportError:
                return ToolResult(
                    success=False,
                    output="",
                    error="未安装 qrcode 库，请执行：pip install qrcode[pil]",
                )

            out = Path(output_path) if output_path else unique_output_path("qrcode")
            out.parent.mkdir(parents=True, exist_ok=True)
            img = qrcode.make(content.strip())
            img.save(out)
            return ToolResult(
                success=True,
                output=str(out),
                metadata={"output_path": str(out), "content_length": len(content.strip())},
            )
        except Exception as e:
            logger.error(f"QR 码生成失败: {e}")
            return ToolResult(success=False, output="", error=f"QR 码生成失败: {e}")
