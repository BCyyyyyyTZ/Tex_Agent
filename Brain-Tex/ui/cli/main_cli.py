# ============================================================
# ui/cli/main_cli.py — 命令行界面主入口
# ============================================================
# 基于 Click 框架实现的交互式命令行工具，
# 支持论文写作辅助、LaTeX 修复、文献搜索等功能的直接调用。
#
# 命令结构:
# neurotex chat               — 进入交互式对话模式
# neurotex fix <file.tex>     — 修复 LaTeX 文件错误
# neurotex search <query>     — 搜索论文
# neurotex analyze <data.csv> — 分析数据文件
# neurotex branch list        — 列出对话分支
# neurotex branch create <name> — 创建新分支
# neurotex session list       — 列出历史会话
# neurotex config             — 配置系统参数
#
# 交互式模式支持：
# - 带颜色的 Rich 渲染（表格/代码高亮/进度条）
# - Markdown 渲染（Agent 的 Markdown 响应）
# - 多行输入（\\ 结尾换行，空行提交）
# ============================================================

from __future__ import annotations
import click


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """NeuroTeX — 神经网络启发的多智能体论文写作协作系统"""
    pass


@cli.command()
@click.option("--session", "-s", default="", help="恢复指定会话 ID")
@click.option("--model", "-m", default="auto", help="指定使用的 LLM 模型")
def chat(session: str, model: str):
    """进入交互式对话模式（【需要实现】）"""
    click.echo("欢迎使用 NeuroTeX！输入 /help 查看命令，Ctrl+C 退出。")
    # 【需要实现】Rich 渲染的交互式对话循环


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--output", "-o", default="", help="输出文件路径")
def fix(file_path: str, output: str):
    """修复 LaTeX 文件错误（【需要实现】）"""
    click.echo(f"正在分析: {file_path}")
    # 【需要实现】调用 LaTeXValidator + LaTeXAgent


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="最多返回的结果数")
def search(query: str, limit: int):
    """搜索学术论文（【需要实现】）"""
    # 【需要实现】调用 LiteratureAgent 并以 Rich Table 格式输出


@cli.command()
@click.argument("data_path", type=click.Path(exists=True))
def analyze(data_path: str):
    """分析数据文件（【需要实现】）"""
    # 【需要实现】调用 AnalysisAgent


if __name__ == "__main__":
    cli()
