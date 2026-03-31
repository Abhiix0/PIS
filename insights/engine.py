import json
import pandas as pd
from pathlib        import Path
from ingest.db_connection import get_connection
from insights.rules import RULES

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

        return {
            'student_id':      student_id,
            'student_name':    data['name'],
            'readiness_score': data['readiness_score'],
            'category':        data['category'],
            'strengths':       result['strengths'],
            'weaknesses':      ranked,
            'recommendations': self._build_recommendations(ranked),
            'top_priority':    ranked[0]['recommendation'] if ranked else 'No critical gaps detected.',
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
        # Normalise nullable prediction fields
        if row['readiness_score'] is not None:
            row['readiness_score'] = float(row['readiness_score'])
        row['category'] = row['category'] if row['category'] else 'Unknown'
        return row

    def _run_rules(self, data: dict) -> dict:
        """Fire every rule against raw feature values.
        Returns separate strengths and weaknesses lists.
        """
        strengths  = []
        weaknesses = []

        for rule in RULES:
            value = data[rule.feature]

            if rule.is_weak(value):
                # Format the message with actual values
                pct = int(value * 100) if rule.feature == 'consistency_score' else None
                msg = rule.weakness_msg.format(
                    value=value,
                    pct=pct if pct is not None else value
                )
                weaknesses.append({
                    'feature':        rule.feature,
                    'label':           rule.weakness_label,
                    'message':         msg,
                    'recommendation':  rule.recommendation,
                    'raw_value':       round(value, 3),
                    'importance':      self.importances.get(rule.feature, 0.0),
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
        """Sort detected weaknesses by ML feature importance (descending).
        The most model-significant weakness becomes recommendation #1.
        This is the ML layer of the hybrid system.
        """
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
    import json

    engine = InsightEngine()

    for sid in [1, 3, 5, 7, 8]:
        result = engine.format_insight(sid)

        print(f"\n{'='*55}")
        print(f"  {result['student_name']} | Score: {result['readiness_score']} | {result['category']}")
        print(f"  Strengths : {[s['label'] for s in result['strengths']]}")
        print(f"  Weaknesses: {[w['label'] for w in result['weaknesses']]}")
        print(f"  Top priority → {result['top_priority'][:80]}...")