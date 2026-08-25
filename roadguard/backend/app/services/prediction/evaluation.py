"""
Evaluation service for RoadGuard Predictive Analytics.
Computes performance metrics for classifier and regressor validation.
"""
from __future__ import annotations

import numpy as np
from typing import Dict, Any
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    auc,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    mean_absolute_error,
    root_mean_squared_error
)


def evaluate_classifier(y_true: np.ndarray | list, y_pred_prob: np.ndarray | list) -> Dict[str, Any]:
    """
    Compute classification metrics for deterioration risk.
    """
    y_t = np.array(y_true)
    y_p_prob = np.array(y_pred_prob)
    
    # Binary predictions thresholded at 0.5
    y_p_bin = (y_p_prob >= 0.5).astype(int)

    # Handlers for single-class datasets (to avoid errors in validation splits)
    unique_classes = np.unique(y_t)
    if len(unique_classes) < 2:
        roc_auc = 0.5
        pr_auc = 0.5
    else:
        try:
            roc_auc = float(roc_auc_score(y_t, y_p_prob))
        except Exception:
            roc_auc = 0.5

        try:
            precisions, recalls, _ = precision_recall_curve(y_t, y_p_prob)
            pr_auc = float(auc(recalls, precisions))
        except Exception:
            pr_auc = 0.5

    # Compute standard metrics
    prec = float(precision_score(y_t, y_p_bin, zero_division=0))
    rec = float(recall_score(y_t, y_p_bin, zero_division=0))
    f1 = float(f1_score(y_t, y_p_bin, zero_division=0))
    
    cm = confusion_matrix(y_t, y_p_bin)
    # Ensure cm is 2x2 even with single class
    tn, fp, fn, tp = 0, 0, 0, 0
    if cm.size == 4:
        tn, fp, fn, tp = (int(v) for v in cm.ravel())
    elif cm.size == 1:
        if unique_classes[0] == 0:
            tn = int(cm[0, 0])
        else:
            tp = int(cm[0, 0])

    return {
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "confusion_matrix": {
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp
        }
    }


def evaluate_regressor(y_true: np.ndarray | list, y_pred: np.ndarray | list) -> Dict[str, Any]:
    """
    Compute regression metrics for future health index estimation.
    """
    y_t = np.array(y_true)
    y_p = np.array(y_pred)
    
    mae = mean_absolute_error(y_t, y_p)
    rmse = root_mean_squared_error(y_t, y_p)
    
    return {
        "mae": round(float(mae), 4),
        "rmse": round(float(rmse), 4)
    }
