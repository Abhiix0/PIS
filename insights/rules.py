# =====================================================
# Insight Engine — Rule Definitions
# All thresholds use RAW feature values (not scaled)
# so they remain human-interpretable.
# =====================================================

from dataclasses import dataclass

RULES_VERSION = "1"  # bump when any threshold or message changes


@dataclass
class Rule:
    feature: str  # which feature this rule watches
    threshold: float  # raw value boundary
    direction: str  # 'below' or 'above'
    weakness_label: str  # short label for the weakness dict
    strength_label: str  # short label when condition NOT triggered
    weakness_msg: str  # human-readable weakness description
    recommendation: str  # specific, actionable next step
    strength_msg: str  # positive reinforcement when strong

    def is_weak(self, raw_value: float) -> bool:
        if self.direction == "below":
            return raw_value < self.threshold
        return raw_value > self.threshold


# ── Rule table — all thresholds are deliberate, not arbitrary ─────────
RULES: list[Rule] = [
    Rule(
        feature="total_problems",
        threshold=50,
        direction="below",
        weakness_label="low_dsa_volume",
        strength_label="strong_dsa_volume",
        weakness_msg="Only {value} problems solved — most companies filter at 75+",
        recommendation="Solve 2–3 LeetCode problems daily. Target medium difficulty. "
        "Focus on arrays, strings, and trees first.",
        strength_msg="{value} problems solved — strong DSA volume",
    ),
    Rule(
        feature="avg_difficulty",
        threshold=1.5,
        direction="below",
        weakness_label="low_problem_depth",
        strength_label="good_problem_depth",
        weakness_msg="Avg difficulty {value:.2f}/3.0 — mostly easy problems, "
        "which do not reflect interview-level questions",
        recommendation="Shift 60% of practice to medium and hard problems. "
        "Study patterns: sliding window, two pointers, DP basics.",
        strength_msg="Avg difficulty {value:.2f}/3.0 — tackling challenging problems",
    ),
    Rule(
        feature="consistency_score",
        threshold=0.4,
        direction="below",
        weakness_label="low_consistency",
        strength_label="consistent_practice",
        weakness_msg="Active only {pct}% of weeks in last 90 days — "
        "burst activity does not build retention",
        recommendation="Block 45 minutes daily for coding practice. "
        "Use a habit tracker. Consistency matters more than volume.",
        strength_msg="Active {pct}% of weeks — consistent practice habit",
    ),
    Rule(
        feature="commit_frequency",
        threshold=0.3,
        direction="below",
        weakness_label="low_github_activity",
        strength_label="active_github_presence",
        weakness_msg="Only {value:.2f} commits/day — weak project portfolio signal",
        recommendation="Start or revive one GitHub project this week. "
        "Aim for daily commits. Recruiters scan contribution graphs.",
        strength_msg="{value:.2f} commits/day — strong project activity",
    ),
    Rule(
        feature="cgpa",
        threshold=6.5,
        direction="below",
        weakness_label="low_cgpa",
        strength_label="solid_academic_record",
        weakness_msg="CGPA {value:.1f} is below the screening threshold "
        "for many product companies (typically 6.5–7.0)",
        recommendation="Focus on upcoming semester grades. "
        "Consider companies with no CGPA cutoff while improving.",
        strength_msg="CGPA {value:.1f} — meets most company screening criteria",
    ),
]
