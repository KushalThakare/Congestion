import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # headless / no display needed
import os
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix, roc_auc_score, roc_curve,
    ConfusionMatrixDisplay
)

RESULTS_DIR = "results"


def evaluate(model, X_test, y_test, feature_names=None, save_plots=True):
    os.makedirs(RESULTS_DIR, exist_ok=True)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] \
             if hasattr(model, "predict_proba") else None

    # ── Core Metrics ──────────────────────────────────────────────────────────
    acc     = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob) if y_prob is not None else None

    print("\n" + "="*55)
    print("         NETWORK CONGESTION DETECTION — RESULTS")
    print("="*55)
    print(f"  Accuracy  : {acc:.4f}")
    if roc_auc:
        print(f"  ROC-AUC   : {roc_auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=["Normal (0)", "Congested (1)"]))

    if save_plots:
        _plot_confusion_matrix(y_test, y_pred)
        if y_prob is not None:
            _plot_roc_curve(y_test, y_prob, roc_auc)
        if feature_names is not None:
            _plot_feature_importance(model, feature_names)

    return {"accuracy": acc, "roc_auc": roc_auc}


def _plot_confusion_matrix(y_test, y_pred):
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm,
                                  display_labels=["Normal", "Congested"])
    fig, ax = plt.subplots(figsize=(6, 5))
    disp.plot(ax=ax, colorbar=False, cmap='Blues')
    ax.set_title("Confusion Matrix", fontsize=14, fontweight='bold')
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "confusion_matrix.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved → {path}")


def _plot_roc_curve(y_test, y_prob, roc_auc):
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, color='steelblue', lw=2,
            label=f"ROC Curve (AUC = {roc_auc:.4f})")
    ax.plot([0, 1], [0, 1], color='gray', linestyle='--', lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve", fontsize=14, fontweight='bold')
    ax.legend(loc="lower right")
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "roc_curve.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved → {path}")


def _plot_feature_importance(model, feature_names, top_n=20):
    # Works for Pipeline wrapping RandomForest or GradientBoosting
    clf = model.named_steps.get('classifier', model)
    if not hasattr(clf, 'feature_importances_'):
        return

    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]
    top_features = [feature_names[i] for i in indices]
    top_scores   = importances[indices]

    fig, ax = plt.subplots(figsize=(9, max(4, top_n * 0.35)))
    bars = ax.barh(top_features[::-1], top_scores[::-1], color='steelblue')
    ax.set_xlabel("Importance Score")
    ax.set_title(f"Top {top_n} Feature Importances", fontsize=14, fontweight='bold')
    ax.bar_label(bars, fmt='%.4f', padding=3, fontsize=8)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "feature_importance.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved → {path}")
