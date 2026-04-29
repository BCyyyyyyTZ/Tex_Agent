import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from tools.base_tool import BaseTool
from core.message import ToolResult


class RegisterInputsTool(BaseTool):
    """
    解析工作流输入，提取：
    - pdf_abs_path
    - checklist_abs_path
    - output_pdf_abs_path

    支持来源：
    1) web-ui 注入块:
       - [PDF] <abs_path>
       - [Checklist] <abs_path>
    2) JSON 字符串 / dict:
       {"pdf_path":"...", "checklist_path":"...", "output_path":"..."}
    3) 普通文本里的路径/文件名（.pdf / .md/.txt/.json/.yaml/.yml）
    """

    def __init__(self):
        super().__init__(
            name="register_inputs",
            description="解析并注册 PDF/checklist/output 路径为绝对路径。",
            input_schema={"payload": "用户输入文本或 JSON/dict"},
        )
        self.project_root = Path(__file__).resolve().parent.parent
        self.storage_pdfs = self.project_root / "storage" / "pdfs"
        self.storage_checklists = self.project_root / "storage" / "checklists"

    def _abs(self, p: str) -> str:
        p = (p or "").strip().strip('"').strip("'")
        if not p:
            return ""
        path = Path(p)
        if path.is_absolute():
            return str(path.resolve())
        return str((self.project_root / path).resolve())

    def _default_output(self, pdf_abs_path: str) -> str:
        if not pdf_abs_path:
            return str((self.project_root / "doc" / "checked.pdf").resolve())
        stem = Path(pdf_abs_path).stem
        return str((self.project_root / "doc" / f"{stem}-checked.pdf").resolve())

    def _parse_injected_block(self, text: str) -> Tuple[str, str]:
        pdf_path = ""
        checklist_path = ""
        pat = re.compile(r"^\s*-\s*\[(PDF|Checklist)\]\s+(.+?)\s*$", flags=re.MULTILINE)
        for m in pat.finditer(text or ""):
            kind = (m.group(1) or "").strip().lower()
            path = (m.group(2) or "").strip()
            if kind == "pdf" and not pdf_path:
                pdf_path = path
            elif kind == "checklist" and not checklist_path:
                checklist_path = path
        return pdf_path, checklist_path

    def _search_storage_by_basename(self, name: str, is_pdf: bool) -> str:
        name = Path(name).name
        if not name:
            return ""
        base_dir = self.storage_pdfs if is_pdf else self.storage_checklists
        cand = base_dir / name
        if cand.is_file():
            return str(cand.resolve())
        return ""

    def _parse_from_text(self, text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}

        # 先尝试 web 注入块
        inj_pdf, inj_cl = self._parse_injected_block(text)
        if inj_pdf:
            out["pdf_path"] = inj_pdf
        if inj_cl:
            out["checklist_path"] = inj_cl

        # 再尝试普通路径提取（未命中时）
        if "pdf_path" not in out:
            pdf_match = re.search(r'([^\s"\']+\.pdf)\b', text, flags=re.IGNORECASE)
            if pdf_match:
                out["pdf_path"] = pdf_match.group(1)

        if "checklist_path" not in out:
            cl_match = re.search(
                r'([^\s"\']+\.(?:md|txt|json|ya?ml))\b',
                text,
                flags=re.IGNORECASE,
            )
            if cl_match:
                out["checklist_path"] = cl_match.group(1)

        # output_path
        out_match = re.search(
            r"(?:output_path|output)\s*[:=]\s*([^\n\r]+)",
            text,
            flags=re.IGNORECASE,
        )
        if out_match:
            out["output_path"] = out_match.group(1).strip()

        return out

    def run(self, payload: Union[str, Dict[str, Any]]) -> ToolResult:
        try:
            data: Dict[str, Any] = {}

            if isinstance(payload, dict):
                data = dict(payload)
            elif isinstance(payload, str):
                raw = payload.strip()
                if raw.startswith("{") and raw.endswith("}"):
                    try:
                        data = json.loads(raw)
                    except Exception:
                        data = self._parse_from_text(raw)
                else:
                    data = self._parse_from_text(raw)
            else:
                return ToolResult(success=False, output="", error=f"不支持的 payload 类型: {type(payload)}")

            pdf_path = str(data.get("pdf_path", "") or "").strip()
            checklist_path = str(data.get("checklist_path", "") or "").strip()
            output_path = str(data.get("output_path", "") or "").strip()

            # 如果是 basename，尝试在 storage 下解析
            if pdf_path and not Path(pdf_path).is_absolute() and "/" not in pdf_path and "\\" not in pdf_path:
                p = self._search_storage_by_basename(pdf_path, is_pdf=True)
                if p:
                    pdf_path = p
            if checklist_path and not Path(checklist_path).is_absolute() and "/" not in checklist_path and "\\" not in checklist_path:
                c = self._search_storage_by_basename(checklist_path, is_pdf=False)
                if c:
                    checklist_path = c

            pdf_abs = self._abs(pdf_path) if pdf_path else ""
            checklist_abs = self._abs(checklist_path) if checklist_path else ""
            output_abs = self._abs(output_path) if output_path else self._default_output(pdf_abs)

            warnings = []
            if not pdf_abs:
                warnings.append("未解析到 PDF 路径")
            elif not os.path.exists(pdf_abs):
                warnings.append(f"PDF 不存在: {pdf_abs}")

            if not checklist_abs:
                warnings.append("未解析到 checklist 路径")
            elif not os.path.exists(checklist_abs):
                warnings.append(f"checklist 不存在: {checklist_abs}")

            out_obj = {
                "pdf_abs_path": pdf_abs,
                "checklist_abs_path": checklist_abs,
                "output_pdf_abs_path": output_abs,
                "warnings": warnings,
            }

            hard_errors = []
            if not pdf_abs:
                hard_errors.append("未解析到 PDF 路径")
            if not checklist_abs:
                hard_errors.append("未解析到 checklist 路径")
            if hard_errors:
                return ToolResult(
                    success=False,
                    output=json.dumps(out_obj, ensure_ascii=False),
                    error="; ".join(hard_errors),
                    metadata=out_obj,
                )

            return ToolResult(
                success=True,
                output=json.dumps(out_obj, ensure_ascii=False),
                metadata=out_obj,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))