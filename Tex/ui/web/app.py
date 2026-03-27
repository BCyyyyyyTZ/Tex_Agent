# ============================================================
# ui/web/app.py — Gradio Web 界面
# ============================================================
# 基于 Gradio 构建的轻量级 Web 界面，让非命令行用户
# 也能方便地使用 NeuroTeX 的核心功能。
#
# 界面布局（三栏式）:
# ┌─────────────────────────────────────────────────────┐
# │  左栏（会话/分支管理）                               │
# │  - 会话列表（历史 + 新建）                           │
# │  - 分支树形视图（可切换/创建/合并）                  │
# ├──────────────────────────────────────────────────────┤
# │  中央栏（主对话区）                                   │
# │  - Chatbot 组件（Markdown 渲染）                     │
# │  - 文件上传拖拽区                                    │
# │  - 输入框 + 发送按钮                                 │
# ├──────────────────────────────────────────────────────┤
# │  右栏（Agent 工具区）                                 │
# │  - 当前任务状态面板                                   │
# │  - 产出物预览（LaTeX/图表）                           │
# │  - 快捷功能按钮（文献搜索/数据分析/LaTeX修复）        │
# └─────────────────────────────────────────────────────┘
#
# 核心函数:
# - create_gradio_app(): 构建并返回 gr.Blocks 实例
# - chat_fn(message, history, session_id): 对话处理函数
# - upload_file_fn(file): 文件上传处理
# - search_fn(query): 快速论文搜索
# - build_branch_tree(): 生成分支树展示数据
# ============================================================

from __future__ import annotations
from typing import Any, Dict, Generator, List, Optional


def create_gradio_app():
    """
    创建 Gradio Web 界面。
    【需要实现】
    - 使用 gr.Blocks() 构建布局
    - 绑定对话、上传、搜索等事件处理函数
    - 返回 gr.Blocks 实例
    """
    pass


async def chat_fn(
    message: str,
    history: List[List[str]],
    session_id: str,
) -> Generator[str, None, None]:
    """
    Gradio 对话处理函数（流式生成）。
    【需要实现】
    - 调用 API 的 /agents/chat 端点（SSE 流式）
    - yield 每个 token 更新界面
    """
    pass


if __name__ == "__main__":
    app = create_gradio_app()
    # app.launch(server_name="0.0.0.0", server_port=7860, share=False)
