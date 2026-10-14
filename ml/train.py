import pandas as pd
import joblib
import json
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.dummy import DummyRegressor, DummyClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    mean_squared_error, r2_score,
    classification_report, accuracy_score
)
from ml.labels import generate_labels

from ml.bundle import FEATURE_COLS, create_candidate

MODELS_DIR = Path('models/staging')  # training never writes live files; create_candidate freezes a bundle

def load_data():
    """Load and label the featured dataset."""
    if not Path('features/features_scaled.csv').exists():
        raise FileNotFoundError("Missing 'features/features_scaled.csv'. Run your feature engineering script first!")
    
    df = pd.read_csv('features/features_scaled.csv')
    df = generate_labels(df)
    X = df[FEATURE_COLS]
    y_score = df['readiness_score']
    y_category = df['category']
    return df, X, y_score, y_category

def compare_baselines(X, y_score, y_cat):
    """Establish the 'minimum bar' for model performance."""
    print("\n── Baseline Comparison ─────────────────────")

    # Regression baseline: always predict the mean score
    dummy_r = DummyRegressor(strategy='mean')
    cv_r = cross_val_score(dummy_r, X, y_score, cv=3, scoring='neg_root_mean_squared_error')
    print(f"   Dummy Regressor RMSE : {-cv_r.mean():.2f}")

    # Classification baseline: always predict majority class
    dummy_c = DummyClassifier(strategy='most_frequent')
    cv_c = cross_val_score(dummy_c, X, y_cat, cv=3, scoring='accuracy')
    print(f"   Dummy Classifier Acc : {cv_c.mean():.2f}")

# ── Regression: predict continuous readiness score (0–100) ───────────
def train_regressor(X, y):
    print("\n── Regression Model ────────────────────────")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42
    )

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    print(f"   RMSE : {rmse:.2f}  (lower is better)")
    print(f"   R²   : {r2:.3f}  (1.0 = perfect fit)")

    # Cross-validation for robust estimation
    cv_scores = cross_val_score(
        RandomForestRegressor(n_estimators=100, random_state=42),
        X, y, cv=3, scoring='neg_root_mean_squared_error'
    )
    print(f"   CV RMSE: {-cv_scores.mean():.2f} ± {cv_scores.std():.2f}")

    print_feature_importances(model, X.columns, label="Regressor")
    joblib.dump(model, MODELS_DIR / 'regressor.pkl')
    print(f"   Saved → models/regressor.pkl")
    return model

# ── Classification: predict category label ────────────────────────────
def train_classifier(X, y):
    print("\n── Classification Model ────────────────────")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    print(f"   Accuracy : {accuracy_score(y_test, y_pred):.2f}")
    print("\n   Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    cv_scores = cross_val_score(
        RandomForestClassifier(n_estimators=100, random_state=42),
        X, y, cv=3, scoring='accuracy'
    )
    print(f"   CV Accuracy: {cv_scores.mean():.2f} ± {cv_scores.std():.2f}")

    print_feature_importances(model, X.columns, label="Classifier")
    joblib.dump(model, MODELS_DIR / 'classifier.pkl')
    print(f"   Saved → models/classifier.pkl")
    return model

def print_feature_importances(model, feature_names, label: str):
    importances = sorted(
        zip(feature_names, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    print(f"\n   Feature Importances ({label}):")
    for name, score in importances:
        bar = '█' * int(score * 40)
        print(f"    {name:<22} {score:.3f}  {bar}")

def export_importances(regressor, classifier, feature_names):
    """Save feature importances as JSON for Phase 5 Insight Engine.
    Logs a warning if any feature's importance shifted by > 0.1 vs previous run.
    """
    reg_imp = dict(zip(feature_names, regressor.feature_importances_.tolist()))
    clf_imp = dict(zip(feature_names, classifier.feature_importances_.tolist()))

    output = {'regressor': reg_imp, 'classifier': clf_imp}

    path = MODELS_DIR / 'feature_importances.json'

    # Drift detection — compare against previous importances if they exist
    if path.exists():
        try:
            old = json.loads(path.read_text())
            old_reg = old.get('regressor', {})
            drifted = [
                f"{feat}: {old_reg[feat]:.3f} → {reg_imp[feat]:.3f}"
                for feat in reg_imp
                if feat in old_reg and abs(reg_imp[feat] - old_reg[feat]) > 0.1
            ]
            if drifted:
                print(f"\n⚠️  Feature importance drift detected (Δ > 0.1):")
                for d in drifted:
                    print(f"    {d}")
            else:
                print("\n✅ Feature importances stable (no drift > 0.1)")
        except Exception:
            pass  # don't fail training on drift check errors

    path.write_text(json.dumps(output, indent=2))
    print(f"\n✅ All-in-one Bridge Saved → {path}")
    return output

if __name__ == "__main__":
    # 1. Initialize
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    df, X, y_score, y_cat = load_data()

    print("\nWARNING: labels are SYNTHETIC (formula + noise). Demo model only; not a placement predictor.")
    print("\n── Label Distribution ──────────────────────")
    print(df['category'].value_counts().to_string())

    # 2. Compare against dummy baseline
    compare_baselines(X, y_score, y_cat)

    # 3. Train models
    regressor  = train_regressor(X, y_score)
    classifier = train_classifier(X, y_cat)
    
    # 4. Export bridge for Insight Engine
    export_importances(regressor, classifier, FEATURE_COLS)

    # 5. Freeze a candidate bundle (scaler fitted by features.compute travels with the models).
    # It is NOT active: approve and activate it explicitly (python -m ml.bundle ...).
    import shutil
    shutil.copy(Path('models/scaler.pkl'), MODELS_DIR / 'scaler.pkl')
    print("Candidate bundle:", create_candidate(MODELS_DIR, {"label_origin": "synthetic_formula"}))
