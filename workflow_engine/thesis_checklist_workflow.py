from __future__ import annotations

"""
论文检查清单工作流（Thesis Checklist Workflow）。

该模块把“检查清单（Markdown） + LLM + PDF 批注工具”组合为可执行的 DAG 工作流：
- 按二级标题（##）将清单拆成若干 section
- 对每个 section 调用 LLM 生成对应的工具调用（pdf_comment）
- ToolNode 执行 pdf_comment，在 PDF 上批注问题片段
- 汇总各 section 的工具执行结果，输出统计信息

该工作流的节点与消息模型来自 workflow_engine.*，工具来自 tools/pdf_comment_tool.py。
"""

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Callable

from tools.pdf_comment_tool import PdfCommentTool
from workflow_engine.messages import TextMessage, ToolCallMessage, ToolResultMessage, MergedMessage, WorkflowMessage
from workflow_engine.nodes import LlmClientLike, LlmNode, ToolNode, FunctionNode
from workflow_engine.workflow import Workflow, WorkflowContext

from workflow_engine.config import MODE


@dataclass(frozen=True)
class ChecklistSection:
    """
    清单分段结构。

    title: Markdown 二级标题文本（## ...）
    content: 该标题下的正文内容（原样保留，交给 LLM 做检查依据）
    """
    title: str
    content: str


def split_checklist_by_primary_headings(markdown_text: str) -> list[ChecklistSection]:
    """
    将 Markdown 清单按二级标题（##）切分为多个 ChecklistSection。

    约定：
    - 仅把 "## " 开头的行视为 section 标题
    - 只保留有正文内容的 section（空内容会被过滤）
    """
    text = markdown_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    sections: list[ChecklistSection] = []
    current_title: Optional[str] = None
    buf: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_title is not None:
                content = "\n".join(buf).strip()
                sections.append(ChecklistSection(title=current_title, content=content))
            current_title = line[3:].strip()
            buf = []
            continue

        if current_title is not None:
            buf.append(line)

    if current_title is not None:
        content = "\n".join(buf).strip()
        sections.append(ChecklistSection(title=current_title, content=content))

    return [s for s in sections if s.content.strip() != ""]


_QUOTE_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)


def extract_question_list(llm_text: str) -> list[dict[str, Any]]:
    """
    从 LLM 回复中提取问题列表（JSON 数组）。

    该实现兼容某些模型输出中的中英文引号差异，并要求模型使用：
        BEGIN [ ...json array... ] END
    的包裹格式，便于稳健提取。
    """
    text = (llm_text or "").translate(_QUOTE_TRANSLATION)
    m = re.search(r"BEGIN\s*(\[[\s\S]*?\])\s*END", text)
    if not m:
        raise ValueError("模型回复中未包含 BEGIN ... END 的问题列表")

    raw = m.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = raw.replace("'", '"')
        data = json.loads(raw2)

    if not isinstance(data, list):
        raise ValueError("问题列表必须是 JSON 数组")
    return data


def build_section_prompt(section: ChecklistSection) -> str:
    """
    构造单个检查 section 的提示词。

    目标是让 LLM 输出严格 TOOL_CALL 格式，从而驱动 ToolNode 执行 pdf_comment。
    """
    return (
        "你是一个专业的论文检查助手。你的任务是根据给定的检查项，只检查用户上传的 PDF 论文是否符合要求，"
        "找出所有不符合要求的问题，并按指定格式输出问题列表。\n\n"
        f"本次检查部分：{section.title}\n"
        "检查项：\n"
        f"{section.content}\n\n"
        "你的回答必须严格为以下格式之一：\n"
        'TOOL_CALL pdf_comment {"question_list": [{"page_idx": 1, "text": "需要高亮的原文片段", "comment": "不符合原因"}, ...]}\n'
        "或（没有任何问题时）：\n"
        "TOOL_CALL none []\n\n"
        "要求：\n"
        "1. page_idx 为问题在论文中的页数，注意不是pdf中标注的页码，而是从pdf第一页开始问题所在的页数（不论一页pdf是否标注页码，均计算在页数中），从 1 开始。\n"
        "2. text 字段确定的方法：\n"
        "   1）找到问题所在的片段。\n"
        "   2）在问题附近找出一段不含有任何标点符号，英文字符（如单词），数字，特殊格式（如角标）且在全文具有唯一性的中文文字片段。\n"
        "   3）再次检查选取的片段，确保不包含标点符号，英文字符（如单词），数字，特殊格式（如角标），只包含中文文字内容，且在全文具有唯一性。\n"
        "   4）确保文字片段与原文在字符串意义上完全相同后作为 text 字段。\n"
        "3. text 字段要求：\n"
        "   1）text 必须在字符串层面严格匹配 PDF 原文内容。\n"
        "   2）text 字段不包含标点符号，英文字符（如单词），数字，特殊格式（如角标），只包含中文文字内容，且在全文具有唯一性\n"
        "   3）text 字段在保证标识性的前提下尽可能短，但不要太短（如一个词语）导致全文多次匹配\n"
        "4. comment 为不符合原因，表述简洁明确。\n"
        "5. 输出必须是可被 json.loads 直接解析的 JSON。\n"
        "6. 不要输出除 TOOL_CALL 格式外的任何内容。\n"
        "7. 不要输出论文要求中没有提到的问题，保证每个问题在检查项中均存在。\n"
    )


class ThesisChecklistWorkflow:
    """
    论文检查工作流封装类。

    负责：
    - 读取并切分 checklist
    - 选择/初始化 LLM 客户端（默认 QwenClient，可替换）
    - 构建 workflow：prepare_pdf -> (sec_i_llm -> pdf_comment)* -> summary
    - 对外提供 run(pdf_path, output_path) 作为一键执行入口
    """
    def __init__(
        self,
        *,
        checklist_path: str,
        llm_client: Optional[LlmClientLike] = None,
        pdf_comment_tool: Optional[PdfCommentTool] = None,
        #model_name: str = "gemini-3.1-flash-lite-preview",
        #model_name: str = "gemini-3-flash-preview",
        model_name: str = "qwen-long-2025-01-25",
        api_key: str = "",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature: float = 0.2,
    ):
        """
        Args:
            checklist_path: Markdown 清单路径（按 ## 分段）
            llm_client: 可选外部注入的 LLM 客户端；不传则按 model_name 选择默认实现
            pdf_comment_tool: 可选外部注入的 PDF 批注工具实例
            model_name/api_key/base_url/temperature: 默认 LLM 客户端初始化参数
        """
        self.checklist_path = str(Path(checklist_path).resolve())

        with open(self.checklist_path, "r", encoding="utf-8") as f:
            md = f.read()
        self.sections = split_checklist_by_primary_headings(md)


        if llm_client is None:
            m = (model_name or "").lower()
            from agents.base_agent import QwenClient

            llm_client = QwenClient(
                model_name=model_name,
                api_key=api_key,
                temperature=temperature,
                base_url=base_url,
            )
            #from agents.base_agent import GeminiClient
            #llm_client = GeminiClient(model_name=model_name, api_key=api_key, temperature=temperature)
        
        self.llm_client = llm_client

        self.pdf_comment_tool = pdf_comment_tool or PdfCommentTool()

    def build(self) -> Workflow:
        """
        构建并返回 Workflow 实例（不执行）。

        节点组成：
        - prepare_pdf: 复制 PDF 到输出路径（确保工具对输出文件写入）
        - sec_*_llm: 每个 section 的 LLM 节点，输出 TOOL_CALL pdf_comment 或 none
        - pdf_comment: 工具节点，执行批注
        - summary: 汇总工具执行结果，输出统计信息
        """

        def prepare_pdf(msg: WorkflowMessage, _ctx: WorkflowContext) -> WorkflowMessage:
            """
            把输入 PDF 复制到 output_path。

            这样后续 pdf_comment 直接在 output_path 上打批注，避免破坏原始 pdf_path。
            """
            pdf_path = str(Path(msg.metadata["pdf_path"]).resolve())
            output_path = str(Path(msg.metadata["output_path"]).resolve())
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf_path, output_path)
            return TextMessage(
                text="",
                metadata={
                    "pdf_path": pdf_path,
                    "output_path": output_path,
                },
            )

        wf = Workflow()
        wf.add_node(FunctionNode("prepare_pdf", prepare_pdf))

        
        wf.add_node(
            ToolNode(
                "pdf_comment", 
                tool_names=["pdf_comment"],
            )
        )

        for idx, section in enumerate(self.sections, start=1):
            llm_node_id = f"sec_{idx:02d}_llm"

            wf.add_node(
                LlmNode(
                    llm_node_id,
                    self.llm_client,
                    prompt=build_section_prompt(section),
                )
            )
            

            wf.add_edge("prepare_pdf", llm_node_id)
            wf.add_edge(llm_node_id, "pdf_comment")


        def summarize(msg: WorkflowMessage, ctx: WorkflowContext) -> WorkflowMessage:
            """
            汇总 pdf_comment 多次执行的结果，输出统计数据到 metadata。

            统计项包括：
            - total_issues: 总问题数
            - success_count/error_count: 工具内部批注成功/失败计数
            - tool_call_summaries: 每个 section 的简表
            """

            results = msg.tool_results["results"]

            tool_call_summaries: list[dict[str, Any]] = []
            total_issues = 0
            total_success_count = 0
            total_error_count = 0
            errors: list[dict[str, Any]] = []
            commented_pages: set[int] = set()

            for i, r in enumerate(results, start=1):
                if MODE == "debug":
                    print(f"总结第{i}个检查项结果: {r}\n\n")
                r_meta = dict(getattr(r, "metadata", {}) or {})
                issues = int(r_meta.get("total_count") or 0)
                success_count = int(r_meta.get("success_count") or 0)
                error_count = int(r_meta.get("error_count") or 0)

                effective_success = bool(getattr(r, "success", False)) or issues == 0

                total_issues += issues
                total_success_count += success_count
                total_error_count += error_count
                commented_pages.update(r_meta.get("commented_pages", set()))
                
                tool_call_summaries.append(
                    {
                        "idx": i,
                        "issues": issues,
                        "success": effective_success,
                        "success_count": success_count,
                        "error_count": error_count,
                    }
                )

                if getattr(r, "error", None):
                    errors.append({"idx": i, "error": r.error})

            tool_success = all(s["success"] for s in tool_call_summaries) if tool_call_summaries else True

            base_meta: dict[str, Any] = {}
            base_meta["tool_success"] = tool_success
            base_meta["total_issues"] = total_issues
            base_meta["total_success_count"] = total_success_count
            base_meta["total_error_count"] = total_error_count
            base_meta["tool_call_summaries"] = tool_call_summaries
            if errors:
                base_meta["tool_errors"] = errors

            print(f"summary finish:\nsuccess: {tool_success}\ntotal issues: {total_issues}\ntotal success count: {total_success_count}\ntotal error count: {total_error_count}\ncommented pages: {sorted(commented_pages)}")

            return TextMessage(text="summary finish", metadata=base_meta)

        wf.add_node(FunctionNode("summary", summarize))
        wf.add_edge("pdf_comment", "summary")

        return wf

    def run(
        self,
        *,
        pdf_path: str,
        output_path: str,
    ) -> Any:
        """
        执行论文检查工作流。

        Args:
            pdf_path: 输入 PDF 路径
            output_path: 输出 PDF 路径（带批注）
        """
        ctx = WorkflowContext(
            metadata={
                "file_to_upload": [pdf_path], 
                "tool_default_args": {
                    "pdf_comment": {
                        "pdf_path": pdf_path,
                        "output_path": output_path,
                    }
                }
            }
        )
        wf = self.build()
        return wf.run(
            initial_message=TextMessage(text="", metadata={"pdf_path": pdf_path, "output_path": output_path}), 
            context=ctx
        )

if __name__ == "__main__":
    wf = ThesisChecklistWorkflow(checklist_path="thesis-checklists.md")
    wf.run(pdf_path=r"C:\Users\Drago\Downloads\zzy.pdf", output_path=r"C:\Users\Drago\Downloads\zzy_comment.pdf")
