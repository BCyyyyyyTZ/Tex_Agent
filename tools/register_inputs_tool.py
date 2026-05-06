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

    def _is_windows_abs_path(self, p: str) -> bool:
        if not p:
            return False
        # 盘符绝对路径: C:\... / C:/...
        if re.match(r"^[a-zA-Z]:[\\/]", p):
            return True
        # UNC 路径: \\server\share\... 或 //server/share/...
        if p.startswith("\\\\") or p.startswith("//"):
            return True
        return False

    def _is_posix_abs_path(self, p: str) -> bool:
        return bool(p and p.startswith("/"))

    def _looks_absolute_path(self, p: str) -> bool:
        p = (p or "").strip()
        if not p:
            return False
        # 兼容识别 Linux/Windows 两类绝对路径，不受当前运行平台影响
        return self._is_windows_abs_path(p) or self._is_posix_abs_path(p)

    def _clean_path_token(self, s: str) -> str:
        # 清理 JSON 片段 / 文本片段里常见的包裹符和尾随标点
        s = (s or "").strip()
        if not s:
            return ""
        # 去掉两侧引号（支持中英文引号）
        s = s.strip().strip('"').strip("'").strip("“").strip("”")
        # 去掉尾随逗号/分号
        s = s.rstrip(",;")
        return s.strip()

    def _abs(self, p: str) -> str:
        p = (p or "").strip().strip('"').strip("'")
        if not p:
            return ""
        if self._is_windows_abs_path(p):
            # 当前在 Windows 运行时规范化；否则原样保留（避免把 C:\... 误当相对路径）
            if os.name == "nt":
                return str(Path(p).resolve())
            return p
        if self._is_posix_abs_path(p):
            # 当前在 POSIX 运行时规范化；否则原样保留（避免 Windows 上错误拼接项目根）
            if os.name != "nt":
                return str(Path(p).resolve())
            return p
        path = Path(p)
        return str((self.project_root / path).resolve())

    def _default_output(self, pdf_abs_path: str) -> str:
        if not pdf_abs_path:
            return str((self.project_root / "storage" / "documents" / "checked.pdf").resolve())
        stem = Path(pdf_abs_path).stem
        return str((self.project_root / "storage" / "documents" / f"{stem}-checked.pdf").resolve())

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
            out["pdf_path"] = self._clean_path_token(inj_pdf)
        if inj_cl:
            out["checklist_path"] = self._clean_path_token(inj_cl)

        # 1) 优先解析显式键值，支持：
        #    pdf_path: "xxx"
        #    "pdf_path": "./storage/pdfs/中文 论文.pdf",
        kv_pattern = re.compile(
            r'["\']?(pdf_path|checklist_path|output_path|output)["\']?\s*[:=]\s*'
            r'(?:"([^"]+)"|\'([^\']+)\'|([^\n\r]+))',
            flags=re.IGNORECASE,
        )
        for m in kv_pattern.finditer(text or ""):
            key = (m.group(1) or "").lower()
            raw_val = m.group(2) or m.group(3) or m.group(4) or ""
            val = self._clean_path_token(raw_val)
            if not val:
                continue
            if key == "output":
                key = "output_path"
            if key not in out:
                out[key] = val
        # 2) 如果没取到，再做兜底后缀匹配（放宽到“直到引号/换行”）
        if "pdf_path" not in out:
            pdf_match = re.search(r'([^\n\r"\']+?\.pdf)\b', text, flags=re.IGNORECASE)
            if pdf_match:
                out["pdf_path"] = self._clean_path_token(pdf_match.group(1))
        if "checklist_path" not in out:
            cl_match = re.search(
                r'([^\n\r"\']+?\.(?:md|txt|json|ya?ml))\b',
                text,
                flags=re.IGNORECASE,
            )
            if cl_match:
                out["checklist_path"] = self._clean_path_token(cl_match.group(1))
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

            pdf_path = self._clean_path_token(str(data.get("pdf_path", "") or ""))
            checklist_path = self._clean_path_token(str(data.get("checklist_path", "") or ""))
            output_path = self._clean_path_token(str(data.get("output_path", "") or ""))

            # 如果是 basename，尝试在 storage 下解析
            if pdf_path and not self._looks_absolute_path(pdf_path) and "/" not in pdf_path and "\\" not in pdf_path:
                p = self._search_storage_by_basename(pdf_path, is_pdf=True)
                if p:
                    pdf_path = p
            if checklist_path and not self._looks_absolute_path(checklist_path) and "/" not in checklist_path and "\\" not in checklist_path:
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