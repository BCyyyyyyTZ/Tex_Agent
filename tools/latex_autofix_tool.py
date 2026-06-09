import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LatexError:
    message: str
    file: str = ""
    line: int = 0
    context: str = ""
    raw: str = ""


class LatexAutoFixTool(BaseTool):
    def __init__(
        self,
        *,
        model_name: str = "gemini-3.1-flash-lite",
        api_key: str = "",
        temperature: float = 0.2,
        use_llm: bool = True,
    ):
        super().__init__(
            name="latex_autofix",
            description="传入 LaTeX 项目目录与入口 tex 文件（或直接传主文件路径），自动编译并根据报错迭代修复副本，直到不再报错，返回修改历史与副本路径。",
            input_schema={
                "project_dir": "可选，LaTeX 项目目录，例如 'paper'（与 tex_file 配套使用）",
                "tex_file": "可选，需要编译的入口 tex 文件（相对 project_dir），例如 'main.tex' 或 'src/main.tex'",
                "latex_path": "可选，LaTeX 主文件路径，例如 'paper/main.tex'（兼容旧用法；传了它可不传 project_dir/tex_file）",
                "output_dir": "可选，输出工作目录，例如 'outputs/latex_autofix'",
                "max_iters": "可选，最大修复轮次，默认 8",
                "engine": "可选，编译引擎：auto|pdflatex|xelatex|lualatex，默认 auto",
                "use_llm": "可选，是否启用 LLM 辅助修复（需要配置 API key），默认 True",
            },
        )
        self.model_name = model_name
        self.api_key = api_key
        self.temperature = float(temperature)
        self.use_llm = bool(use_llm)

    def _resolve_api_key(self, api_key: str) -> str:
        return (
            api_key
            or self.api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        )

    def _load_gemini_client_class(self):
        base_agent_path = Path(__file__).resolve().parents[1] / "agents" / "base_agent.py"
        spec = spec_from_file_location("_tex_agent_base_agent", str(base_agent_path))
        if spec is None or spec.loader is None:
            raise RuntimeError("无法加载 GeminiClient")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        GeminiClient = getattr(mod, "GeminiClient", None)
        if GeminiClient is None:
            raise RuntimeError("未找到 GeminiClient")
        return GeminiClient

    def _decode_bytes(self, b: bytes) -> str:
        if not b:
            return ""
        for enc in ("utf-8", "gbk", "utf-8-sig"):
            try:
                return b.decode(enc)
            except Exception:
                continue
        return b.decode("utf-8", errors="replace")

    def _which(self, exe: str) -> Optional[str]:
        p = shutil.which(exe)
        if p:
            return p

        exe_name = exe
        if not exe_name.lower().endswith(".exe"):
            exe_name = exe_name + ".exe"

        candidates: list[Path] = []
        local = os.getenv("LOCALAPPDATA") or ""
        if local:
            candidates.append(Path(local) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64")
            candidates.append(Path(local) / "MiKTeX" / "miktex" / "bin" / "x64")

        for env_key in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.getenv(env_key) or ""
            if root:
                candidates.append(Path(root) / "MiKTeX" / "miktex" / "bin" / "x64")

        for d in candidates:
            try:
                fp = (d / exe_name).resolve()
            except Exception:
                continue
            if fp.exists():
                return str(fp)
        return None

    def _has_any_latex_engine(self) -> bool:
        return any(self._which(x) for x in ("latexmk", "pdflatex", "xelatex", "lualatex", "latex"))

    def _project_copy(self, src_dir: Path, dst_dir: Path, extra_ignore_top: Optional[set[str]] = None) -> None:
        extra = set(extra_ignore_top or set())

        def _ignore(_: str, names: list[str]) -> set[str]:
            deny = {
                ".git",
                ".hg",
                ".svn",
                "__pycache__",
                ".venv",
                "venv",
                "node_modules",
                "build",
                "dist",
                "outputs",
                ".pytest_cache",
                ".mypy_cache",
            }
            deny |= extra
            ignored: set[str] = set()
            for n in names:
                if n in deny:
                    ignored.add(n)
            return ignored

        if dst_dir.exists():
            shutil.rmtree(dst_dir, ignore_errors=True)
        shutil.copytree(src_dir, dst_dir, ignore=_ignore)

    def _compile(
        self,
        *,
        work_dir: Path,
        main_tex: Path,
        engine: str,
        shell_escape: bool,
        timeout_s: int,
    ) -> dict[str, Any]:
        build_dir = work_dir / "_build"
        build_dir.mkdir(parents=True, exist_ok=True)

        try:
            main_name = str(main_tex.resolve().relative_to(work_dir.resolve()))
        except Exception:
            main_name = main_tex.name
        latexmk = self._which("latexmk")
        cmd: list[str]

        base_flags = ["-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
        se_flag = ["-shell-escape"] if shell_escape else []

        eng = (engine or "auto").strip().lower()
        if eng not in {"auto", "pdflatex", "xelatex", "lualatex"}:
            eng = "auto"

        if latexmk:
            cmd = [
                latexmk,
                "-pdf",
                "-outdir=" + str(build_dir),
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
            ]
            if eng == "xelatex":
                cmd.append("-xelatex")
            elif eng == "lualatex":
                cmd.append("-lualatex")
            cmd.extend(se_flag)
            cmd.append(main_name)
        else:
            exe = None
            if eng in {"auto", "pdflatex"}:
                exe = self._which("pdflatex") or self._which("latex")
                eng = "pdflatex"
            if exe is None and eng in {"auto", "xelatex"}:
                exe = self._which("xelatex")
                eng = "xelatex"
            if exe is None and eng in {"auto", "lualatex"}:
                exe = self._which("lualatex")
                eng = "lualatex"

            if not exe:
                return {
                    "success": False,
                    "returncode": -1,
                    "engine": eng,
                    "command": "",
                    "stdout": "",
                    "stderr": "未找到 latexmk/pdflatex/xelatex/lualatex 可执行文件",
                    "log_path": "",
                    "pdf_path": "",
                }
            cmd = [exe, *base_flags, "-output-directory=" + str(build_dir), *se_flag, main_name]

        t0 = time.time()
        try:
            p = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=False,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -2,
                "engine": eng,
                "command": " ".join(cmd),
                "stdout": "",
                "stderr": f"编译超时（{timeout_s}s）",
                "log_path": "",
                "pdf_path": "",
                "duration_s": time.time() - t0,
            }

        stdout = self._decode_bytes(p.stdout)
        stderr = self._decode_bytes(p.stderr)
        log_path = build_dir / (main_tex.stem + ".log")
        pdf_path = build_dir / (main_tex.stem + ".pdf")
        return {
            "success": p.returncode == 0 and pdf_path.exists(),
            "returncode": int(p.returncode),
            "engine": eng,
            "command": " ".join(cmd),
            "stdout": stdout,
            "stderr": stderr,
            "log_path": str(log_path) if log_path.exists() else "",
            "pdf_path": str(pdf_path) if pdf_path.exists() else "",
            "duration_s": time.time() - t0,
        }

    def _extract_first_error(self, text: str) -> LatexError:
        s = (text or "").strip("\ufeff")
        if not s:
            return LatexError(message="未知错误", raw="")

        lines = s.splitlines()

        file_line = ""
        file_no = 0
        msg = ""
        ctx = ""

        file_line_re = re.compile(r"^(?P<file>[^:\n]+?\.(?:tex|sty|cls|bib|bst)):(?P<line>\d+):\s*(?P<rest>.*)$")
        latex_err_re = re.compile(r"^!\s+(?P<msg>.+?)\s*$")
        ldot_re = re.compile(r"^l\.(?P<line>\d+)\s*(?P<context>.*)$")

        idx = 0
        while idx < len(lines):
            m = file_line_re.match(lines[idx].strip())
            if m:
                file_line = (m.group("file") or "").strip()
                try:
                    file_no = int(m.group("line") or "0")
                except Exception:
                    file_no = 0
                if not msg:
                    rest = (m.group("rest") or "").strip()
                    if rest:
                        msg = rest
                break
            idx += 1

        i = 0
        while i < len(lines):
            m = latex_err_re.match(lines[i].strip())
            if m:
                msg = (m.group("msg") or "").strip()
                j = i + 1
                while j < min(len(lines), i + 20):
                    lm = ldot_re.match(lines[j].strip())
                    if lm:
                        if file_no <= 0:
                            try:
                                file_no = int(lm.group("line") or "0")
                            except Exception:
                                file_no = 0
                        ctx = (lm.group("context") or "").strip()
                        break
                    j += 1
                raw = "\n".join(lines[i : min(len(lines), i + 30)]).strip()
                return LatexError(message=msg or "LaTeX 编译错误", file=file_line, line=file_no, context=ctx, raw=raw)
            i += 1

        return LatexError(message=msg or "LaTeX 编译错误", file=file_line, line=file_no, context=ctx, raw="\n".join(lines[:50]).strip())

    def _safe_relpath(self, p: Path, base: Path) -> str:
        try:
            return str(p.resolve().relative_to(base.resolve())).replace("\\", "/")
        except Exception:
            return str(p).replace("\\", "/")

    def _find_target_file(self, work_dir: Path, err_file: str, fallback: Path) -> Path:
        if err_file:
            candidate = (work_dir / err_file).resolve() if not Path(err_file).is_absolute() else Path(err_file).resolve()
            try:
                candidate.relative_to(work_dir.resolve())
            except Exception:
                candidate = work_dir / Path(err_file).name
            if candidate.exists():
                return candidate
            by_name = list(work_dir.rglob(Path(err_file).name))
            if by_name:
                return by_name[0]
        return fallback

    def _read_lines(self, p: Path) -> list[str]:
        try:
            return p.read_text(encoding="utf-8").splitlines(True)
        except Exception:
            return p.read_text(encoding="utf-8", errors="replace").splitlines(True)

    def _write_lines(self, p: Path, lines: list[str]) -> None:
        p.write_text("".join(lines), encoding="utf-8")

    def _insert_package(self, lines: list[str], pkg: str) -> tuple[bool, list[str]]:
        joined = "".join(lines)
        if re.search(rf"\\usepackage(?:\[[^\]]*\])?\{{\s*{re.escape(pkg)}\s*\}}", joined):
            return False, lines
        begin_doc = None
        for i, ln in enumerate(lines):
            if re.search(r"\\begin\{document\}", ln):
                begin_doc = i
                break
        if begin_doc is None:
            return False, lines
        insert_at = begin_doc
        while insert_at > 0 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        new_lines = list(lines)
        new_lines.insert(insert_at, f"\\usepackage{{{pkg}}}\n")
        return True, new_lines

    def _escape_underscores_on_line(self, line: str) -> tuple[bool, str]:
        if "\\_" in line:
            return False, line
        if "$" in line:
            return False, line
        if "\\url{" in line or "\\href{" in line:
            return False, line
        new = re.sub(r"(?<!\\)_", r"\\_", line)
        if new != line:
            return True, new
        return False, line

    def _deterministic_fix(
        self,
        *,
        err: LatexError,
        work_dir: Path,
        main_tex: Path,
        state: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        msg = (err.message or "").strip()
        raw = err.raw or ""

        if re.search(r"File `.+?\.sty' not found", msg, flags=re.IGNORECASE) or re.search(
            r"File `.+?\.sty' not found", raw, flags=re.IGNORECASE
        ):
            return None

        if re.search(r"must be invoked with the -shell-escape flag", raw, flags=re.IGNORECASE) or re.search(
            r"shell-escape", msg, flags=re.IGNORECASE
        ):
            if not state.get("shell_escape", False):
                state["shell_escape"] = True
                return {
                    "type": "compile_option",
                    "change": "enable_shell_escape",
                    "reason": "minted 或外部程序需要 -shell-escape",
                }
            return None

        if re.search(r"Unicode character", msg, flags=re.IGNORECASE) or re.search(r"inputenc.*Unicode", raw, flags=re.IGNORECASE):
            if state.get("engine") != "xelatex":
                state["engine"] = "xelatex"
                return {
                    "type": "compile_option",
                    "change": "switch_engine",
                    "engine": "xelatex",
                    "reason": "检测到 Unicode 报错，切换到 xelatex",
                }
            return None

        if re.search(r"Undefined control sequence", msg, flags=re.IGNORECASE) or re.search(
            r"Undefined control sequence", raw, flags=re.IGNORECASE
        ):
            target_for_probe = self._find_target_file(work_dir, err.file, main_tex)
            cmd = ""
            probe = err.context or ""
            if not probe and err.line > 0:
                try:
                    lines = self._read_lines(target_for_probe)
                    probe = lines[err.line - 1] if 0 < err.line <= len(lines) else ""
                except Exception:
                    probe = ""
            m = re.search(r"(\\[A-Za-z@]+)", probe)
            if m:
                cmd = m.group(1)
            pkg_map = {
                "\\includegraphics": "graphicx",
                "\\toprule": "booktabs",
                "\\midrule": "booktabs",
                "\\bottomrule": "booktabs",
                "\\mathbb": "amssymb",
                "\\bm": "bm",
                "\\SI": "siunitx",
                "\\si": "siunitx",
                "\\url": "url",
                "\\href": "hyperref",
                "\\autoref": "hyperref",
                "\\textcolor": "xcolor",
                "\\geometry": "geometry",
                "\\citep": "natbib",
                "\\citet": "natbib",
                "\\todo": "todonotes",
            }
            pkg = pkg_map.get(cmd)
            if pkg:
                target = main_tex
                lines = self._read_lines(target)
                changed, new_lines = self._insert_package(lines, pkg)
                if not changed:
                    return None
                before = "".join(lines[: min(len(lines), 200)])
                after = "".join(new_lines[: min(len(new_lines), 200)])
                self._write_lines(target, new_lines)
                return {
                    "type": "edit",
                    "path": self._safe_relpath(target, work_dir),
                    "action": "insert_usepackage",
                    "package": pkg,
                    "command": cmd,
                    "reason": "Undefined control sequence，尝试补齐常用宏包",
                    "before_head": before,
                    "after_head": after,
                }
            return None

        if re.search(r"Missing \$ inserted", msg, flags=re.IGNORECASE) or re.search(
            r"Missing \$ inserted", raw, flags=re.IGNORECASE
        ):
            target = self._find_target_file(work_dir, err.file, main_tex)
            lines = self._read_lines(target)
            line_no = err.line
            if line_no <= 0 or line_no > len(lines):
                return None
            old_line = lines[line_no - 1]
            changed, new_line = self._escape_underscores_on_line(old_line)
            if not changed:
                return None
            new_lines = list(lines)
            new_lines[line_no - 1] = new_line
            self._write_lines(target, new_lines)
            return {
                "type": "edit",
                "path": self._safe_relpath(target, work_dir),
                "action": "escape_underscores",
                "line": line_no,
                "reason": "Missing $ inserted，尝试对文本下划线进行转义",
                "before": old_line.rstrip("\n"),
                "after": new_line.rstrip("\n"),
            }

        return None

    def _apply_llm_edits_to_file(self, target: Path, edits: list[dict[str, Any]], raw: str) -> Optional[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for e in edits:
            if not isinstance(e, dict):
                continue
            try:
                sline = int(e.get("start_line") or 0)
                eline = int(e.get("end_line") or 0)
            except Exception:
                continue
            if sline <= 0 or eline <= 0 or eline < sline:
                continue
            replacement = str(e.get("replacement") or "")
            reason = str(e.get("reason") or "")[:2000]
            normalized.append({"start_line": sline, "end_line": eline, "replacement": replacement, "reason": reason})

        if not normalized:
            return None

        normalized.sort(key=lambda x: (x["start_line"], x["end_line"]))
        for i in range(1, len(normalized)):
            if normalized[i - 1]["end_line"] >= normalized[i]["start_line"]:
                return None

        f_lines = self._read_lines(target)
        for e in normalized:
            if e["start_line"] > len(f_lines) + 1:
                return None

        applied: list[dict[str, Any]] = []
        new_lines = list(f_lines)
        for e in sorted(normalized, key=lambda x: (x["start_line"], x["end_line"]), reverse=True):
            sline = int(e["start_line"])
            eline = min(int(e["end_line"]), len(new_lines))
            before_block = "".join(new_lines[sline - 1 : eline])
            rep_lines = e["replacement"].splitlines(True)
            if e["replacement"] and rep_lines and not rep_lines[-1].endswith("\n"):
                rep_lines[-1] = rep_lines[-1] + "\n"
            new_lines = list(new_lines[: sline - 1]) + rep_lines + list(new_lines[eline:])
            after_block = "".join(rep_lines)
            applied.append(
                {
                    "start_line": sline,
                    "end_line": eline,
                    "reason": e["reason"],
                    "before": before_block,
                    "after": after_block,
                }
            )

        applied.reverse()
        if new_lines == f_lines:
            return None
        self._write_lines(target, new_lines)
        return {
            "type": "edit",
            "path": str(target),
            "action": "llm_edits",
            "edits": applied,
            "llm_raw": raw[:4000],
        }

    def _llm_fix(
        self,
        *,
        err: LatexError,
        main_tex: Path,
        work_dir: Path,
    ) -> Optional[dict[str, Any]]:
        resolved_api_key = self._resolve_api_key("")
        if not resolved_api_key:
            return {"type": "llm_stop", "reason": "未配置 GEMINI_API_KEY 或 GOOGLE_API_KEY，无法进行 LLM 修复", "llm_raw": ""}
        target = self._find_target_file(work_dir, err.file, main_tex)
        if target.suffix.lower() != ".tex":
            return {"type": "llm_stop", "reason": "LLM 修复仅支持修改 .tex 文件", "llm_raw": ""}

        lines = self._read_lines(target)
        ln = err.line if err.line > 0 else 1
        start = max(1, ln - 8)
        end = min(len(lines), ln + 8)
        snippet = "".join([f"{i:>4}: {lines[i-1]}" for i in range(start, end + 1)])
        target_display = self._safe_relpath(target, work_dir)

        prompt = (
            "你是 LaTeX 编译报错修复助手。\n"
            "目标：用最小改动修复编译错误，尽量不改变语义。\n"
            f"只允许修改文件：{target_display}。\n"
            "输出必须是严格 JSON，禁止任何解释文字。\n\n"
            f"你会收到 {Path(target_display).name} 作为上传文件（LaTeX 源文件）。\n"
            "请按以下 JSON 结构返回多个修改建议（可 1 个或多个），或返回停止原因：\n"
            'A) {"action":"edits","edits":[{"start_line":修改起始行(1-based),"end_line":修改结束行(1-based),"replacement":"替换内容(可含\\n)","reason":"原因"}]}\n'
            'B) {"action":"stop","reason":"无法安全自动修复的原因"}\n\n'
            f"入口文件: {self._safe_relpath(main_tex, work_dir)}\n"
            f"当前待修复文件: {target_display}\n"
            f"当前错误摘要: {err.message}\n"
            f"错误定位: {target_display}:{err.line}\n"
            "错误原始片段:\n"
            f"{err.raw}\n\n"
            f"待修复文件片段（带行号）:\n{snippet}\n"
        )

        GeminiClient = self._load_gemini_client_class()
        llm = GeminiClient(model_name=self.model_name, api_key=resolved_api_key, temperature=self.temperature)
        upload_path = target
        if upload_path.suffix.lower() == ".tex":
            try:
                alt = upload_path.with_suffix(upload_path.suffix + ".txt")
                alt.write_text(upload_path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
                upload_path = alt
            except Exception:
                upload_path = target
        try:
            raw = llm.response(prompt, file_paths=str(upload_path), file_mime_types="text/plain")
        except TypeError:
            raw = llm.response(prompt, file_paths=str(upload_path))
        try:
            data = json.loads(raw)
        except Exception:
            return None

        edits: list[dict[str, Any]] = []
        stop_reason = ""
        if isinstance(data, dict):
            if data.get("action") == "stop":
                stop_reason = str(data.get("reason") or "")[:2000]
            elif isinstance(data.get("edits"), list):
                for e in data.get("edits") or []:
                    if isinstance(e, dict):
                        edits.append(e)
            elif data.get("action") == "edit":
                edits.append(data)
        elif isinstance(data, list):
            for e in data:
                if isinstance(e, dict):
                    edits.append(e)

        if stop_reason:
            return {"type": "llm_stop", "reason": stop_reason, "llm_raw": raw[:4000]}
        if not edits:
            return None
        action = self._apply_llm_edits_to_file(target, edits, raw)
        if isinstance(action, dict):
            action["path"] = self._safe_relpath(target, work_dir)
        return action

    def run(
        self,
        latex_path: str = "",
        project_dir: str = "",
        tex_file: str = "",
        output_dir: str = "",
        max_iters: int = 8,
        engine: str = "auto",
        use_llm: Optional[bool] = None,
    ) -> ToolResult:
        try:
            src_project = None
            src_main = None

            if latex_path:
                src_main = Path(latex_path).expanduser()
                if not src_main.is_absolute():
                    src_main = (Path.cwd() / src_main).resolve()
                if not src_main.exists():
                    return ToolResult(success=False, output="", error=f"文件不存在: {src_main}")
                if src_main.suffix.lower() != ".tex":
                    return ToolResult(success=False, output="", error="latex_path 必须指向 .tex 文件")
                src_project = src_main.parent
            else:
                if not project_dir:
                    return ToolResult(success=False, output="", error="project_dir 不能为空（或改用 latex_path）")
                if not tex_file:
                    return ToolResult(success=False, output="", error="tex_file 不能为空（或改用 latex_path）")
                src_project = Path(project_dir).expanduser()
                if not src_project.is_absolute():
                    src_project = (Path.cwd() / src_project).resolve()
                if not src_project.exists() or not src_project.is_dir():
                    return ToolResult(success=False, output="", error=f"项目目录不存在: {src_project}")
                src_main = (src_project / tex_file).resolve()
                try:
                    src_main.relative_to(src_project.resolve())
                except Exception:
                    return ToolResult(success=False, output="", error="tex_file 必须位于 project_dir 目录内")
                if not src_main.exists():
                    return ToolResult(success=False, output="", error=f"入口 tex 不存在: {src_main}")
                if src_main.suffix.lower() != ".tex":
                    return ToolResult(success=False, output="", error="tex_file 必须指向 .tex 文件")

            assert src_project is not None and src_main is not None

            src_project = src_project.resolve()
            src_main = src_main.resolve()

            rel_main = None
            try:
                rel_main = src_main.relative_to(src_project)
            except Exception:
                rel_main = Path(src_main.name)

            max_iters = int(max_iters or 0)
            if max_iters <= 0:
                max_iters = 8


            use_llm_eff = self.use_llm if use_llm is None else bool(use_llm)

            base_out = Path(output_dir) if output_dir else (Path(__file__).resolve().parents[1] / "outputs" / "latex_autofix")
            base_out.mkdir(parents=True, exist_ok=True)

            ts = time.strftime("%Y%m%d_%H%M%S")
            job_dir = (base_out / f"{src_main.stem}_{ts}").resolve()
            work_dir = job_dir / "work"
            job_dir.mkdir(parents=True, exist_ok=True)

            extra_ignore: set[str] = set()
            try:
                rel = base_out.resolve().relative_to(src_project.resolve())
                if rel.parts:
                    extra_ignore.add(rel.parts[0])
            except Exception:
                pass
            self._project_copy(src_project, work_dir, extra_ignore_top=extra_ignore)
            main_tex = (work_dir / rel_main).resolve()
            if not main_tex.exists():
                return ToolResult(success=False, output="", error="复制副本失败：未找到主文件副本")

            history: list[dict[str, Any]] = []
            state: dict[str, Any] = {"engine": (engine or "auto").strip().lower(), "shell_escape": False}

            last_compile: dict[str, Any] = {}
            for i in range(1, max_iters + 1):
                c = self._compile(
                    work_dir=work_dir,
                    main_tex=main_tex,
                    engine=str(state.get("engine") or "auto"),
                    shell_escape=bool(state.get("shell_escape", False)),
                    timeout_s=90,
                )
                last_compile = c
                if int(c.get("returncode") or 0) == -1:
                    payload = {
                        "status": "failed",
                        "work_dir": str(work_dir),
                        "main_tex": str(main_tex),
                        "engine": str(state.get("engine") or ""),
                        "reason": "未找到可用的 LaTeX 编译器（latexmk/pdflatex/xelatex/lualatex）",
                        "last_compile": {
                            "returncode": c.get("returncode"),
                            "command": c.get("command"),
                            "stdout": str(c.get("stdout") or "")[:4000],
                            "stderr": str(c.get("stderr") or "")[:4000],
                        },
                        "history": history,
                    }
                    return ToolResult(success=False, output=json.dumps(payload, ensure_ascii=False, indent=2), error=payload["reason"], metadata=payload)
                if c.get("success"):
                    payload = {
                        "status": "success",
                        "work_dir": str(work_dir),
                        "main_tex": str(main_tex),
                        "pdf_path": str(c.get("pdf_path") or ""),
                        "engine": str(c.get("engine") or ""),
                        "iterations": i - 1,
                        "history": history,
                    }
                    return ToolResult(success=True, output=json.dumps(payload, ensure_ascii=False, indent=2), metadata=payload)

                combined = "\n".join([str(c.get("stdout") or ""), str(c.get("stderr") or "")]).strip()
                err = self._extract_first_error(combined)
                step: dict[str, Any] = {
                    "iter": i,
                    "error": {
                        "message": err.message,
                        "file": err.file,
                        "line": err.line,
                        "context": err.context,
                        "raw": err.raw[:4000],
                    },
                    "compile": {
                        "engine": c.get("engine"),
                        "command": c.get("command"),
                        "returncode": c.get("returncode"),
                        "log_path": c.get("log_path"),
                    },
                    "action": None,
                }

                action = self._deterministic_fix(err=err, work_dir=work_dir, main_tex=main_tex, state=state)
                if action is None and use_llm_eff:
                    action = self._llm_fix(err=err, main_tex=main_tex, work_dir=work_dir)
                step["action"] = action
                history.append(step)

                if action is None:
                    payload = {
                        "status": "failed",
                        "work_dir": str(work_dir),
                        "main_tex": str(main_tex),
                        "engine": str(state.get("engine") or ""),
                        "reason": "无法自动生成安全的修复动作",
                        "last_error": step["error"],
                        "history": history,
                        "last_compile": {
                            "returncode": c.get("returncode"),
                            "command": c.get("command"),
                            "stdout": str(c.get("stdout") or "")[:4000],
                            "stderr": str(c.get("stderr") or "")[:4000],
                        },
                    }
                    return ToolResult(success=False, output=json.dumps(payload, ensure_ascii=False, indent=2), error=payload["reason"], metadata=payload)

                if action.get("type") == "llm_stop":
                    payload = {
                        "status": "failed",
                        "work_dir": str(work_dir),
                        "main_tex": str(main_tex),
                        "engine": str(state.get("engine") or ""),
                        "reason": "LLM 判断无法安全自动修复",
                        "last_error": step["error"],
                        "history": history,
                    }
                    return ToolResult(success=False, output=json.dumps(payload, ensure_ascii=False, indent=2), error=payload["reason"], metadata=payload)

            payload = {
                "status": "failed",
                "work_dir": str(work_dir),
                "main_tex": str(main_tex),
                "engine": str(state.get("engine") or ""),
                "reason": f"超过最大迭代次数（{max_iters}）仍未编译通过",
                "history": history,
                "last_compile": {
                    "returncode": last_compile.get("returncode"),
                    "command": last_compile.get("command"),
                    "stdout": str(last_compile.get("stdout") or "")[:4000],
                    "stderr": str(last_compile.get("stderr") or "")[:4000],
                },
            }
            return ToolResult(success=False, output=json.dumps(payload, ensure_ascii=False, indent=2), error=payload["reason"], metadata=payload)
        except Exception as e:
            logger.error(f"LatexAutoFixTool 失败: {e}")
            return ToolResult(success=False, output="", error=f"LatexAutoFixTool 失败: {e}")


def _assert_file_ok(path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise AssertionError(f"文件未生成: {p}")
    if p.stat().st_size <= 0:
        raise AssertionError(f"文件为空: {p}")


def _run_self_test(output_dir: Optional[str] = None) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    test_project_dir = repo_root / "latex_autofix_llm_test_project"
    test_project_llm = test_project_dir / "main.tex"
    if not test_project_llm.exists():
        raise AssertionError(f"测试工程不存在: {test_project_llm}")

    tool = LatexAutoFixTool(use_llm=True)
    if not tool._has_any_latex_engine():
        print("latex_autofix 自测跳过：未检测到 latexmk/pdflatex/xelatex/lualatex")
        return

    base = Path(output_dir) if output_dir else (repo_root / "outputs" / "latex_autofix_tool_test")
    base.mkdir(parents=True, exist_ok=True)

    r = tool.run(
        project_dir=str(test_project_dir),
        tex_file="main.tex",
        output_dir=str(base),
        max_iters=20,
        engine="auto",
        use_llm=True,
    )
    payload = r.metadata or {}
    if not payload and (r.output or "").strip().startswith("{"):
        try:
            payload = json.loads(r.output)
        except Exception:
            payload = {}

    print("latex_autofix 实际场景自测结果")
    print(f"success: {r.success}")
    if r.error:
        print(f"error: {r.error}")
    if payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(r.output)


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else None
    _run_self_test(out_dir)