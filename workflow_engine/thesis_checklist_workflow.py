from __future__ import annotations

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
    title: str
    content: str


def split_checklist_by_primary_headings(markdown_text: str) -> list[ChecklistSection]:
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
        "1. page_idx 为问题在论文中的页码，从 1 开始。\n"
        "2. text 必须在字符串层面严格匹配 PDF 原文内容，尽量选择不包含特殊格式（上标/下标/角标/公式）的短片段。\n"
        "3. comment 为不符合原因，表述简洁明确。\n"
        "4. 输出必须是可被 json.loads 直接解析的 JSON。\n"
        "5. 不要输出除 TOOL_CALL 格式外的任何内容。\n"
    )


class ThesisChecklistWorkflow:
    def __init__(
        self,
        *,
        checklist_path: str,
        llm_client: Optional[LlmClientLike] = None,
        pdf_comment_tool: Optional[PdfCommentTool] = None,
        #model_name: str = "gemini-3.1-flash-lite-preview",
        model_name: str = "gemini-3-flash-preview",
        #model_name: str = "gemini-2.5-flash",
        api_key: str = "",
        temperature: float = 0.2,
    ):
        self.checklist_path = str(Path(checklist_path).resolve())

        with open(self.checklist_path, "r", encoding="utf-8") as f:
            md = f.read()
        self.sections = split_checklist_by_primary_headings(md)


        if llm_client is None:
            from agents.base_agent import GeminiClient

            llm_client = GeminiClient(model_name=model_name, api_key=api_key, temperature=temperature)
        self.llm_client = llm_client

        self.pdf_comment_tool = pdf_comment_tool or PdfCommentTool()

    def build(self) -> Workflow:

        def prepare_pdf(msg: WorkflowMessage, _ctx: WorkflowContext) -> WorkflowMessage:
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
