import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

MODEL_DIR = "models"


def get_model(model_type="random_forest"):
    """Return a sklearn Pipeline with scaler + classifier."""
    if model_type == "random_forest":
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
    elif model_type == "gradient_boosting":
        clf = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', clf)
    ])
    return pipeline


def train(train_df=None, test_df=None, model_type="random_forest",
          data_path="data/dataset.csv", save_model=True):
    """
    Train model on NSL-KDD (train_df/test_df) or synthetic CSV (data_path).
    Returns: model, X_test, y_test, feature_names
    """
    os.makedirs(MODEL_DIR, exist_ok=True)

    # --- Load data ---
    if train_df is not None:
        # NSL-KDD path: pre-split data passed in
        X_train = train_df.drop('congestion', axis=1)
        y_train = train_df['congestion']

        if test_df is not None:
            X_test = test_df.drop('congestion', axis=1)
            y_test = test_df['congestion']
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X_train, y_train, test_size=0.2, stratify=y_train, random_state=42
            )
    else:
        # Synthetic CSV path
        data = pd.read_csv(data_path)
        X = data.drop('congestion', axis=1)
        y = data['congestion']
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=42
        )

    feature_names = list(X_train.columns)
    print(f"\nTraining {model_type} on {len(X_train)} samples "
          f"({len(feature_names)} features)...")

    # --- Cross-validation ---
    model = get_model(model_type)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train, y_train, cv=cv,
                                scoring='f1_weighted', n_jobs=-1)
    print(f"5-Fold CV F1 (weighted): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # --- Final fit ---
    model.fit(X_train, y_train)
    print("Training complete.")

    # --- Save model ---
    if save_model:
        model_path = os.path.join(MODEL_DIR, f"{model_type}_congestion.pkl")
        joblib.dump(model, model_path)
        print(f"Model saved -> {model_path}")

    return model, X_test, y_test, feature_names


if __name__ == "__main__":
    model, X_test, y_test, features = train()
