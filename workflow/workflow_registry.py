"""
工作流注册表加载器。

职责：
1. 从 config/workflow_registry.json 读取“名称 -> 工作流规格”映射（具体图定义在 config/workflow/*.json）
2. 支持 file 规格：通过 YAML/JSON 配置文件解析动态图
3. 所有 workflow（包含 default）统一转换为 nodes / edges
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from workflow.workflow_parser import YAMLWorkflowParser, NodeConfig, EdgeConfig


class WorkflowRegistry:
    """按名称加载用户自定义工作流配置。"""

    def __init__(self, registry_path: Optional[str] = None):
        project_root = Path(__file__).resolve().parent.parent
        self.registry_path = Path(registry_path) if registry_path else project_root / "config" / "workflow_registry.json"
        self._parser = YAMLWorkflowParser()

    def _load_mapping(self) -> Dict[str, Any]:
        """读取工作流映射，文件不存在时返回空映射。"""
        if not self.registry_path.exists():
            return {}

        with self.registry_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        workflows = data.get("workflows", {})
        if not isinstance(workflows, dict):
            raise ValueError("workflow_registry.json 中 workflows 必须是对象映射")

        # 统一 key 为 str；value 可为 str（兼容旧格式）或 dict（新规格）
        normalized: Dict[str, Any] = {}
        for k, v in workflows.items():
            normalized[str(k)] = v
        return normalized

    def list_workflows(self) -> List[str]:
        """返回可用工作流名称列表。"""
        return sorted(self._load_mapping().keys())

    def get_workflow_spec(self, workflow_name: str) -> Dict[str, Any]:
        """
        获取工作流规格。
        兼容格式：
        - "name": "config/xxx.json"         -> {"type":"file","path":"..."}
        - "name": {"type":"file","path":"..."}
        """
        workflows = self._load_mapping()
        if workflow_name not in workflows:
            available = ", ".join(sorted(workflows.keys())) if workflows else "（空）"
            raise ValueError(f"未知工作流: {workflow_name}。可用工作流: {available}")

        raw_spec = workflows[workflow_name]
        if isinstance(raw_spec, str):
            return {"type": "file", "path": raw_spec}

        if not isinstance(raw_spec, dict):
            raise ValueError(f"工作流 '{workflow_name}' 配置非法，必须是字符串路径或对象")

        wf_type = str(raw_spec.get("type", "")).strip()
        if wf_type == "file":
            wf_path = raw_spec.get("path")
            if not wf_path:
                raise ValueError(f"工作流 '{workflow_name}' 缺少 path")
            return {"type": "file", "path": str(wf_path)}

        raise ValueError(f"工作流 '{workflow_name}' 的 type 不受支持: {wf_type}")

    def get_config_path(self, workflow_name: str) -> Path:
        """根据工作流名称解析 file 类型配置文件绝对路径。"""
        spec = self.get_workflow_spec(workflow_name)
        if spec.get("type") != "file":
            raise ValueError(f"工作流 '{workflow_name}' 不是 file 类型，无法读取配置路径")

        raw_path = Path(spec["path"])
        if not raw_path.is_absolute():
            raw_path = self.registry_path.parent.parent / raw_path

        config_path = raw_path.resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"工作流配置文件不存在: {config_path}")

        return config_path

    def load_graph_config(self, workflow_name: str) -> Tuple[List[NodeConfig], List[EdgeConfig]]:
        """
        加载指定 file 工作流并解析为 nodes / edges。
        """
        config_path = self.get_config_path(workflow_name)
        config = self._parser.load_config(str(config_path))
        nodes = self._parser.parse_nodes(config)
        edges = self._parser.parse_edges(config)
        return nodes, edges
