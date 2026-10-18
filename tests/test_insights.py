from insights.rules import RULES, Rule

# ── Test the rule detection layer in isolation ────────────────────────


def get_rule(feature: str) -> Rule:
    return next(r for r in RULES if r.feature == feature)


def test_low_problems_triggers_weakness():
    rule = get_rule("total_problems")
    assert rule.is_weak(30)  # 30 < 50 → should be weak


def test_high_problems_no_weakness():
    rule = get_rule("total_problems")
    assert not rule.is_weak(120)  # 120 >= 50 → should be strong


def test_boundary_value_total_problems():
    rule = get_rule("total_problems")
    assert not rule.is_weak(50)  # exactly at threshold → not weak


def test_zero_commit_frequency_is_weak():
    rule = get_rule("commit_frequency")
    assert rule.is_weak(0.0)  # student 8 edge case


def test_perfect_consistency_not_weak():
    rule = get_rule("consistency_score")
    assert not rule.is_weak(1.0)


def test_all_rules_have_required_fields():
    for rule in RULES:
        assert rule.feature
        assert rule.recommendation  # must have actionable text
        assert rule.weakness_label
        assert rule.strength_label


def test_ranking_puts_highest_importance_first():
    """Engine should rank weaknesses by importance descending."""
    from insights.engine import InsightEngine

    engine = InsightEngine()
    weaknesses = [
        {
            "feature": "total_problems",
            "importance": 0.15,
            "label": "x",
            "message": "",
            "recommendation": "",
            "raw_value": 10,
        },
        {
            "feature": "consistency_score",
            "importance": 0.42,
            "label": "y",
            "message": "",
            "recommendation": "",
            "raw_value": 0.1,
        },
    ]
    ranked = engine._rank_by_importance(weaknesses)
    assert ranked[0]["feature"] == "consistency_score"  # 0.42 > 0.15
