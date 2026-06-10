"""
ui.web.server 的单元测试（不启动 Web 服务）。

覆盖点：
1) 静态资源存在性检查：确保 Web UI 的关键入口文件未缺失。

说明：
- 该文件只做“静态资源完整性”验证，不启动服务、不发起 HTTP 请求。
"""

from __future__ import annotations

from pathlib import Path

def test_static_assets_exist() -> None:
    """
    Web UI 依赖静态目录：若关键入口文件缺失，将导致 UI 无法正常加载。
    """
    repo_root = Path(__file__).resolve().parents[1]
    static_dir = repo_root / "ui" / "web" / "static"
    assert static_dir.exists() and static_dir.is_dir()
    must = ["index.html", "app.js", "styles.css"]
    for name in must:
        p = static_dir / name
        assert p.exists(), f"missing static asset: {p}"
