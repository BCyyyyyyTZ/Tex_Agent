"""
概念示意图生成工具（ConceptDiagramTool）。

输入一段概念描述，工具会：
1) 调用 LLM（GeminiClient）生成 Mermaid flowchart 代码
2) 将 Mermaid 代码通过 mermaid.ink 渲染为 PNG
3) 输出图片路径，并在 metadata 中返回 Mermaid 代码等信息，便于复现与调试

适用场景：
- 论文方法/系统架构/流程的概念图快速生成
- 把较长的结构化描述“压缩”为图形化概览
"""

import base64
import json
import os
import re
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Optional

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.base_agent import GeminiClient
from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class ConceptDiagramTool(BaseTool):
    """
    将概念描述转换为 Mermaid 并渲染为图片的工具封装。

    说明：
    - 本工具不直接使用本地 Mermaid 渲染，而是调用 mermaid.ink 在线渲染服务生成 PNG。
    - LLM 输出会做基本清洗（去除 ```mermaid 代码块等），并校验必须以 flowchart/graph 开头。
    """
    def __init__(
        self,
        *,
        model_name: str = "gemini-3.1-flash-lite",
        api_key: str = "",
        temperature: float = 0.2,
    ):
        """初始化概念图工具，并配置模型参数（model_name/api_key/temperature）。"""
        super().__init__(
            name="concept_diagram",
            description="输入概念描述，调用 Gemini 生成 Mermaid 结构化代码并渲染为学术风格概念示意图，输出图片路径。",
            input_schema={
                "prompt": "必填，概念描述或需要图示化的内容",
                "output_path": "必填，输出图片路径，例如 'outputs/diagram.png'",
                "title": "可选，图标题",
            },
        )
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = float(temperature)

    def _resolve_api_key(self, api_key: str) -> str:
        """解析实际可用的 Gemini API Key（优先入参，其次实例字段与环境变量）。"""
        return (
            api_key
            or self.api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        )

    def _build_prompt(self, user_prompt: str, title: str) -> str:
        """构造用于生成 Mermaid 的提示词（约束输出为 flowchart 代码本体）。"""
        t = (title or "").strip()
        title_line = f"标题：{t}\n" if t else ""
        return (
            "你是一个论文写作助手，负责把概念内容转换成学术风格的概念示意图。\n"
            "输出必须是 Mermaid 代码本体，禁止输出 Markdown 代码块标记、解释文字或任何额外内容。\n"
            "要求：\n"
            "1) 仅输出一段 Mermaid 代码，以 flowchart 开头。\n"
            "2) 使用简洁节点文本，避免标点符号、引号、括号与特殊字符；尽量使用短语。\n"
            "3) 图结构清晰，层级分明，适合论文排版。\n"
            "4) 不要使用 emoji。\n"
            "5) 默认方向为 TB。\n\n"
            f"{title_line}"
            f"需要图示化的内容：\n{user_prompt}\n"
        )

    def _extract_mermaid(self, text: str) -> str:
        """从模型输出中提取 Mermaid 代码并清理可能的 Markdown 代码块包裹。"""
        s = (text or "").strip()
        if not s:
            return ""
        s = re.sub(r"^```(?:mermaid)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s, flags=re.IGNORECASE)
        return s.strip()

    def _encode_mermaid_ink(self, mermaid_code: str) -> str:
        """将 Mermaid 代码按 mermaid.ink 的 pako 压缩+base64url 规则编码为 URL 片段。"""
        payload = json.dumps(
            {"code": mermaid_code, "mermaid": {"theme": "neutral"}},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        compressed = zlib.compress(payload, level=9)
        encoded = base64.b64encode(compressed).decode("ascii")
        encoded = encoded.replace("+", "-").replace("/", "_")
        return f"pako:{encoded}"

    def _render_with_mermaid_ink(self, mermaid_code: str, output_path: Path) -> None:
        """调用 mermaid.ink 在线渲染服务，将 Mermaid 代码渲染为 PNG 并写入 output_path。"""
        encoded = self._encode_mermaid_ink(mermaid_code)
        url = f"https://mermaid.ink/img/{encoded}?type=png&theme=neutral&bgColor=!white"
        timeout = httpx.Timeout(60.0, connect=10.0)
        last_err: Exception | None = None
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for i in range(3):
                try:
                    r = client.get(url, headers={"Accept": "image/png,image/*"})
                    r.raise_for_status()
                    output_path.write_bytes(r.content)
                    return
                except Exception as e:
                    last_err = e
                    if i < 2:
                        time.sleep(1.0 * (2**i))
                        continue
                    raise last_err

    def run(self, prompt: str, output_path: str, title: str = "") -> ToolResult:
        """
        生成概念示意图。

        Args:
            prompt: 需要图示化的概念/流程描述
            output_path: 输出 PNG 路径（会自动创建父目录）
            title: 可选标题，会注入到 LLM 提示词中
        """
        try:
            if not prompt:
                return ToolResult(success=False, output="", error="prompt 不能为空")
            if not output_path:
                return ToolResult(success=False, output="", error="output_path 不能为空")

            api_key = self._resolve_api_key("")
            if not api_key:
                return ToolResult(
                    success=False,
                    output="",
                    error="未配置 GEMINI_API_KEY 或 GOOGLE_API_KEY，无法调用 GeminiClient",
                )

            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            llm = GeminiClient(model_name=self.model_name, api_key=api_key, temperature=self.temperature)
            llm_prompt = self._build_prompt(prompt, title)
            raw = llm.response(llm_prompt)
            mermaid_code = self._extract_mermaid(raw)

            if not mermaid_code.lower().lstrip().startswith(("flowchart", "graph")):
                return ToolResult(
                    success=False,
                    output="",
                    error="模型输出不是有效的 Mermaid flowchart 代码",
                    metadata={"llm_output": raw},
                )

            self._render_with_mermaid_ink(mermaid_code, out)
            if not out.exists() or out.stat().st_size <= 0:
                return ToolResult(success=False, output="", error="图片生成失败：输出文件为空")

            return ToolResult(
                success=True,
                output=str(out),
                metadata={
                    "output_path": str(out),
                    "model_name": self.model_name,
                    "render_backend": "mermaid.ink",
                    "mermaid_code": mermaid_code,
                    "title": title,
                },
            )
        except Exception as e:
            logger.error(f"ConceptDiagramTool 失败: {e}")
            return ToolResult(success=False, output="", error=f"ConceptDiagramTool 失败: {e}")


def _assert_file_ok(path: str) -> None:
    """断言指定路径文件存在且非空（用于自测验证输出）。"""
    p = Path(path)
    if not p.exists():
        raise AssertionError(f"文件未生成: {p}")
    if p.stat().st_size <= 0:
        raise AssertionError(f"文件为空: {p}")


def _run_self_test(output_dir: Optional[str] = None) -> None:
    """运行本工具的最小自测：生成一张概念图并校验输出文件可用。"""
    base = Path(output_dir) if output_dir else (Path(__file__).resolve().parents[1] / "outputs" / "concept_diagram_tool_test")
    base.mkdir(parents=True, exist_ok=True)

    for p in base.glob("*.png"):
        try:
            p.unlink()
        except Exception:
            pass

    tool = ConceptDiagramTool(model_name="gemini-3.1-flash-lite-preview", api_key="", temperature=0.2)
    r = tool.run(
        prompt=(
            "请画出一个完整的论文方法与实验流程概念图，主题为面向长文档的检索增强生成系统用于学术问答\n"
            "需要包含数据来源与采集 解析与清洗 段落切分 去重 质量过滤\n"
            "需要包含离线索引构建模块 编码器训练 向量表示 向量库构建 稀疏索引构建 元数据存储\n"
            "需要包含训练阶段 模拟查询生成 正负样本构造 对比学习 监督微调 偏好优化\n"
            "需要包含在线推理阶段 查询改写 混合检索 交叉重排 上下文拼接 生成回答 引用对齐 事实核验 安全过滤\n"
            "需要包含失败回退路径 检索为空时关键词检索 仍为空时拒答并给出下一步建议\n"
            "需要包含评测与分析 自动指标 人工评测 消融实验 误差分析\n"
            "需要包含部署与迭代 缓存 监控 反馈收集 周期性重建索引 模型版本回滚"
        ),
        output_path=str(base / "rag_system_overview.png"),
        title="RAG System Overview",
    )
    assert r.success, r.error
    _assert_file_ok(r.output)
    print(f"概念示意图自测通过，输出目录: {base.resolve()}")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else None
    _run_self_test(out_dir)
