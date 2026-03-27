# ============================================================
# scripts/train_router.py — ML 路由模型训练脚本
# ============================================================
# 使用历史路由记录（RoutingRecord）训练 MLRouter 的分类模型，
# 提升路由决策的准确性和适应性。
#
# 训练流程:
# 1. 从数据库加载历史 RoutingRecord（需要 >= 100 条有效记录）
# 2. 提取特征向量（task embedding + complexity + category）
# 3. 标签编码（target_agent_type + model → 类别标签）
# 4. 划分训练集/验证集（80/20）
# 5. 训练分类模型（默认：Random Forest，可选 XGBoost/MLP）
# 6. 评估模型性能（Accuracy / F1-score / Confusion Matrix）
# 7. 保存模型到 data/models/router_model.pkl
# 8. 更新路由器配置，启用 ML 路由
#
# 使用方式：
#   python scripts/train_router.py
#   python scripts/train_router.py --model xgboost --min-samples 200
#   python scripts/train_router.py --evaluate-only  # 只评估不训练
# ============================================================

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def load_training_data(min_samples: int = 100) -> list:
    """
    从数据库加载历史路由记录。
    【需要实现】
    - 连接数据库，查询 RoutingRecord 表
    - 过滤掉 outcome=partial 的不确定样本
    - 确保各类别样本均衡（必要时做过采样）
    - 如数据量不足，抛出提示并退出
    """
    print(f"📊 加载历史路由记录（最少需要 {min_samples} 条）...")
    return []  # 【需要实现】


def prepare_features(records: list) -> tuple:
    """
    提取特征矩阵和标签向量。
    【需要实现】
    - 调用 EmbeddingGenerator 批量生成任务描述嵌入
    - 拼接复杂度特征、类别 one-hot 等
    - 返回 (X_train, X_test, y_train, y_test)
    """
    print("🔧 提取特征向量...")
    return None, None, None, None  # 【需要实现】


def train_model(
    X_train, y_train, model_type: str = "random_forest"
) -> object:
    """
    训练分类模型。
    【需要实现】
    支持 random_forest / xgboost / mlp
    """
    print(f"🤖 训练 {model_type} 模型...")
    return None  # 【需要实现】


def evaluate_model(model, X_test, y_test) -> dict:
    """
    评估模型并打印报告。
    【需要实现】
    - sklearn.metrics: accuracy_score, f1_score, classification_report
    - 输出混淆矩阵
    """
    print("📈 评估模型性能...")
    return {}  # 【需要实现】


def save_model(model, output_path: str = "data/models/router_model.pkl") -> None:
    """保存模型到文件，【需要实现】使用 joblib.dump()"""
    print(f"💾 保存模型到 {output_path}")
    pass  # 【需要实现】


async def main(args: argparse.Namespace) -> None:
    print("🚀 NeuroTeX ML 路由模型训练开始...")
    records = await load_training_data(min_samples=args.min_samples)
    if not records:
        print("⚠️  数据不足，无法训练模型。请积累更多使用记录后重试。")
        return

    X_train, X_test, y_train, y_test = prepare_features(records)

    if not args.evaluate_only:
        model = train_model(X_train, y_train, model_type=args.model)
        metrics = evaluate_model(model, X_test, y_test)
        save_model(model)
        print(f"\n✅ 训练完成！验证集准确率: {metrics.get('accuracy', 'N/A'):.2%}")
    else:
        print("仅评估模式，【需要实现加载已有模型并评估】")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroTeX ML 路由模型训练")
    parser.add_argument("--model", default="random_forest",
                        choices=["random_forest", "xgboost", "mlp"])
    parser.add_argument("--min-samples", type=int, default=100)
    parser.add_argument("--evaluate-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args))
