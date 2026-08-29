"""API d'alerte RATISS-Cyber — FastAPI.

Endpoints :
- GET  /health      : état du système + intégrité
- POST /analyze     : analyse une fenêtre de trafic -> scores + alerte + preuve SHA-256
- GET  /stats       : statistiques du moteur (canaux, poids, seuil)

Le serveur embarque le pipeline Phase 2/3 : détecteurs classiques + canaux
topologiques + fusion + preuve. Pattern éprouvé dans ratiss-Skynet.
"""

from __future__ import annotations

import time

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

from cyber.classical_detectors import (
    IsolationForestDetector,
    OneClassSVMDetector,
    PCAAutoencoderDetector,
)
from cyber.fusion_engine import FusionEngine, window_proof
from cyber.synthetic_attacks import build_synthetic_dataset
from cyber.topo_probe import window_correlation
from ratiss_topo.arsenal import KibbleZurekTracker, triad_frustration
from ratiss_topo.robust_metrics import coupled_metric, spectral_channels

app = FastAPI(title="RATISS-Cyber", version="0.3.0")

# --- état global du moteur (calibré au démarrage sur trafic normal synthétique) ---
STATE: dict = {}


class WindowRequest(BaseModel):
    """Une fenêtre de trafic : matrice (n_connexions, n_features)."""
    window: list[list[float]]


@app.on_event("startup")
def startup() -> None:
    data = build_synthetic_dataset()
    X_normal = data["X"][data["labels"] == "normal"]
    detectors = [
        IsolationForestDetector().fit(X_normal),
        OneClassSVMDetector().fit(X_normal),
        PCAAutoencoderDetector().fit(X_normal),
    ]
    # calibration de la fusion sur fenêtres normales
    engine = FusionEngine(w_classical=0.5, w_topo=0.5)
    normal_scores = {"classical": [], "psig": [], "edge": [], "entropie": [],
                     "drift": [], "neg_energy": [], "pr": [],
                     "frustration": [], "cumul_drift": []}
    corrs = []
    ref_corr = window_correlation(X_normal[:30])
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(ref_corr)
    for s in range(0, 300, 10):
        win = X_normal[s : s + 30]
        corr = window_correlation(win)
        corrs.append(corr)
        topo = coupled_metric(corr)
        spec = spectral_channels(corr)
        kzr = kz.update(corr)
        normal_scores["classical"].append(max(d.score(win).mean() for d in detectors))
        normal_scores["psig"].append(topo["psig_seuille"])
        normal_scores["edge"].append(topo["edge"])
        normal_scores["entropie"].append(topo["entropie"])
        normal_scores["neg_energy"].append(spec["neg_energy"])
        normal_scores["pr"].append(spec["pr"])
        normal_scores["frustration"].append(triad_frustration(corr))
        normal_scores["cumul_drift"].append(kzr["cumul_drift"])
    drift = [0.0] + [float(np.linalg.norm(corrs[i] - corrs[i-1])) for i in range(1, len(corrs))]
    normal_scores["drift"] = drift
    engine.calibrate({k: np.array(v) for k, v in normal_scores.items()})
    combined = np.array([
        engine.combine({k: normal_scores[k][i] for k in normal_scores})
        for i in range(len(corrs))
    ])
    STATE.update({
        "detectors": detectors,
        "engine": engine,
        "threshold": float(np.percentile(combined, 98)),
        "ref_corr": ref_corr,
        "kz": KibbleZurekTracker(window=12),
        "n_start": time.time(),
        "n_analyzed": 0,
        "n_alerts": 0,
    })
    STATE["kz"].set_reference(ref_corr)


def analyze_window(win: np.ndarray) -> dict:
    detectors = STATE["detectors"]
    engine = STATE["engine"]
    corr = window_correlation(win)
    topo = coupled_metric(corr)
    spec = spectral_channels(corr)
    kzr = STATE["kz"].update(corr)  # mémoire du flux (Kibble-Zurek)
    scores = {
        "classical": float(max(d.score(win).mean() for d in detectors)),
        "psig": topo["psig_seuille"],
        "edge": topo["edge"],
        "entropie": topo["entropie"],
        "drift": 0.0,  # une fenêtre isolée n'a pas de trajectoire locale
        "neg_energy": spec["neg_energy"],
        "pr": spec["pr"],
        "frustration": triad_frustration(corr),
        "cumul_drift": kzr["cumul_drift"],
    }
    combined = engine.combine(scores)
    alert = bool(combined >= STATE["threshold"])
    STATE["n_analyzed"] += 1
    STATE["n_alerts"] += int(alert)
    return {
        "alert": alert,
        "combined_score": round(combined, 4),
        "threshold": round(STATE["threshold"], 4),
        "channels": {k: round(v, 4) for k, v in scores.items()},
        "proof_sha256": window_proof(win, scores, "ALERTE" if alert else "OK"),
    }


@app.get("/health")
def health() -> dict:
    return {
        "status": "operational",
        "version": "0.3.0",
        "uptime_s": round(time.time() - STATE.get("n_start", time.time()), 1),
        "analyzed": STATE.get("n_analyzed", 0),
        "alerts": STATE.get("n_alerts", 0),
    }


@app.get("/stats")
def stats() -> dict:
    engine = STATE["engine"]
    return {
        "fusion_weights": {"classical": engine.w_classical, "topo": engine.w_topo},
        "threshold": STATE["threshold"],
        "channels": ["classical", "psig", "edge", "entropie", "drift",
                     "neg_energy", "pr", "frustration", "cumul_drift"],
        "analyzed": STATE["n_analyzed"],
        "alerts": STATE["n_alerts"],
    }


@app.post("/analyze")
def analyze(req: WindowRequest) -> dict:
    win = np.array(req.window, dtype=float)
    if win.ndim != 2 or win.shape[0] < 3:
        return {"error": "window must be (n_connexions>=3, n_features)"}
    return analyze_window(win)
