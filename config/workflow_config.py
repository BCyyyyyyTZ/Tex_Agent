"""
工作流节点与边配置。

本文件描述不含 RAG 的基础三节点线性拓扑：
    Design → Think → Execute

RAG 说明
--------
当 build_graph(rag_pipeline=pipeline) 传入 RAG 管道时，
graph_builder.py 会跳过本文件的 WORKFLOW_EDGES，
动态插入 Retrieve 节点形成四节点拓扑：
    Design → Retrieve → Think → Execute

这是有意的设计：基础配置与可选扩展节点分离，
避免在不启用 RAG 时引入额外的节点定义。

未来可扩展为从 YAML/JSON 配置文件动态加载图结构（参见 workflow/workflow_parser.py）。
"""
from typing import List, Tuple

# 节点执行顺序列表
WORKFLOW_NODES: List[str] = ["design", "think", "execute"]

# 线性边定义：(起始节点, 目标节点)
WORKFLOW_EDGES: List[Tuple[str, str]] = [
    ("design", "think"),
    ("think", "execute"),
]

# 工作流入口节点
ENTRY_NODE: str = "design"

# 工作流终止节点
FINISH_NODE: str = "execute"

# TODO: 未来在此处接入用户自定义工作流配置（YAML/JSON 解析），
#       支持动态组装 Graph 节点与边
