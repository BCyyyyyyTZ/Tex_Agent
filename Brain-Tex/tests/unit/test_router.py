# ============================================================
# tests/unit/test_router.py — 路由模块单元测试
# ============================================================
# 验证任务分类、复杂度估算、规则路由等核心路由逻辑。
#
# 测试范围:
# ┌─────────────────────────────────────────────────────────┐
# │ TestTaskClassifier                                      │
# │  - test_literature_keywords_classified_correctly        │
# │  - test_emotional_keywords_trigger_companion_category   │
# │  - test_latex_error_keywords_classified_correctly       │
# │  - test_confidence_above_threshold_for_clear_input      │
# │  - test_entity_extraction_finds_arxiv_id               │
# ├─────────────────────────────────────────────────────────┤
# │ TestComplexityEstimator                                 │
# │  - test_simple_question_scores_low                      │
# │  - test_multi_step_task_scores_high                     │
# │  - test_recommend_correct_agent_architecture            │
# │  - test_recommend_correct_model_tier                    │
# ├─────────────────────────────────────────────────────────┤
# │ TestRuleBasedRouter                                     │
# │  - test_literature_query_routes_to_literature_agent     │
# │  - test_high_complexity_routes_to_planner               │
# │  - test_emotional_input_routes_to_companion             │
# │  - test_default_fallback_routes_to_simple_agent         │
# │  - test_add_custom_rule_takes_precedence                │
# └─────────────────────────────────────────────────────────┘
# ============================================================

import pytest


# ─── TaskClassifier Tests ────────────────────────────────────

class TestTaskClassifier:

    def test_literature_keywords_classified_correctly(self):
        """包含"文献"/"arXiv"的输入应分类为 LITERATURE_SEARCH，【需要实现】"""
        from router.task_classifier import TaskClassifier, TaskCategory
        clf = TaskClassifier()
        result = clf.classify("帮我找一些关于 Transformer 的 arXiv 论文")
        assert result.primary_category == TaskCategory.LITERATURE_SEARCH

    def test_emotional_keywords_trigger_companion(self):
        """包含"难受"/"焦虑"应分类为 EMOTIONAL_SUPPORT，【需要实现】"""
        from router.task_classifier import TaskClassifier, TaskCategory
        clf = TaskClassifier()
        result = clf.classify("我好焦虑，论文写不下去了")
        assert result.primary_category == TaskCategory.EMOTIONAL_SUPPORT

    def test_latex_error_keywords_classified_correctly(self):
        """包含"LaTeX"/"error"应分类为 LATEX_SYNTAX_FIX，【需要实现】"""
        pass

    def test_confidence_above_threshold_for_clear_input(self):
        """明确输入的分类置信度应 >= 0.7，【需要实现】"""
        pass


# ─── ComplexityEstimator Tests ───────────────────────────────

class TestComplexityEstimator:

    def test_simple_question_scores_low(self):
        """简单问句（如"LaTeX 怎么写表格？"）复杂度应 < 0.4，【需要实现】"""
        from router.complexity_estimator import ComplexityEstimator
        from router.task_classifier import TaskCategory
        estimator = ComplexityEstimator()
        score = estimator.estimate("LaTeX 怎么写表格？", TaskCategory.GENERAL_QA)
        assert score.overall < 0.4

    def test_multi_step_task_scores_high(self):
        """多步骤复杂任务（检索+分析+写作）复杂度应 > 0.7，【需要实现】"""
        pass

    def test_recommend_correct_agent_architecture(self):
        """低复杂度推荐 SimpleAgent，高复杂度推荐 PlannerAgent，【需要实现】"""
        pass


# ─── RuleBasedRouter Tests ───────────────────────────────────

class TestRuleBasedRouter:

    def test_emotional_input_routes_to_companion(self):
        """情感类输入路由到 CompanionAgent，【需要实现】"""
        from router.routing_strategies.rule_based_router import RuleBasedRouter
        router = RuleBasedRouter()
        decision = router.route("我好累好沮丧")
        assert "companion" in decision.target_agent_type.lower()

    def test_add_custom_rule_takes_precedence(self):
        """自定义规则优先级高于默认规则，【需要实现】"""
        pass

    def test_default_fallback_routes_to_simple_agent(self):
        """无规则匹配时使用默认路由（SimpleAgent），【需要实现】"""
        pass
