import pandas as pd
import psycopg2
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
from config import DATABASE_URL

SQL_PATH     = Path("sql/feature_engineering.sql")
FEATURES_CSV = Path("features/features_scaled.csv")
RAW_CSV      = Path("features/features_raw.csv")

# Columns that will be scaled — cgpa included because ML needs it normalized
SCALE_COLS = [
    'cgpa', 'total_problems', 'avg_difficulty',
    'consistency_score', 'commit_frequency'
]

def run_feature_sql():
    """Execute the SQL pipeline to populate the features table."""
    sql = SQL_PATH.read_text()
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Feature SQL executed — features table updated.")
    finally:
        conn.close()

def load_features() -> pd.DataFrame:
    """Pull features + cgpa from DB into a single DataFrame."""
    query = """
        SELECT
            s.id         AS student_id,
            s.name,
            s.branch,
            s.cgpa,
            f.total_problems,
            f.avg_difficulty,
            f.consistency_score,
            f.commit_frequency
        FROM  students s
        JOIN  features  f ON s.id = f.student_id
        ORDER BY s.id
    """
    conn = psycopg2.connect(DATABASE_URL)
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df

def scale_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Min-Max scaling to numeric feature columns.
    Saves raw CSV before scaling for reference and debugging.
    """
    import joblib

    # Save raw (unscaled) version — useful for Phase 5 insight thresholds
    df.to_csv(RAW_CSV, index=False)
    print(f"Raw features saved → {RAW_CSV}")

    df_scaled = df.copy()
    scaler = MinMaxScaler()
    df_scaled[SCALE_COLS] = scaler.fit_transform(df[SCALE_COLS])

    joblib.dump(scaler, Path('models/scaler.pkl'))
    print("Scaler saved → models/scaler.pkl")

    # Round to 4 decimal places — keeps CSV readable
    df_scaled[SCALE_COLS] = df_scaled[SCALE_COLS].round(4)
    df_scaled.to_csv(FEATURES_CSV, index=False)
    print(f"Scaled features saved → {FEATURES_CSV}")
    return df_scaled

def print_summary(raw: pd.DataFrame, scaled: pd.DataFrame):
    """Print a side-by-side summary for quick sanity checking."""
    print("\n── Raw feature ranges ──────────────────")
    print(raw[SCALE_COLS].agg(['min', 'max', 'mean']).round(3))
    print("\n── Scaled feature ranges (should all be 0–1) ──")
    print(scaled[SCALE_COLS].agg(['min', 'max', 'mean']).round(3))
    print("\n── Per-student scaled features ─────────")
    print(scaled[['name'] + SCALE_COLS].to_string(index=False))

if __name__ == "__main__":
    run_feature_sql()          # Step 1: populate features table
    raw    = load_features()   # Step 2: pull into Pandas
    scaled = scale_features(raw)  # Step 3: scale + export CSVs
    print_summary(raw, scaled) # Step 4: sanity check output