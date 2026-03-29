import pandas as pd
from pathlib import Path

# Weights must sum to 100 — each represents % contribution to readiness
WEIGHTS = {
    'cgpa':             20,
    'total_problems':   15,
    'avg_difficulty':   20,
    'consistency_score':25,
    'commit_frequency': 20,
}

def compute_readiness_score(row: pd.Series) -> float:
    """Weighted sum of scaled features → readiness score 0–100."""
    return round(
        sum(row[col] * weight for col, weight in WEIGHTS.items()),
        2
    )

def score_to_category(score: float) -> str:
    if   score >= 65: return 'Ready'
    elif score >= 40: return 'Near Ready'
    else:            return 'Needs Improvement'

def generate_labels(df_scaled: pd.DataFrame) -> pd.DataFrame:
    """Add readiness_score and category columns to the scaled DataFrame."""
    df = df_scaled.copy()
    df['readiness_score'] = df.apply(compute_readiness_score, axis=1)
    df['category']        = df['readiness_score'].apply(score_to_category)
    return df

if __name__ == "__main__":
    df_scaled = pd.read_csv('features/features_scaled.csv')
    df_labeled = generate_labels(df_scaled)
    print(df_labeled[['name', 'readiness_score', 'category']])
    df_labeled.to_csv('features/features_labeled.csv', index=False)