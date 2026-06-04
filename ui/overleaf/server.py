"""
Overleaf-style LaTeX Editor with Agent Support.
Not modifying ui.web.server or latex.ghost_cli.
启动: python -m ui.overleaf.server
"""
from __future__ import annotations





import json


import base64


import os


import shutil


import uuid


import zipfile


from pathlib import Path


from typing import Any, Dict, List, Optional





from fastapi import FastAPI, File, HTTPException, UploadFile


from fastapi.middleware.cors import CORSMiddleware


from fastapi.responses import FileResponse, Response


from fastapi.staticfiles import StaticFiles


from pydantic import BaseModel





OVERLEAF_DIR = Path(__file__).resolve().parents[2] / "storage" / "overleaf_projects"


TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "storage" / "overleaf_templates"


OVERLEAF_DIR.mkdir(parents=True, exist_ok=True)


TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


_STATIC_DIR = Path(__file__).resolve().parent / "static"








def _project_path(project_id: str) -> Path:


    p = OVERLEAF_DIR / project_id


    if not p.is_dir():


        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")


    return p








def _read_project_meta(project_id: str) -> Dict[str, Any]:


    p = _project_path(project_id) / "project.json"


    if not p.is_file():


        return {"id": project_id, "name": project_id, "main_tex": None}


    return json.loads(p.read_text("utf-8"))








def _write_project_meta(project_id: str, meta: Dict[str, Any]) -> None:


    (OVERLEAF_DIR / project_id / "project.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")








def _guess_main_tex(project_dir: Path) -> Optional[str]:


    """Find the main .tex file (the one with \\documentclass)."""


    tex_files = list(project_dir.rglob("*.tex"))


    for f in sorted(tex_files, key=lambda x: (len(x.relative_to(project_dir).parts), x.name)):


        try:


            if "\\documentclass" in f.read_text("utf-8", errors="replace"):


                return str(f.relative_to(project_dir).as_posix())


        except Exception:


            continue


    if tex_files:


        return str(tex_files[0].relative_to(project_dir).as_posix())


    return None








def _safe_path(project_dir: Path, rel_path: str) -> Path:


    full = (project_dir / rel_path).resolve()


    if not str(full).startswith(str(project_dir.resolve())):


        raise HTTPException(status_code=400, detail="路径安全错误")


    return full








def _is_valid_pdf(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _resolve_compiled_pdf(project_dir: Path, main_tex: str) -> Optional[Path]:
    """Locate the compiled PDF, skipping empty placeholder files."""
    candidates: List[Path] = []
    if main_tex:
        stem = Path(main_tex).stem
        candidates.extend([
            project_dir / "output" / "output.pdf",
            project_dir / "output" / f"{stem}.pdf",
            project_dir / f"{stem}.pdf",
        ])
    else:
        candidates.append(project_dir / "output" / "output.pdf")

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if _is_valid_pdf(candidate):
            return candidate

    for folder in (project_dir / "output", project_dir):
        if not folder.is_dir():
            continue
        pdfs = sorted(
            (f for f in folder.glob("*.pdf") if _is_valid_pdf(f)),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        if pdfs:
            return pdfs[0]
    return None


def _scan_files(project_dir: Path) -> List[Dict[str, Any]]:


    files = []


    for f in sorted(project_dir.rglob("*")):


        if f.is_file() and f.name != "project.json":


            rel = str(f.relative_to(project_dir).as_posix())


            if rel.startswith("output/"):


                continue


            files.append({"path": rel, "name": f.name, "is_tex": f.suffix == ".tex", "size": f.stat().st_size})


    return files








class PolishBody(BaseModel):
    query: str = ""
    target_file: str = ""
    selected_text: Optional[str] = None


class GenerateBody(BaseModel):
    outline: str = ""
    template_id: str = ""
    template_content: Optional[str] = None


def create_app() -> FastAPI:


    app = FastAPI(title="TeX Agent Overleaf", version="0.1.0")


    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])





    @app.get("/")


    async def serve_index():


        return FileResponse(_STATIC_DIR / "index.html")





    @app.get("/editor")


    async def serve_editor():


        return FileResponse(_STATIC_DIR / "editor.html")





    @app.get("/api/templates")


    async def list_templates() -> List[Dict[str, Any]]:


        if not TEMPLATES_DIR.is_dir():


            return []


        templates = []


        for d in sorted(TEMPLATES_DIR.iterdir()):


            if d.is_dir():


                mp = d / "template.json"


                meta = json.loads(mp.read_text("utf-8")) if mp.is_file() else {}


                templates.append({"id": d.name, "name": meta.get("name", d.name), "description": meta.get("description", ""), "main_tex": meta.get("main_tex", "")})


        return templates





    @app.post("/api/templates/upload")


    async def upload_template(file: UploadFile = File(...)) -> Dict[str, Any]:


        if not file.filename or not file.filename.endswith(".zip"):


            raise HTTPException(status_code=400, detail="\u4ec5\u652f\u6301 zip \u6587\u4ef6")


        tid = str(uuid.uuid4())[:8]


        ed = TEMPLATES_DIR / tid


        ed.mkdir(parents=True, exist_ok=True)


        try:


            with zipfile.ZipFile(file.file) as zf:


                zf.extractall(str(ed))


        except zipfile.BadZipFile:


            shutil.rmtree(ed, ignore_errors=True)


            raise HTTPException(status_code=400, detail="\u65e0\u6548\u7684 zip \u6587\u4ef6")


        main_tex = _guess_main_tex(ed)


        meta = {"name": Path(file.filename).stem, "description": "", "main_tex": main_tex or ""}


        (ed / "template.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")


        return {"id": tid, **meta}





    @app.post("/api/projects")


    async def create_project(data: Dict[str, Any]) -> Dict[str, Any]:


        pid = str(uuid.uuid4())[:8]


        pd = OVERLEAF_DIR / pid


        pd.mkdir(parents=True, exist_ok=True)


        tex = data.get("template_content", "")


        if not tex:


            tex = "\\documentclass{article}\n\\usepackage[utf8]{inputenc}\n\\usepackage{ctex}\n\\title{新论文}\n\\author{作者}\n\\date{\\today}\n\\begin{document}\n\\maketitle\n\\tableofcontents\n\\section{引言}\n请在此处撰写引言。\n\\end{document}\n"


        main_tex = data.get("main_tex", "main.tex")


        (pd / main_tex).write_text(tex, "utf-8")


        meta = {"id": pid, "name": data.get("name", f"project_{pid}"), "main_tex": main_tex}


        _write_project_meta(pid, meta)


        return meta





    @app.get("/api/projects")


    async def list_projects() -> List[Dict[str, Any]]:


        if not OVERLEAF_DIR.is_dir():


            return []


        projects = []


        for d in sorted(OVERLEAF_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):


            if d.is_dir():


                projects.append(_read_project_meta(d.name))


        return projects





    @app.get("/api/projects/{project_id}")


    async def get_project(project_id: str) -> Dict[str, Any]:


        meta = _read_project_meta(project_id)


        meta["files"] = _scan_files(_project_path(project_id))


        return meta





    @app.post("/api/projects/upload")


    async def upload_project(file: UploadFile = File(...)) -> Dict[str, Any]:


        if not file.filename or not file.filename.endswith(".zip"):


            raise HTTPException(status_code=400, detail="\u4ec5\u652f\u6301 zip \u6587\u4ef6")


        pid = str(uuid.uuid4())[:8]


        pd = OVERLEAF_DIR / pid


        pd.mkdir(parents=True, exist_ok=True)


        try:


            with zipfile.ZipFile(file.file) as zf:


                zf.extractall(str(pd))


        except zipfile.BadZipFile:


            shutil.rmtree(pd, ignore_errors=True)


            raise HTTPException(status_code=400, detail="\u65e0\u6548\u7684 zip \u6587\u4ef6")


        main_tex = _guess_main_tex(pd)


        meta = {"id": pid, "name": Path(file.filename).stem, "main_tex": main_tex or ""}


        _write_project_meta(pid, meta)


        return meta





    async def list_project_files(project_id: str) -> List[Dict[str, Any]]:
        return _scan_files(_project_path(project_id))





    @app.get("/api/projects/{project_id}/file")


    async def read_project_file(project_id: str, path: str) -> Dict[str, Any]:


        p = _project_path(project_id)


        target = _safe_path(p, path)


        if not target.is_file():


            raise HTTPException(status_code=404, detail=f"\u6587\u4ef6\u4e0d\u5b58\u5728: {path}")


        return {"path": path, "content": target.read_text("utf-8", errors="replace")}





    @app.put("/api/projects/{project_id}/file")


    async def write_project_file(project_id: str, path: str, data: Dict[str, Any]) -> Dict[str, str]:


        p = _project_path(project_id)


        target = _safe_path(p, path)


        target.parent.mkdir(parents=True, exist_ok=True)


        target.write_text(data.get("content", ""), "utf-8")


        return {"status": "ok"}





    @app.get("/api/projects/{project_id}/pdf")
    async def serve_project_pdf(project_id: str) -> Response:
        p = _project_path(project_id)
        meta = _read_project_meta(project_id)
        pdf_path = _resolve_compiled_pdf(p, meta.get("main_tex", ""))
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF \u5c1a\u672a\u7f16\u8bd1")
        data = pdf_path.read_bytes()
        if not data:
            raise HTTPException(status_code=404, detail="PDF \u6587\u4ef6\u4e3a\u7a7a\uff0c\u8bf7\u91cd\u65b0\u7f16\u8bd1")
        return Response(
            content=data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'inline; filename="output.pdf"',
                "Content-Length": str(len(data)),
                "Cache-Control": "no-store",
            },
        )


    @app.post("/api/projects/{project_id}/compile")
    async def compile_project(project_id: str, file: str = None) -> Dict[str, Any]:
        """Compile the project using pdflatex directly (latexmk needs perl which is not installed)."""
        import subprocess
        try:
            meta = _read_project_meta(project_id)
            p = _project_path(project_id)
            main_tex = meta.get("main_tex") or file or ""
            if not main_tex:
                raise HTTPException(status_code=400, detail="\u672a\u8bbe\u7f6e\u4e3b\u6587\u4ef6")
            main_path = p / main_tex
            if not main_path.is_file():
                raise HTTPException(status_code=400, detail=f"\u4e3b\u6587\u4ef6\u4e0d\u5b58\u5728: {main_tex}")
            od = p / "output"
            od.mkdir(exist_ok=True)
            stale_output = od / "output.pdf"
            if stale_output.is_file() and stale_output.stat().st_size == 0:
                stale_output.unlink(missing_ok=True)
            from latex.tex_env import probe_tex_env
            tex_env = probe_tex_env()
            pdflatex = tex_env.paths.get("pdflatex")
            if not pdflatex:
                return {"success": False, "issues": [], "warnings": ["pdflatex_not_found"], "log": "\u672a\u627e\u5230 pdflatex", "stdout": "", "stderr": "", "pdf_exists": False}
            argv = [pdflatex, "-interaction=nonstopmode", "-output-directory", str(od.resolve()), main_tex]
            proc = subprocess.run(
                argv,
                cwd=str(p),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
            )
            # Run a second time for cross-refs
            subprocess.run(
                argv,
                cwd=str(p),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
            )
            stem_pdf = od / f"{Path(main_tex).stem}.pdf"
            output_pdf = od / "output.pdf"
            if _is_valid_pdf(stem_pdf):
                shutil.copy2(stem_pdf, output_pdf)
            pdf_path = _resolve_compiled_pdf(p, main_tex)
            pdf_exists = pdf_path is not None
            compile_ok = pdf_exists
            pdf_size = pdf_path.stat().st_size if pdf_path else 0
            payload: Dict[str, Any] = {
                "success": compile_ok,
                "issues": [],
                "warnings": [] if compile_ok else ["pdf_not_generated"],
                "log": (proc.stdout or "")[-2000:] if not compile_ok else "",
                "stdout": (proc.stdout or "")[-2000:],
                "stderr": (proc.stderr or "")[-2000:],
                "pdf_exists": pdf_exists,
                "pdf_size": pdf_size,
                "compiled_file": main_tex,
                "project_root": str(p),
                "return_code": proc.returncode,
            }
            if compile_ok and pdf_path and pdf_size <= 15 * 1024 * 1024:
                payload["pdf_base64"] = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
            return payload
        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            return {"success": False, "issues": [], "warnings": ["timeout"], "log": "pdflatex \u8d85\u65f6", "stdout": "", "stderr": "", "pdf_exists": False}
        except Exception as e:
            return {"success": False, "issues": [], "warnings": [str(e)], "log": str(e)[:500], "stdout": "", "stderr": "", "pdf_exists": False}

    @app.post("/api/projects/{project_id}/polish")


    async def polish_file(project_id: str, body: PolishBody) -> Dict[str, Any]:


        from latex.ghost_polish_prompt import build_ghost_polish_prompt


        from agents.simple_agent import SimpleAgent


        from core.message import WorkflowMessage


        q = (body.query or "").strip()
        selected = (body.selected_text or "").strip()
        tr = body.target_file or ""

        if not q and not selected:
            raise HTTPException(status_code=400, detail="query \u4e0d\u80fd\u4e3a\u7a7a")


        if not tr:


            raise HTTPException(status_code=400, detail="target_file \u4e0d\u80fd\u4e3a\u7a7a")


        p = _project_path(project_id)


        tp = _safe_path(p, tr)


        if not tp.is_file():


            raise HTTPException(status_code=404, detail=f"\u6587\u4ef6\u4e0d\u5b58\u5728: {tr}")


        tt = tp.read_text("utf-8", errors="replace")
        polish_query = q or ("请润色以下选中文本，保持 LaTeX 语法正确，表达更学术流畅。" if selected else q)
        target_text = selected if selected else tt
        prompt = build_ghost_polish_prompt(
            query=polish_query,
            target_file=tr,
            target_text=target_text,
            context_file=tr,
            context_text=tt,
        )


        agent = SimpleAgent(name="overleaf_polish", temperature=0.4)


        res = agent.run(WorkflowMessage(role="user", content=prompt))


        import json as _json


        from latex.suggestion import _extract_json_candidates


        raw = str(res.content)


        data = None


        for c in [raw] + list(_extract_json_candidates(raw)):


            try:


                p2 = _json.loads(c)


                if isinstance(p2, dict):


                    data = p2


                    break


            except _json.JSONDecodeError:


                continue


        if not data:


            raise HTTPException(status_code=400, detail="\u6da6\u8272\u7ed3\u679c\u65e0\u6cd5\u89e3\u6790")


        return {"original_text": str(data.get("original_text", "")), "polished_text": str(data.get("polished_text", "")), "problem_zh": str(data.get("problem_zh", "")), "advice_zh": str(data.get("advice_zh", ""))}


    @app.post("/api/projects/generate")


    async def generate_thesis(body: GenerateBody) -> Dict[str, Any]:
        try:
            from ui.overleaf.thesis_generator import generate_thesis_project
            if not body.outline.strip():
                raise HTTPException(status_code=400, detail="\u5927\u7eb2\u4e0d\u80fd\u4e3a\u7a7a")
            tdir = (TEMPLATES_DIR / body.template_id) if body.template_id and (TEMPLATES_DIR / body.template_id).is_dir() else None
            pid = str(uuid.uuid4())[:8]
            pd = OVERLEAF_DIR / pid
            pd.mkdir(parents=True, exist_ok=True)
            result = generate_thesis_project(project_dir=pd, outline=body.outline, template_dir=tdir, template_content=body.template_content)
            meta = {"id": pid, "name": result.get("title", "\u751f\u6210\u8bba\u6587"), "main_tex": result.get("main_tex", "main.tex")}
            _write_project_meta(pid, meta)
            meta["summary"] = result.get("summary", "")
            return meta
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"\u751f\u6210\u5931\u8d25: {e}")





    @app.get("/api/templates/builtin")


    async def list_builtin_templates() -> List[Dict[str, Any]]:


        builtin_dir = Path(__file__).resolve().parents[2] / "doc" / "templates"


        if not builtin_dir.is_dir():


            return []


        templates = []


        for f in sorted(builtin_dir.glob("*.tex")):


            templates.append({"id": f"builtin:{f.stem}", "name": f.stem, "description": "\u5185\u7f6e\u6a21\u677f"})


        return templates






    @app.get("/api/projects/{project_id}/diagnose")
    async def diagnose_project(project_id: str) -> Dict[str, Any]:
        from latex.chktex_runner import run_chktex, resolve_target_files
        from latex.issues import merge_issues
        meta = _read_project_meta(project_id)
        pd = _project_path(project_id)
        main_tex = meta.get("main_tex", "")
        rel_files = resolve_target_files(pd, main_tex=main_tex or None)
        chk_res = run_chktex(pd, rel_files)
        merged = merge_issues(chk_res.issues, [])
        return {"issues": [i.model_dump(mode="json") for i in merged], "chktex_warnings": list(chk_res.warnings)}

    if _STATIC_DIR.is_dir():


        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="overleaf_static")


    return app








app = create_app()








def main():


    import uvicorn


    host = os.environ.get("OVERLEAF_HOST", "127.0.0.1")


    port = int(os.environ.get("OVERLEAF_PORT", "8772"))


    print(f"[Overleaf] http://{host}:{port}/")


    uvicorn.run("ui.overleaf.server:app", host=host, port=port, reload=False)








if __name__ == "__main__":
    main()

