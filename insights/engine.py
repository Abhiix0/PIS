import json
import pandas as pd
from pathlib          import Path
from ingest.db_connection import get_connection
from insights.rules   import RULES

IMPORTANCES_PATH = Path('models/feature_importances.json')


class InsightEngine:

    def __init__(self):
        # Load importances once at instantiation — not on every call
        raw = json.loads(IMPORTANCES_PATH.read_text())
        self.importances = raw['regressor']  # use regressor importances

    # ── Public API ────────────────────────────────────────────────────

    def format_insight(self, student_id: int) -> dict:
        """Main entry point. Returns structured insight dict for a student."""
        data   = self._fetch_student_data(student_id)
        result = self._run_rules(data)
        ranked = self._rank_by_importance(result['weaknesses'])

        # Score velocity — how much has the score changed in 7 days?
        delta, trend = self._fetch_score_velocity(student_id, data.get('readiness_score'))

        # Cross-rule composite patterns
        composites = self._generate_composite_insights(
            data, result['weaknesses'], result['strengths']
        )

        return {
            'student_id':         student_id,
            'student_name':       data['name'],
            'readiness_score':    data['readiness_score'],
            'category':           data['category'],
            'score_delta_7d':     delta,
            'score_trend':        trend,
            'strengths':          result['strengths'],
            'weaknesses':         ranked,
            'composite_insights': composites,
            'recommendations':    self._build_recommendations(ranked),
            'top_priority':       ranked[0]['recommendation'] if ranked else 'No critical gaps detected.',
        }

    # ── Private methods ───────────────────────────────────────────────

    def _fetch_student_data(self, student_id: int) -> dict:
        """Fetch all required student data in a single query."""
        query = """
            SELECT s.name, s.cgpa,
                   f.total_problems, f.avg_difficulty,
                   f.consistency_score, f.commit_frequency,
                   p.readiness_score, p.category
            FROM   students s
            JOIN   features f ON s.id = f.student_id
            LEFT JOIN predictions p ON s.id = p.student_id
            WHERE  s.id = %(sid)s
        """
        with get_connection() as conn:
            df = pd.read_sql(query, conn, params={'sid': student_id})
        if df.empty:
            raise ValueError(
                f"Student {student_id} not found or has no features computed. "
                "Run POST /predict/{student_id} first."
            )
        row = df.iloc[0].to_dict()
        if row['readiness_score'] is not None:
            row['readiness_score'] = float(row['readiness_score'])
        row['category'] = row['category'] if row['category'] else 'Unknown'
        return row

    def _fetch_score_velocity(
        self, student_id: int, current_score: float | None
    ) -> tuple[float | None, str | None]:
        """Compute 7-day score delta from prediction_history.

        Returns (delta, trend_label) or (None, None) if insufficient history.
        """
        if current_score is None:
            return None, None

        query = """
            SELECT readiness_score
            FROM   prediction_history
            WHERE  student_id = %(sid)s
              AND  recorded_at <= NOW() - INTERVAL '7 days'
            ORDER BY recorded_at DESC
            LIMIT 1
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {'sid': student_id})
                row = cur.fetchone()

        if not row:
            return None, None  # not enough history yet

        past_score = float(row[0])
        delta = round(current_score - past_score, 2)

        if delta > 5:
            trend = "↑ improving fast"
        elif delta > 0:
            trend = "↑ improving"
        elif delta < -5:
            trend = "↓ declining"
        elif delta < 0:
            trend = "↓ slipping"
        else:
            trend = "→ stagnant"

        return delta, trend

    def _generate_composite_insights(
        self, data: dict, weaknesses: list, strengths: list
    ) -> list[dict]:
        """Detect cross-rule patterns that individual rules can't express.

        These fire when a combination of strengths and weaknesses creates a
        specific, actionable situation — more useful than generic advice.
        """
        weak_set   = {w['label'] for w in weaknesses}
        strong_set = {s['label'] for s in strengths}
        composites = []

        # Good coder, bad visibility — strong DSA but no GitHub presence
        if 'low_github_activity' in weak_set and 'low_dsa_volume' not in weak_set:
            composites.append({
                'pattern': 'invisible_coder',
                'message': 'Strong problem-solver with low public visibility — '
                           'your skills are not visible to recruiters.',
                'action':  'Document your DSA solutions in a GitHub repo. '
                           '50 well-commented solutions > 10 empty repos.',
            })

        # Consistent but shallow — good habit, wrong difficulty
        if 'consistent_practice' in strong_set and 'low_problem_depth' in weak_set:
            composites.append({
                'pattern': 'consistent_but_shallow',
                'message': 'Excellent consistency, but easy problems daily '
                           'builds habit without building interview skill.',
                'action':  'Keep the same schedule, shift to medium difficulty. '
                           'Same time investment, 3× the interview impact.',
            })

        # High GitHub, low DSA — project-builder who can't pass screening
        if 'active_github_presence' in strong_set and 'low_dsa_volume' in weak_set:
            composites.append({
                'pattern': 'builder_not_solver',
                'message': 'Strong project portfolio but insufficient DSA practice — '
                           'most companies screen on algorithms before reviewing projects.',
                'action':  'Dedicate 30 minutes daily to LeetCode before any project work. '
                           'Reach 75 problems before your next application cycle.',
            })

        # Low consistency AND low volume — needs a structured plan
        if 'low_consistency' in weak_set and 'low_dsa_volume' in weak_set:
            composites.append({
                'pattern': 'needs_structure',
                'message': 'Both practice volume and consistency are below threshold — '
                           'sporadic effort is not compounding.',
                'action':  'Start a 30-day streak: one problem per day, any difficulty. '
                           'Habit first, difficulty second.',
            })

        return composites

    def _run_rules(self, data: dict) -> dict:
        """Fire every rule against raw feature values."""
        strengths  = []
        weaknesses = []

        for rule in RULES:
            value = data[rule.feature]

            if rule.is_weak(value):
                pct = int(value * 100) if rule.feature == 'consistency_score' else None
                msg = rule.weakness_msg.format(
                    value=value,
                    pct=pct if pct is not None else value
                )
                weaknesses.append({
                    'feature':       rule.feature,
                    'label':         rule.weakness_label,
                    'message':       msg,
                    'recommendation': rule.recommendation,
                    'raw_value':     round(value, 3),
                    'importance':    self.importances.get(rule.feature, 0.0),
                })
            else:
                msg = rule.strength_msg.format(
                    value=value,
                    pct=int(value * 100) if rule.feature == 'consistency_score' else value
                )
                strengths.append({
                    'feature': rule.feature,
                    'label':   rule.strength_label,
                    'message': msg,
                })

        return {'strengths': strengths, 'weaknesses': weaknesses}

    def _rank_by_importance(self, weaknesses: list) -> list:
        """Sort weaknesses by ML feature importance (descending)."""
        return sorted(weaknesses, key=lambda w: w['importance'], reverse=True)

    def _build_recommendations(self, ranked_weaknesses: list) -> list[dict]:
        """Convert ranked weaknesses into a tiered recommendation list."""
        tiers = ['critical', 'important', 'suggested']
        result = []
        for i, w in enumerate(ranked_weaknesses):
            result.append({
                'priority':       i + 1,
                'tier':           tiers[min(i, len(tiers) - 1)],
                'area':           w['label'],
                'action':         w['recommendation'],
                'why_it_matters': f"Feature importance: {w['importance']:.3f}",
            })
        return result


if __name__ == "__main__":
    engine = InsightEngine()

    for sid in [1, 3, 5, 7, 8]:
        result = engine.format_insight(sid)

        print(f"\n{'='*55}")
        score_line = f"Score: {result['readiness_score']}"
        if result.get('score_trend'):
            score_line += f"  {result['score_trend']} ({result['score_delta_7d']:+.1f})"
        print(f"  {result['student_name']} | {score_line} | {result['category']}")
        print(f"  Strengths  : {[s['label'] for s in result['strengths']]}")
        print(f"  Weaknesses : {[w['label'] for w in result['weaknesses']]}")
        if result['composite_insights']:
            print(f"  Composites : {[c['pattern'] for c in result['composite_insights']]}")
        print(f"  Top priority → {result['top_priority'][:80]}...")
