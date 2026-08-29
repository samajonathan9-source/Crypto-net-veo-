"""Benchmark Phase 1 — algorithmes classiques sur NSL-KDD.

Protocole honnête et reproductible :
- entraînement sur KDDTrain+ (sous-ensemble fixe, seed 42)
- évaluation sur KDDTest+ (jamais vu, avec ses attaques inédites — c'est
  la difficulté connue de NSL-KDD et un bon test de généralisation)
- métriques : accuracy, precision, recall, F1, FPR, AUC, temps d'inférence
- sortie : artifacts/benchmark_nsl_kdd.json

Usage : python benchmarks/run_nsl_kdd.py [--train-size 40000] [--test-size 10000]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from cyber.classical_detectors import ALL_DETECTORS
from cyber.datasets import load_nsl_kdd

ROOT = Path(__file__).resolve().parent.parent


def evaluate(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    y_pred = (scores >= threshold).astype(int)
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "fpr": float(fp / max(fp + tn, 1)),
        "auc": float(roc_auc_score(y_true, scores)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-size", type=int, default=40_000)
    parser.add_argument("--test-size", type=int, default=10_000)
    args = parser.parse_args()

    rng = np.random.default_rng(42)
    data = load_nsl_kdd(ROOT / "data/KDDTrain+.txt", ROOT / "data/KDDTest+.txt")

    idx = rng.choice(len(data["X_train"]), args.train_size, replace=False)
    X_train, y_train = data["X_train"][idx], data["y_train"][idx]
    idx = rng.choice(len(data["X_test"]), args.test_size, replace=False)
    X_test, y_test = data["X_test"][idx], data["y_test"][idx]

    scaler = StandardScaler().fit(X_train)
    X_train_s, X_test_s = scaler.transform(X_train), scaler.transform(X_test)
    # sous-ensemble normal pour les détecteurs non supervisés
    X_normal = X_train_s[y_train == 0]

    results = {}
    for cls in ALL_DETECTORS:
        det = cls()
        supervised = cls.__name__ == "RandomForestDetector"
        t0 = time.perf_counter()
        det.fit(X_train_s if supervised else X_normal, y_train if supervised else None)
        t_fit = time.perf_counter() - t0

        t0 = time.perf_counter()
        scores = det.score(X_test_s)
        t_infer = (time.perf_counter() - t0) / len(X_test_s) * 1000  # ms/échantillon

        # seuil : médiane des scores sur le train (normal) pour l'unsupervisé,
        # 0.5 pour le supervisé
        ref = det.score(X_normal if not supervised else X_train_s)
        threshold = float(np.percentile(ref, 95)) if not supervised else 0.5

        metrics = evaluate(y_test, scores, threshold)
        metrics["fit_time_s"] = round(t_fit, 2)
        metrics["infer_ms_per_sample"] = round(t_infer, 4)
        results[det.name] = metrics
        print(f"{det.name:20s} F1={metrics['f1']:.3f} FPR={metrics['fpr']:.3f} "
              f"AUC={metrics['auc']:.3f} infer={metrics['infer_ms_per_sample']:.3f}ms")

    out = {
        "dataset": "NSL-KDD",
        "train_size": args.train_size,
        "test_size": args.test_size,
        "seed": 42,
        "protocol": "binaire normal/attaque, StandardScaler, seuil p95 (unsup) ou 0.5 (sup)",
        "results": results,
    }
    out_path = ROOT / "artifacts/benchmark_nsl_kdd.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n-> {out_path}")


if __name__ == "__main__":
    main()
