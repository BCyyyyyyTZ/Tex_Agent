# ============================================================
# scripts/migrate_db.py — 数据库迁移脚本
# ============================================================
# 管理 NeuroTeX 关系数据库（SQLite/PostgreSQL）的结构变更，
# 确保数据库 schema 与当前代码版本保持同步。
# 基于 Alembic 迁移框架实现版本控制。
#
# 数据库表结构（需要创建的核心表）:
# ┌─────────────────────────────────────────────────────────┐
# │ users           — 用户账户（id/email/api_key_hash/...）  │
# │ sessions        — 会话记录（id/user_id/created_at/...）  │
# │ episodes        — 情节记忆（id/session_id/summary/...）  │
# │ routing_records — 路由历史（id/task/agent/outcome/...）  │
# │ audit_logs      — 审计日志（id/event/user/ip/...）       │
# │ documents       — 文档记录（id/user_id/path/type/...）   │
# │ user_resources  — 用户知识库（id/user_id/file/tags/...） │
# └─────────────────────────────────────────────────────────┘
#
# 使用方式：
#   python scripts/migrate_db.py init      # 初始化迁移仓库
#   python scripts/migrate_db.py upgrade   # 升级到最新版本
#   python scripts/migrate_db.py downgrade # 回退一个版本
#   python scripts/migrate_db.py status    # 查看当前版本
#   python scripts/migrate_db.py create "add user table"  # 创建新迁移
# ============================================================

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_init() -> None:
    """
    初始化 Alembic 迁移仓库。
    【需要实现】
    - alembic init migrations
    - 配置 alembic.ini 中的数据库连接 URL（从 settings 读取）
    """
    print("🔧 初始化数据库迁移仓库...")
    # 【需要实现】subprocess.run(["alembic", "init", "migrations"])
    print("✅ 迁移仓库初始化完成，请检查 alembic.ini 配置")


def cmd_upgrade(revision: str = "head") -> None:
    """
    执行数据库升级迁移。
    【需要实现】alembic upgrade {revision}
    """
    print(f"⬆️  升级数据库到 {revision}...")
    # 【需要实现】subprocess.run(["alembic", "upgrade", revision])
    print("✅ 数据库升级完成")


def cmd_downgrade(revision: str = "-1") -> None:
    """
    回退数据库迁移。
    【需要实现】alembic downgrade {revision}
    """
    print(f"⬇️  回退数据库迁移（{revision}）...")
    # 【需要实现】
    print("✅ 数据库回退完成")


def cmd_status() -> None:
    """
    查看当前迁移状态。
    【需要实现】alembic current + alembic history
    """
    print("📋 当前数据库迁移状态：")
    # 【需要实现】
    pass


def cmd_create(message: str) -> None:
    """
    创建新的迁移文件。
    【需要实现】alembic revision --autogenerate -m "{message}"
    """
    print(f"📝 创建迁移文件：{message}")
    # 【需要实现】
    pass


def cmd_create_tables_directly() -> None:
    """
    不使用 Alembic，直接用 SQLAlchemy 创建所有表（开发模式快速建表）。
    【需要实现】
    - 从 config/settings.py 读取数据库 URL
    - 定义所有 ORM 模型并调用 Base.metadata.create_all(engine)
    """
    print("🏗️  直接创建数据库表（开发模式）...")
    # 【需要实现】
    print("✅ 所有数据库表创建完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroTeX 数据库迁移管理")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="初始化迁移仓库")
    subparsers.add_parser("upgrade", help="升级到最新版本")
    subparsers.add_parser("downgrade", help="回退一个版本")
    subparsers.add_parser("status", help="查看当前版本")
    create_parser = subparsers.add_parser("create", help="创建新迁移文件")
    create_parser.add_argument("message", help="迁移描述")
    subparsers.add_parser("init-tables", help="直接创建所有表（开发模式）")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "upgrade": cmd_upgrade,
        "downgrade": cmd_downgrade,
        "status": cmd_status,
        "init-tables": cmd_create_tables_directly,
    }

    if args.command == "create":
        cmd_create(args.message)
    elif args.command in commands:
        commands[args.command]()
    else:
        parser.print_help()
