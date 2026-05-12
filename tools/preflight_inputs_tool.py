import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.message import ToolResult
from tools.base_tool import BaseTool
from tools.register_inputs_tool import RegisterInputsTool
from utils.logger import get_logger
from workflow.workflow_registry import WorkflowRegistry

logger = get_logger(__name__)


class PreflightInputsTool(BaseTool):
    """
    预检工作流输入依赖：
    1) 静态扫描后续节点中路径/文件类输入；
    2) 判断哪些依赖更可能由用户输入提供；
    3) 从用户输入文本中抽取路径（支持中英文与 Win/Linux 风格）；
    4) 产出可直接传给下游 register_inputs 的 payload（可选在本工具内联执行 register，见 run_register）。
    """

    _TEMPLATE_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _KEYVAL_PATTERN = re.compile(
        r'["\']?([a-zA-Z0-9_.-]*(?:path|file|pdf|checklist|output|chapter|chapters|section)[a-zA-Z0-9_.-]*)["\']?\s*[:=]\s*'
        r'(?:"([^"]+)"|\'([^\']+)\'|([^\n\r]+))',
        flags=re.IGNORECASE,
    )
    _LABEL_PATTERN = re.compile(
        r"^\s*-\s*\[(PDF|Checklist|Output|File)\]\s+(.+?)\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    _GENERIC_PATH_PATTERN = re.compile(
        r"((?:[A-Za-z]:[\\/]|\\\\|/|\.{1,2}[\\/]|~[\\/])"
        r"[^\"'\n\r]*?"
        r"(?:\.(?:pdf|md|txt|json|ya?ml|docx?|xlsx?|csv|pptx?))?)",
        flags=re.IGNORECASE,
    )
    _QUOTED_PATH_PATTERN = re.compile(
        r"[\"“”'‘’]([^\"“”'‘’\n\r]*[\\/][^\"“”'‘’\n\r]+)[\"“”'‘’]"
    )

    _PDF_EXT = {".pdf"}
    _CHECKLIST_EXT = {".md", ".txt", ".json", ".yaml", ".yml"}
    _PATH_HINT_KEYS = ("path", "file", "pdf", "checklist", "output", "attachment")
    _VALUE_HINT_KEYS = ("chapter", "chapters", "section")
    _CHAPTER_KEYVAL_PATTERN = re.compile(
        r'["\']?(chapter_selection|chapter|chapters|section|sections)["\']?\s*[:=]\s*'
        r'(?:"([^"]+)"|\'([^\']+)\'|([^\n\r]+))',
        flags=re.IGNORECASE,
    )
    _CHAPTER_TOKEN_PATTERN = re.compile(
        r"(第\s*[一二三四五六七八九十百千万零两\d]+\s*[章节篇]|"
        r"chapter\s+\d+(?:\.\d+)*|"
        r"\d+(?:\.\d+)*(?:\s*[-~到至]\s*\d+(?:\.\d+)*)?)",
        flags=re.IGNORECASE,
    )
    _CHAPTER_KEYWORD_PATTERN = re.compile(
        r"(摘要|中文摘要|英文摘要|abstract|参考文献|references|bibliography|致谢|鸣谢|"
        r"acknowledgements|acknowledgments|引言|绪论|结论|附录)",
        flags=re.IGNORECASE,
    )
    _QUOTED_SECTION_PATTERN = re.compile(
        r"[\"“”'‘’]([^\"“”'‘’\n\r]{1,80})[\"“”'‘’]\s*(?:这一|这)?(?:章节|小节|节|部分)",
        flags=re.IGNORECASE,
    )
    _SUFFIX_SECTION_PATTERN = re.compile(
        r"(?:^|[，。；;,\n\s])([A-Za-z0-9\u4e00-\u9fa5\.\- ]{2,40})\s*(?:这一|这)?(?:章节|小节|节|部分)",
        flags=re.IGNORECASE,
    )
    _USER_EXPR_PREFIXES = (
        "input",
        "last_message",
        "last_message_content",
        "messages",
        "state.input",
    )
    _DEFAULTABLE_SLOT_RULES = {
        "output_path": "auto_output_from_pdf",
        "output_pdf_path": "auto_output_from_pdf",
    }

    def __init__(self):
        super().__init__(
            name="preflight_inputs",
            description=(
                "静态分析当前工作流后续节点的文件/路径输入需求，并从用户输入中抽取路径。"
                "支持 Linux/Windows 路径与中文路径。"
            ),
            input_schema={
                "user_input": "用户本轮输入文本（可与 context_text 合并后再抽取路径）",
                "context_text": "可选：来自对话上下文的文本（如 ${last_message_content}），与 user_input 拼接后参与路径抽取；"
                "若路径仅出现在上文，用户本轮不必重复粘贴。",
                "workflow_name": "当前工作流名（可选，建议传 ${metadata.workflow}）",
                "workflow_path": "工作流配置文件路径（可选，优先级高于 workflow_name）",
                "current_node_id": "本 preflight 节点 node_id（可选，用于忽略自身）",
                "run_register": "是否在抽取后内联执行 register_inputs 逻辑并写出 pdf_abs_path/checklist_abs_path/output_pdf_abs_path（默认 false，避免与独立 register_inputs 节点重复）",
                "strict_mode": "是否严格校验必填路径槽位，缺失时直接失败（默认 true）",
                "llm_provider": "LLM 提供方，支持 openai/gemini（默认 openai）",
                "use_llm": "是否启用 LLM 二次语义抽取（可选，默认 true）",
                "llm_model": "LLM 模型名（可选，openai 默认取 LLM_MODEL）",
            },
        )
        self.project_root = Path(__file__).resolve().parent.parent
        self._workflow_registry = WorkflowRegistry()
        self._llm_client = None

    # ----------------------------- run -----------------------------
    def run(
        self,
        payload: Union[str, Dict[str, Any], None] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """
        兼容 workflow 里 `tool.run(**tool_input)`：dict 会被拆成关键字参数传入。
        """
        if kwargs:
            if isinstance(payload, dict):
                merged_payload: Union[str, Dict[str, Any]] = {**payload, **kwargs}
            elif isinstance(payload, str) and str(payload).strip():
                merged_payload = {**kwargs, "user_input": str(payload)}
            else:
                merged_payload = dict(kwargs)
        elif payload is not None:
            merged_payload = payload
        else:
            merged_payload = ""

        user_input = ""
        context_text = ""
        workflow_name = ""
        workflow_path = ""
        current_node_id = ""
        use_llm = True
        llm_model = ""
        llm_provider = "openai"
        run_register = False
        strict_mode = True

        try:
            data = self._coerce_payload(merged_payload)
            user_input = str(data.get("user_input", "") or "")
            context_text = str(data.get("context_text", "") or "")
            workflow_name = str(data.get("workflow_name", "") or "")
            workflow_path = str(data.get("workflow_path", "") or "")
            current_node_id = str(data.get("current_node_id", "") or "").strip()
            use_llm = self._coerce_bool(data.get("use_llm", True))
            llm_model = str(data.get("llm_model", "") or "")
            llm_provider = str(data.get("llm_provider", "") or "openai").strip().lower()
            run_register = self._coerce_bool(data.get("run_register", False))
            strict_mode = self._coerce_bool(data.get("strict_mode", True))

            combined_text = self._merge_context_and_user_input(context_text, user_input)

            wf_path, scan_warning = self._resolve_workflow_path(
                workflow_name=workflow_name,
                workflow_path=workflow_path,
            )
            workflow_config = self._load_workflow_config(wf_path) if wf_path else {}

            analysis = self._analyze_workflow_requirements(
                workflow_config=workflow_config,
                current_node_id=current_node_id,
            )
            extracted = self._extract_paths_from_text(combined_text)
            extracted_values = self._extract_values_from_text(combined_text)
            user_slots = analysis.get("user_required_slots", [])
            slot_contract = self._build_slot_contract(user_slots)
            slot_values = self._map_paths_to_slots(
                slots=slot_contract,
                extracted=extracted,
            )
            slot_values.update(
                self._map_values_to_slots(
                    slots=slot_contract,
                    extracted_values=extracted_values,
                )
            )

            llm_info: Dict[str, Any] = {"enabled": False, "used": False, "error": ""}
            if use_llm:
                llm_info["enabled"] = True
                llm_slot_values, llm_error = self._extract_paths_with_llm(
                    user_input=combined_text,
                    slots=slot_contract,
                    extracted={**extracted, **extracted_values},
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
                if llm_slot_values:
                    llm_info["used"] = True
                    slot_values = self._merge_slot_values(slot_values, llm_slot_values, slot_contract)
                if llm_error:
                    llm_info["error"] = llm_error

            self._apply_slot_defaults(slot_values, slot_contract)
            normalized_inputs = self._to_normalized_inputs(slot_values, extracted)
            extra_slots = self._to_extra_slots(slot_values, slot_contract)
            required_view = dict(normalized_inputs)
            required_view.update(extra_slots)
            missing_required_slots = self._find_missing_required_slots(
                slot_values=required_view,
                slot_contract=slot_contract,
            )
            payload_for_register_inputs: Union[str, Dict[str, Any]]
            if any(normalized_inputs.values()):
                payload_for_register_inputs = normalized_inputs
            else:
                payload_for_register_inputs = combined_text if combined_text.strip() else user_input

            warnings: List[str] = []
            if scan_warning:
                warnings.append(scan_warning)
            if context_text.strip():
                warnings.append("已合并 context_text 与 user_input 做路径抽取（上文路径可补全本轮未重复给出的路径）。")
            if not user_slots:
                warnings.append("未发现明确的用户路径输入槽位，已退化为纯路径抽取模式。")
            if not extracted.get("all_paths"):
                warnings.append("未从合并文本中提取到明确路径。")
            if missing_required_slots:
                warnings.append(f"缺失必填槽位：{', '.join(missing_required_slots)}")
            if llm_info.get("error"):
                warnings.append(f"LLM 抽取未生效：{llm_info['error']}")

            output_obj: Dict[str, Any] = {
                "workflow_name": workflow_name,
                "workflow_path": str(wf_path) if wf_path else "",
                "analysis": analysis,
                "slot_contract": slot_contract,
                "extracted_paths": extracted,
                "extracted_values": extracted_values,
                "resolved_user_paths": slot_values,
                "extra_slots": extra_slots,
                "normalized_inputs": normalized_inputs,
                "payload_for_register_inputs": payload_for_register_inputs,
                "context_text_used": bool(context_text.strip()),
                "run_register": run_register,
                "strict_mode": strict_mode,
                "llm": llm_info,
                "warnings": warnings,
            }

            final_success = True
            final_error: Optional[str] = None
            if strict_mode and missing_required_slots:
                final_success = False
                final_error = (
                    "缺少工作流必填参数："
                    + ", ".join(missing_required_slots)
                    + "。请在输入中补充这些参数后重试。"
                )
            if run_register:
                reg_tool = RegisterInputsTool()
                reg_res = reg_tool.run(payload_for_register_inputs)
                reg_meta = reg_res.metadata if isinstance(reg_res.metadata, dict) else {}
                for key in ("pdf_abs_path", "checklist_abs_path", "output_pdf_abs_path"):
                    if reg_meta.get(key):
                        output_obj[key] = reg_meta[key]
                if isinstance(reg_meta.get("warnings"), list):
                    output_obj["register_warnings"] = list(reg_meta["warnings"])
                output_obj["register_success"] = bool(reg_res.success)
                if not reg_res.success and final_success:
                    final_success = False
                    final_error = str(reg_res.error or "register_inputs 内联失败")
                    warnings.append(final_error)

            output_obj["warnings"] = warnings
            return ToolResult(
                success=final_success,
                output=json.dumps(output_obj, ensure_ascii=False),
                metadata=output_obj,
                error=final_error,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("[preflight_inputs] 执行失败")
            combined_fb = self._merge_context_and_user_input(context_text, user_input)
            fallback_obj = {
                "workflow_name": workflow_name,
                "workflow_path": workflow_path,
                "analysis": {},
                "extracted_paths": self._extract_paths_from_text(combined_fb.strip() or user_input),
                "extracted_values": self._extract_values_from_text(combined_fb.strip() or user_input),
                "resolved_user_paths": {},
                "extra_slots": {},
                "normalized_inputs": {},
                "payload_for_register_inputs": combined_fb or user_input,
                "warnings": [f"preflight_inputs 降级：{e}"],
            }
            return ToolResult(
                success=False,
                output=json.dumps(fallback_obj, ensure_ascii=False),
                metadata=fallback_obj,
                error=str(e),
            )

    # ----------------------------- payload -----------------------------
    def _coerce_payload(self, payload: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(payload, dict):
            data = dict(payload)
            if "user_input" not in data and "payload" in data:
                data["user_input"] = data.get("payload", "")
            return data
        if isinstance(payload, str):
            raw = payload.strip()
            if not raw:
                return {"user_input": ""}
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        if "user_input" not in data and "payload" in data:
                            data["user_input"] = data.get("payload", "")
                        return data
                except Exception:
                    pass
            return {"user_input": raw}
        return {"user_input": str(payload)}

    @staticmethod
    def _merge_context_and_user_input(context_text: str, user_input: str) -> str:
        """
        上下文在前、本轮输入在后，便于同一 key（如 [PDF]）在上下文中已出现时优先被解析。
        """
        c = (context_text or "").strip()
        u = (user_input or "").strip()
        if c and u:
            return f"{c}\n{u}"
        return c or u

    @staticmethod
    def _coerce_bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        s = str(v).strip().lower()
        return s in {"1", "true", "yes", "y", "on"}

    # ----------------------------- workflow scan -----------------------------
    def _resolve_workflow_path(
        self, *, workflow_name: str, workflow_path: str
    ) -> Tuple[Optional[Path], str]:
        if workflow_path:
            p = Path(workflow_path.strip().strip('"').strip("'"))
            if not p.is_absolute():
                p = (self.project_root / p).resolve()
            if p.exists():
                return p, ""
            return None, f"workflow_path 不存在：{p}"

        if workflow_name:
            try:
                return self._workflow_registry.get_config_path(workflow_name), ""
            except Exception as e:  # noqa: BLE001
                return None, f"无法通过 workflow_name 解析配置：{e}"
        return None, "未提供 workflow_name/workflow_path，无法执行完整静态扫描。"

    def _load_workflow_config(self, workflow_path: Path) -> Dict[str, Any]:
        with workflow_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _analyze_workflow_requirements(
        self,
        *,
        workflow_config: Dict[str, Any],
        current_node_id: str,
    ) -> Dict[str, Any]:
        nodes_raw = workflow_config.get("nodes", []) if isinstance(workflow_config, dict) else []
        if not isinstance(nodes_raw, list):
            nodes_raw = []

        node_map: Dict[str, Dict[str, Any]] = {}
        for raw in nodes_raw:
            if not isinstance(raw, dict):
                continue
            nid = str(raw.get("node_id", "") or "").strip()
            if not nid:
                continue
            node_map[nid] = raw

        user_origin_cache: Dict[str, bool] = {}
        visiting: Set[str] = set()

        def is_user_origin(node_id: str) -> bool:
            if node_id in user_origin_cache:
                return user_origin_cache[node_id]
            if node_id in visiting:
                return False
            visiting.add(node_id)
            raw = node_map.get(node_id, {})
            node_type = str(raw.get("node_type", "") or "").strip().lower()
            cfg = raw.get("config", {})
            if not isinstance(cfg, dict):
                cfg = {}

            if node_type == "user":
                user_origin_cache[node_id] = True
                visiting.discard(node_id)
                return True

            template_exprs = self._collect_template_exprs(cfg)
            if any(self._is_direct_user_expr(expr) for expr in template_exprs):
                user_origin_cache[node_id] = True
                visiting.discard(node_id)
                return True

            upstream_nodes = self._extract_metadata_node_refs(template_exprs)
            if any(is_user_origin(up_id) for up_id in upstream_nodes):
                user_origin_cache[node_id] = True
                visiting.discard(node_id)
                return True

            # tool 节点如果无显式依赖和模板，默认视作直接吃输入（与引擎默认行为一致）
            if node_type == "tool":
                depends_on = cfg.get("depends_on", [])
                raw_tool_input = cfg.get("tool_input")
                if (not depends_on) and (raw_tool_input is None):
                    user_origin_cache[node_id] = True
                    visiting.discard(node_id)
                    return True

            user_origin_cache[node_id] = False
            visiting.discard(node_id)
            return False

        requirements: List[Dict[str, Any]] = []
        for node_id, raw in node_map.items():
            if current_node_id and node_id == current_node_id:
                continue
            cfg = raw.get("config", {})
            if not isinstance(cfg, dict):
                continue
            self._scan_value_requirements(
                node_id=node_id,
                value=cfg,
                path="config",
                out=requirements,
                node_map=node_map,
                is_user_origin_fn=is_user_origin,
            )

        user_slots = self._build_user_slots(requirements)
        return {
            "required_inputs": requirements,
            "user_required_slots": user_slots,
            "node_count": len(node_map),
        }

    def _scan_value_requirements(
        self,
        *,
        node_id: str,
        value: Any,
        path: str,
        out: List[Dict[str, Any]],
        node_map: Dict[str, Dict[str, Any]],
        is_user_origin_fn,
    ) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                next_path = f"{path}.{k}" if path else str(k)
                self._scan_value_requirements(
                    node_id=node_id,
                    value=v,
                    path=next_path,
                    out=out,
                    node_map=node_map,
                    is_user_origin_fn=is_user_origin_fn,
                )
            return
        if isinstance(value, list):
            for i, item in enumerate(value):
                next_path = f"{path}[{i}]"
                self._scan_value_requirements(
                    node_id=node_id,
                    value=item,
                    path=next_path,
                    out=out,
                    node_map=node_map,
                    is_user_origin_fn=is_user_origin_fn,
                )
            return
        if not isinstance(value, str):
            return

        templates = [m.group(1).strip() for m in self._TEMPLATE_PATTERN.finditer(value)]
        is_path_like = self._looks_path_related(path, value)
        is_value_like = self._looks_value_related(path, value)
        if not templates and not is_path_like and not is_value_like:
            return

        source_types: List[str] = []
        provider_nodes: List[str] = []
        user_required = False
        for expr in templates:
            st, pn, user_flag = self._classify_expr(expr, node_map, is_user_origin_fn)
            source_types.append(st)
            if pn:
                provider_nodes.append(pn)
            if user_flag:
                user_required = True

        if not templates and (is_path_like or is_value_like):
            source_types.append("literal")
            user_required = False

        out.append(
            {
                "node_id": node_id,
                "field_path": path,
                "value_preview": value[:240],
                "templates": templates,
                "source_types": sorted(set(source_types)),
                "provider_nodes": sorted(set(provider_nodes)),
                "user_required": user_required,
            }
        )

    def _classify_expr(
        self,
        expr: str,
        node_map: Dict[str, Dict[str, Any]],
        is_user_origin_fn,
    ) -> Tuple[str, str, bool]:
        expr = (expr or "").strip()
        if not expr:
            return "unknown", "", False
        if self._is_direct_user_expr(expr):
            return "direct_user_input", "", True
        if expr.startswith("metadata."):
            parts = [p for p in expr.split(".") if p]
            if len(parts) >= 2:
                provider = parts[1]
                if provider in node_map:
                    if is_user_origin_fn(provider):
                        return "derived_from_user_node", provider, True
                    return "derived_from_upstream_node", provider, False
                return "metadata_unknown_node", provider, True
            return "metadata_unknown", "", True
        if expr.startswith("state.input"):
            return "direct_user_input", "", True
        return "other_expression", "", False

    def _collect_template_exprs(self, value: Any) -> List[str]:
        exprs: List[str] = []
        if isinstance(value, dict):
            for v in value.values():
                exprs.extend(self._collect_template_exprs(v))
            return exprs
        if isinstance(value, list):
            for item in value:
                exprs.extend(self._collect_template_exprs(item))
            return exprs
        if isinstance(value, str):
            exprs.extend(m.group(1).strip() for m in self._TEMPLATE_PATTERN.finditer(value))
        return exprs

    def _extract_metadata_node_refs(self, exprs: List[str]) -> Set[str]:
        out: Set[str] = set()
        for expr in exprs:
            ex = (expr or "").strip()
            if not ex.startswith("metadata."):
                continue
            parts = [p for p in ex.split(".") if p]
            if len(parts) >= 2:
                out.add(parts[1])
        return out

    def _build_user_slots(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        slots: Dict[str, Dict[str, Any]] = {}
        for req in requirements:
            if not req.get("user_required"):
                continue
            field_path = str(req.get("field_path", ""))
            slot_name = self._to_slot_name(
                field_path=field_path,
                value_preview=str(req.get("value_preview", "") or ""),
                templates=req.get("templates", []) or [],
            )
            entry = slots.get(slot_name)
            if entry is None:
                slot_kind = self._infer_slot_kind(slot_name)
                entry = {
                    "slot": slot_name,
                    "from_nodes": [],
                    "field_paths": [],
                    "slot_kind": slot_kind,
                    "suggested_extensions": self._suggest_extensions(slot_name),
                }
                slots[slot_name] = entry
            node_id = str(req.get("node_id", ""))
            if node_id and node_id not in entry["from_nodes"]:
                entry["from_nodes"].append(node_id)
            if field_path and field_path not in entry["field_paths"]:
                entry["field_paths"].append(field_path)
        return list(slots.values())

    def _build_slot_contract(self, user_slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        contract: List[Dict[str, Any]] = []
        for slot in user_slots:
            name = str(slot.get("slot", "") or "").strip()
            if not name:
                continue
            default_strategy = self._DEFAULTABLE_SLOT_RULES.get(name, "")
            required = not bool(default_strategy)
            entry = dict(slot)
            if not entry.get("slot_kind"):
                entry["slot_kind"] = self._infer_slot_kind(name)
            entry["required"] = required
            entry["default_strategy"] = default_strategy
            contract.append(entry)
        return contract

    def _infer_slot_kind(self, slot_name: str) -> str:
        name = str(slot_name or "").strip().lower()
        if "chapter" in name or "section" in name:
            return "value"
        return "path"

    def _to_slot_name(self, *, field_path: str, value_preview: str, templates: List[str]) -> str:
        fp = (field_path or "").lower()
        merged = " ".join([fp, (value_preview or "").lower(), " ".join(str(t).lower() for t in templates)])
        if "chapter_selection" in merged or "chapters" in merged or "chapter" in merged or "section" in merged:
            return "chapter_selection"
        if "pdf" in merged:
            return "pdf_path"
        if "checklist" in merged:
            return "checklist_path"
        if "output" in merged:
            return "output_path"
        if "file_path" in merged or "file" in merged:
            return "file_path"
        if "attachment" in merged:
            return "attachment_path"
        tail = fp.split(".")[-1].replace("[", "_").replace("]", "")
        tail = re.sub(r"[^a-z0-9_]+", "_", tail).strip("_")
        return tail if tail else "path"

    def _suggest_extensions(self, slot_name: str) -> List[str]:
        s = (slot_name or "").lower()
        if "chapter" in s or "section" in s:
            return []
        if "pdf" in s:
            return [".pdf"]
        if "checklist" in s:
            return [".md", ".txt", ".json", ".yaml", ".yml"]
        if "output" in s:
            return [".pdf", ".md", ".txt", ".json"]
        return [".pdf", ".md", ".txt", ".json", ".yaml", ".yml", ".docx"]

    def _is_direct_user_expr(self, expr: str) -> bool:
        ex = (expr or "").strip().lower()
        return any(ex == p or ex.startswith(f"{p}.") for p in self._USER_EXPR_PREFIXES)

    def _looks_path_related(self, field_path: str, value: str) -> bool:
        fp = (field_path or "").lower()
        if any(k in fp for k in self._PATH_HINT_KEYS):
            return True
        text = (value or "").strip()
        if not text:
            return False
        if "/" in text or "\\" in text:
            return True
        if re.search(r"\.(pdf|md|txt|json|ya?ml|docx?|csv|xlsx?|pptx?)\b", text, re.IGNORECASE):
            return True
        return False

    def _looks_value_related(self, field_path: str, value: str) -> bool:
        fp = (field_path or "").lower()
        if any(k in fp for k in self._VALUE_HINT_KEYS):
            return True
        text = (value or "").strip().lower()
        if not text:
            return False
        if any(k in text for k in self._VALUE_HINT_KEYS):
            return True
        return False

    # ----------------------------- extraction -----------------------------
    def _extract_paths_from_text(self, text: str) -> Dict[str, Any]:
        raw = str(text or "")
        labeled: Dict[str, str] = {}
        kv: Dict[str, str] = {}
        all_paths: List[str] = []

        for m in self._LABEL_PATTERN.finditer(raw):
            key = m.group(1).strip().lower()
            val = self._normalize_token_path(m.group(2))
            if val:
                labeled[key] = val
                all_paths.append(val)

        for m in self._KEYVAL_PATTERN.finditer(raw):
            key = (m.group(1) or "").strip().lower()
            val = m.group(2) or m.group(3) or m.group(4) or ""
            cleaned = self._normalize_token_path(val)
            if not cleaned:
                continue
            if key not in kv:
                kv[key] = cleaned
            all_paths.append(cleaned)

        for m in self._QUOTED_PATH_PATTERN.finditer(raw):
            cleaned = self._normalize_token_path(m.group(1))
            if cleaned:
                all_paths.append(cleaned)

        for m in self._GENERIC_PATH_PATTERN.finditer(raw):
            cleaned = self._normalize_token_path(m.group(1))
            if cleaned:
                all_paths.append(cleaned)

        all_paths = self._dedupe([p for p in all_paths if not self._looks_like_url(p)])
        pdf_candidates = [p for p in all_paths if self._suffix(p) in self._PDF_EXT]
        checklist_candidates = [
            p for p in all_paths if self._suffix(p) in self._CHECKLIST_EXT
        ]

        return {
            "labeled": labeled,
            "key_values": kv,
            "all_paths": all_paths,
            "pdf_candidates": pdf_candidates,
            "checklist_candidates": checklist_candidates,
        }

    def _extract_values_from_text(self, text: str) -> Dict[str, Any]:
        raw = str(text or "")
        kv: Dict[str, str] = {}
        chapter_tokens: List[str] = []

        for m in self._CHAPTER_KEYVAL_PATTERN.finditer(raw):
            key = str(m.group(1) or "").strip().lower()
            val = m.group(2) or m.group(3) or m.group(4) or ""
            cleaned = self._normalize_chapter_value(val)
            if not cleaned:
                continue
            if key not in kv:
                kv[key] = cleaned
            chapter_tokens.extend(self._split_chapter_tokens(cleaned))

        for m in self._CHAPTER_TOKEN_PATTERN.finditer(raw):
            token = self._normalize_chapter_value(m.group(1) or "")
            if token:
                chapter_tokens.extend(self._split_chapter_tokens(token))

        for m in self._CHAPTER_KEYWORD_PATTERN.finditer(raw):
            token = self._normalize_chapter_value(m.group(1) or "")
            if token:
                chapter_tokens.append(token)

        for m in self._QUOTED_SECTION_PATTERN.finditer(raw):
            token = self._normalize_chapter_value(m.group(1) or "")
            if token:
                chapter_tokens.append(token)

        for m in self._SUFFIX_SECTION_PATTERN.finditer(raw):
            token = self._normalize_chapter_value(m.group(1) or "")
            if token:
                chapter_tokens.append(token)

        chapter_tokens = self._dedupe([t for t in chapter_tokens if t])
        chapter_selection = ";".join(chapter_tokens)
        return {
            "key_values": kv,
            "chapter_tokens": chapter_tokens,
            "chapter_selection": chapter_selection,
        }

    def _split_chapter_tokens(self, text: str) -> List[str]:
        parts = re.split(r"[,\n;；、+]+", str(text or ""))
        out: List[str] = []
        for p in parts:
            token = self._normalize_chapter_value(p)
            if token:
                out.append(token)
        return out

    def _normalize_chapter_value(self, value: str) -> str:
        s = str(value or "").strip()
        if not s:
            return ""
        s = s.strip().strip('"').strip("'").strip("“").strip("”").strip("‘").strip("’")
        s = s.rstrip("。；，,;")
        s = s.replace("～", "-").replace("—", "-")
        s = re.sub(r"\s*到\s*", "-", s)
        s = re.sub(r"\s*至\s*", "-", s)
        s = re.sub(r"(?:这一|这)?(?:章节|小节|节|部分)\s*$", "", s, flags=re.IGNORECASE)
        s = s.rstrip("的")
        s = re.sub(
            r"^(?:请|麻烦|帮我|帮忙|只|仅|请你|解析|提取|查看|看|定位|分析|处理)\s+",
            "",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(
            r"^(?:我(?:想|希望)?|请|麻烦|帮我|帮忙)?(?:想要|希望)?(?:只|仅)?(?:解析|提取|查看|看|定位|分析|处理)",
            "",
            s,
            flags=re.IGNORECASE,
        )
        s = s.strip()
        lower = s.lower()
        alias_map = {
            "abstract": "英文摘要",
            "references": "参考文献",
            "bibliography": "参考文献",
            "acknowledgements": "致谢",
            "acknowledgments": "致谢",
        }
        if lower in alias_map:
            s = alias_map[lower]
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    def _map_paths_to_slots(
        self,
        *,
        slots: List[Dict[str, Any]],
        extracted: Dict[str, Any],
    ) -> Dict[str, str]:
        values: Dict[str, str] = {}
        labeled = extracted.get("labeled", {}) or {}
        kv = extracted.get("key_values", {}) or {}
        all_paths = extracted.get("all_paths", []) or []
        pdf_candidates = extracted.get("pdf_candidates", []) or []
        checklist_candidates = extracted.get("checklist_candidates", []) or []

        # 常见语义优先
        values["pdf_path"] = (
            labeled.get("pdf")
            or kv.get("pdf_path")
            or kv.get("pdf")
            or (pdf_candidates[0] if pdf_candidates else "")
        )
        values["checklist_path"] = (
            labeled.get("checklist")
            or kv.get("checklist_path")
            or kv.get("checklist")
            or (checklist_candidates[0] if checklist_candidates else "")
        )
        values["output_path"] = (
            labeled.get("output")
            or kv.get("output_path")
            or kv.get("output")
            or ""
        )

        for slot in slots:
            slot_name = str(slot.get("slot", "") or "").strip()
            if not slot_name:
                continue
            if values.get(slot_name):
                continue

            exts = [str(e).lower() for e in (slot.get("suggested_extensions") or [])]
            picked = ""
            if exts:
                for p in all_paths:
                    if self._suffix(p) in exts:
                        picked = p
                        break
            if not picked and all_paths:
                picked = all_paths[0]
            values[slot_name] = picked

        return {k: v for k, v in values.items() if isinstance(v, str)}

    def _map_values_to_slots(
        self,
        *,
        slots: List[Dict[str, Any]],
        extracted_values: Dict[str, Any],
    ) -> Dict[str, str]:
        values: Dict[str, str] = {}
        key_values = extracted_values.get("key_values", {}) or {}
        chapter_selection = str(extracted_values.get("chapter_selection", "") or "")

        for slot in slots:
            slot_name = str(slot.get("slot", "") or "").strip()
            if not slot_name:
                continue
            if str(slot.get("slot_kind", "path")) != "value":
                continue
            if slot_name == "chapter_selection":
                picked = (
                    key_values.get("chapter_selection")
                    or key_values.get("chapters")
                    or key_values.get("chapter")
                    or key_values.get("section")
                    or key_values.get("sections")
                    or chapter_selection
                )
                values[slot_name] = self._normalize_chapter_value(picked)
                continue
            # 其他 value 类槽位兜底使用 chapter_selection 文本
            values[slot_name] = self._normalize_chapter_value(chapter_selection)
        return values

    def _merge_slot_values(
        self,
        rule_values: Dict[str, str],
        llm_values: Dict[str, str],
        slot_contract: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        merged = dict(rule_values or {})
        slot_kind_map = {
            str(s.get("slot", "")).strip(): str(s.get("slot_kind", "path")).strip().lower()
            for s in (slot_contract or [])
            if str(s.get("slot", "")).strip()
        }
        for slot, value in (llm_values or {}).items():
            s = str(slot or "").strip()
            kind = slot_kind_map.get(s, "path")
            if kind == "value":
                v = self._normalize_chapter_value(str(value or ""))
            else:
                v = self._normalize_token_path(str(value or ""))
            if not s or not v:
                continue
            # LLM 负责语义判断；规则抽取保留兜底
            merged[s] = v
        return merged

    def _apply_slot_defaults(self, slot_values: Dict[str, str], slot_contract: List[Dict[str, Any]]) -> None:
        for slot in slot_contract:
            name = str(slot.get("slot", "") or "").strip()
            if not name or slot_values.get(name):
                continue
            strategy = str(slot.get("default_strategy", "") or "").strip()
            default_value = self._default_value_by_strategy(strategy, slot_values)
            if default_value:
                slot_values[name] = default_value

    def _default_value_by_strategy(self, strategy: str, slot_values: Dict[str, str]) -> str:
        s = str(strategy or "").strip().lower()
        if s == "auto_output_from_pdf":
            pdf_path = self._to_abs_or_keep(slot_values.get("pdf_path", ""))
            if pdf_path:
                stem = Path(pdf_path).stem
                return str((self.project_root / "storage" / "documents" / f"{stem}-checked.pdf").resolve())
            return str((self.project_root / "storage" / "documents" / "checked.pdf").resolve())
        return ""

    def _find_missing_required_slots(
        self,
        *,
        slot_values: Dict[str, str],
        slot_contract: List[Dict[str, Any]],
    ) -> List[str]:
        missing: List[str] = []
        values = slot_values or {}
        for slot in slot_contract:
            name = str(slot.get("slot", "") or "").strip()
            if not name or not bool(slot.get("required", False)):
                continue
            if not str(values.get(name, "") or "").strip():
                missing.append(name)
        return missing

    def _to_normalized_inputs(
        self,
        slot_values: Dict[str, str],
        extracted: Dict[str, Any],
    ) -> Dict[str, str]:
        kv = extracted.get("key_values", {}) or {}
        out = {
            "pdf_path": self._to_abs_or_keep(slot_values.get("pdf_path", "")),
            "checklist_path": self._to_abs_or_keep(slot_values.get("checklist_path", "")),
            "output_path": self._to_abs_or_keep(
                slot_values.get("output_path", "")
                or kv.get("output_path", "")
                or kv.get("output", "")
            ),
        }
        return out

    def _to_extra_slots(
        self,
        slot_values: Dict[str, str],
        slot_contract: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for slot in slot_contract:
            name = str(slot.get("slot", "") or "").strip()
            if not name:
                continue
            if str(slot.get("slot_kind", "path")).strip().lower() != "value":
                continue
            value = self._normalize_chapter_value(str(slot_values.get(name, "") or ""))
            if value:
                out[name] = value
        return out

    # ----------------------------- llm assist -----------------------------
    def _extract_paths_with_llm(
        self,
        *,
        user_input: str,
        slots: List[Dict[str, Any]],
        extracted: Dict[str, Any],
        llm_provider: str,
        llm_model: str,
    ) -> Tuple[Dict[str, str], str]:
        if not slots:
            return {}, ""
        provider = str(llm_provider or "openai").strip().lower()
        if provider == "gemini":
            return self._extract_paths_with_gemini(
                user_input=user_input,
                slots=slots,
                extracted=extracted,
                llm_model=llm_model or "gemini-2.5-flash",
            )
        return self._extract_paths_with_openai(
            user_input=user_input,
            slots=slots,
            extracted=extracted,
            llm_model=llm_model,
        )

    def _extract_paths_with_openai(
        self,
        *,
        user_input: str,
        slots: List[Dict[str, Any]],
        extracted: Dict[str, Any],
        llm_model: str,
    ) -> Tuple[Dict[str, str], str]:
        api_key = str(os.getenv("OPENAI_API_KEY", "") or "").strip()
        if not api_key:
            return {}, "未配置 OPENAI_API_KEY"
        base_url = str(os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").strip()
        model = str(llm_model or os.getenv("LLM_MODEL") or "gpt-4o-mini").strip()
        try:
            slot_desc = json.dumps(slots, ensure_ascii=False)
            extracted_desc = json.dumps(extracted, ensure_ascii=False)
            system_prompt = (
                "你是工作流参数语义抽取器。"
                "请根据 slot_contract 中的 slot_kind 提取参数："
                "slot_kind=path 时提取路径，slot_kind=value 时提取非路径值（如章节选择器）。"
                "不能编造用户未提及的参数。"
            )
            user_prompt = (
                "请仅输出 JSON。\n"
                "规则：\n"
                "1) slot_kind=path：只能返回输入中真实出现过的路径，支持 Windows/Linux/相对路径、中文和空格；\n"
                "2) slot_kind=value：按用户意图归一化输出（如 chapters 用分号分隔），但不能虚构未提及内容；\n"
                "3) 若某槽位无法判断，返回空字符串；\n"
                "4) 优先语义匹配，不按出现顺序盲选。\n\n"
                f"slots={slot_desc}\n"
                f"rule_candidates={extracted_desc}\n"
                f"user_input={user_input}\n\n"
                "输出格式："
                "{\"slot_values\":{\"pdf_path\":\"...\",\"checklist_path\":\"...\",\"output_path\":\"...\",\"chapter_selection\":\"...\"}}"
            )
            text = self._call_openai_chat(
                base_url=base_url,
                api_key=api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            obj = self._extract_json_object(text)
            if not isinstance(obj, dict):
                return {}, "OpenAI 未返回可解析 JSON"
            raw_slots = obj.get("slot_values", {})
            if not isinstance(raw_slots, dict):
                return {}, "OpenAI JSON 缺少 slot_values"
            slot_kind_map = {
                str(s.get("slot", "")).strip(): str(s.get("slot_kind", "path")).strip().lower()
                for s in (slots or [])
                if str(s.get("slot", "")).strip()
            }
            cleaned: Dict[str, str] = {}
            for k, v in raw_slots.items():
                key = str(k).strip()
                if not key:
                    continue
                kind = slot_kind_map.get(key, "path")
                if kind == "value":
                    val = self._normalize_chapter_value(str(v or ""))
                else:
                    val = self._normalize_token_path(str(v or ""))
                if val:
                    cleaned[key] = val
            return cleaned, ""
        except Exception as e:  # noqa: BLE001
            return {}, str(e)

    def _call_openai_chat(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        endpoint = base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as http_err:
            detail = http_err.read().decode("utf-8", errors="ignore") if hasattr(http_err, "read") else ""
            raise RuntimeError(f"OpenAI HTTPError {http_err.code}: {detail[:400]}") from http_err
        except urllib.error.URLError as url_err:
            raise RuntimeError(f"OpenAI 连接失败: {url_err}") from url_err
        try:
            obj = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"OpenAI 返回非 JSON: {raw[:300]}") from e
        choices = obj.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"OpenAI 返回缺少 choices: {str(obj)[:300]}")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            text_fragments: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_fragments.append(str(part.get("text", "")))
                elif isinstance(part, str):
                    text_fragments.append(part)
            return "\n".join(text_fragments).strip()
        return str(content or "").strip()

    def _extract_paths_with_gemini(
        self,
        *,
        user_input: str,
        slots: List[Dict[str, Any]],
        extracted: Dict[str, Any],
        llm_model: str,
    ) -> Tuple[Dict[str, str], str]:
        try:
            client = self._get_llm_client()
            if client is None:
                return {}, "未配置 GEMINI_API_KEY/GOOGLE_API_KEY 或 google-genai 依赖"

            slot_desc = json.dumps(slots, ensure_ascii=False)
            extracted_desc = json.dumps(extracted, ensure_ascii=False)
            prompt = (
                "你是工作流参数抽取助手。请从用户输入中提取参数，按给定 slot 映射。\n"
                "要求：\n"
                "1) slot_kind=path 时，只能返回给定文本里出现过的路径，不要编造；\n"
                "2) slot_kind=value 时允许语义规范化（如章节号列表），但不能虚构；\n"
                "3) 仅输出 JSON，不要解释。\n\n"
                f"slots={slot_desc}\n"
                f"rule_candidates={extracted_desc}\n"
                f"user_input={user_input}\n\n"
                "输出格式：{\"slot_values\":{\"pdf_path\":\"...\",\"checklist_path\":\"...\",\"chapter_selection\":\"...\"}}"
            )
            resp = client.models.generate_content(
                model=llm_model,
                contents=prompt,
            )
            text = str(getattr(resp, "text", "") or "")
            obj = self._extract_json_object(text)
            if not isinstance(obj, dict):
                return {}, "LLM 未返回可解析 JSON"
            raw_slots = obj.get("slot_values", {})
            if not isinstance(raw_slots, dict):
                return {}, "LLM JSON 缺少 slot_values"
            slot_kind_map = {
                str(s.get("slot", "")).strip(): str(s.get("slot_kind", "path")).strip().lower()
                for s in (slots or [])
                if str(s.get("slot", "")).strip()
            }
            cleaned: Dict[str, str] = {}
            for k, v in raw_slots.items():
                key = str(k).strip()
                if not key:
                    continue
                kind = slot_kind_map.get(key, "path")
                if kind == "value":
                    val = self._normalize_chapter_value(str(v or ""))
                else:
                    val = self._normalize_token_path(str(v or ""))
                if val:
                    cleaned[key] = val
            return cleaned, ""
        except Exception as e:  # noqa: BLE001
            return {}, str(e)

    def _get_llm_client(self):
        if self._llm_client is not None:
            return self._llm_client
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        if not api_key:
            return None
        try:
            from google import genai  # type: ignore
        except Exception:
            return None
        self._llm_client = genai.Client(api_key=api_key)
        return self._llm_client

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        raw = (text or "").strip()
        if not raw:
            return None
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
        # fenced json
        m = re.search(r"```json\s*(\{.*?\})\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(1))
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass
        # first object
        m2 = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
        if m2:
            try:
                obj = json.loads(m2.group(1))
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None
        return None

    # ----------------------------- path helpers -----------------------------
    @staticmethod
    def _suffix(p: str) -> str:
        return Path(p).suffix.lower()

    @staticmethod
    def _dedupe(items: List[str]) -> List[str]:
        out: List[str] = []
        seen: Set[str] = set()
        for item in items:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    @staticmethod
    def _looks_like_url(token: str) -> bool:
        s = (token or "").strip().lower()
        return s.startswith("http://") or s.startswith("https://")

    def _normalize_token_path(self, token: str) -> str:
        s = str(token or "").strip()
        if not s:
            return ""
        s = s.strip().strip('"').strip("'").strip("“").strip("”").strip("‘").strip("’")
        s = s.rstrip(",;")
        s = s.rstrip("。；，")
        s = s.strip()
        if not s:
            return ""
        if self._looks_like_url(s):
            return ""
        return s

    def _to_abs_or_keep(self, p: str) -> str:
        raw = self._normalize_token_path(p)
        if not raw:
            return ""
        if raw.startswith("~"):
            return str(Path(raw).expanduser())
        if self._is_windows_abs(raw):
            if os.name == "nt":
                return str(Path(raw).resolve())
            return raw
        if self._is_posix_abs(raw):
            if os.name != "nt":
                return str(Path(raw).resolve())
            return raw
        return str((self.project_root / raw).resolve())

    @staticmethod
    def _is_windows_abs(p: str) -> bool:
        s = (p or "").strip()
        if not s:
            return False
        if re.match(r"^[a-zA-Z]:[\\/]", s):
            return True
        if s.startswith("\\\\") or s.startswith("//"):
            return True
        return False

    @staticmethod
    def _is_posix_abs(p: str) -> bool:
        return bool(p and p.startswith("/"))
