"""Dashboard RATISS-Cyber — démo temps réel (Streamlit).

Simule un flux réseau (normal + injection d'attaques topologiques) et montre
en direct : les scores des canaux, la fusion, les alertes et leurs preuves
SHA-256. C'est l'interface de la démo SMI.

Lancer : streamlit run dashboard/app.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

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

st.set_page_config(page_title="RATISS-Cyber", page_icon="🛡️", layout="wide")

WINDOW = 30


@st.cache_resource
def load_engine():
    data = build_synthetic_dataset()
    X, labels = data["X"], data["labels"]
    X_normal = X[labels == "normal"]
    detectors = [
        IsolationForestDetector().fit(X_normal),
        OneClassSVMDetector().fit(X_normal),
        PCAAutoencoderDetector().fit(X_normal),
    ]
    engine = FusionEngine(w_classical=0.5, w_topo=0.5)
    # calibration sur fenêtres normales
    calib = {"classical": [], "psig": [], "edge": [], "entropie": [],
             "drift": [], "neg_energy": [], "pr": [],
             "frustration": [], "cumul_drift": []}
    corrs = []
    ref_corr = window_correlation(X_normal[:WINDOW])
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(ref_corr)
    for s in range(0, 300, 10):
        win = X_normal[s : s + WINDOW]
        corr = window_correlation(win)
        corrs.append(corr)
        topo = coupled_metric(corr)
        spec = spectral_channels(corr)
        kzr = kz.update(corr)
        calib["classical"].append(max(d.score(win).mean() for d in detectors))
        calib["psig"].append(topo["psig_seuille"])
        calib["edge"].append(topo["edge"])
        calib["entropie"].append(topo["entropie"])
        calib["neg_energy"].append(spec["neg_energy"])
        calib["pr"].append(spec["pr"])
        calib["frustration"].append(triad_frustration(corr))
        calib["cumul_drift"].append(kzr["cumul_drift"])
    calib["drift"] = [0.0] + [float(np.linalg.norm(corrs[i] - corrs[i-1]))
                              for i in range(1, len(corrs))]
    engine.calibrate({k: np.array(v) for k, v in calib.items()})
    combined = np.array([engine.combine({k: calib[k][i] for k in calib})
                         for i in range(len(corrs))])
    threshold = float(np.percentile(combined, 98))
    return data, detectors, engine, threshold, ref_corr


def score_window(win, detectors, engine, prev_corr, kz):
    corr = window_correlation(win)
    topo = coupled_metric(corr)
    spec = spectral_channels(corr)
    drift = float(np.linalg.norm(corr - prev_corr)) if prev_corr is not None else 0.0
    kzr = kz.update(corr)
    scores = {
        "classical": float(max(d.score(win).mean() for d in detectors)),
        "psig": topo["psig_seuille"], "edge": topo["edge"],
        "entropie": topo["entropie"], "drift": drift,
        "neg_energy": spec["neg_energy"], "pr": spec["pr"],
        "frustration": triad_frustration(corr),
        "cumul_drift": kzr["cumul_drift"],
    }
    combined = engine.combine(scores)
    return scores, combined, corr


def main() -> None:
    st.title("🛡️ RATISS-Cyber — Détection d'intrusion topologique")
    st.caption("Les classiques voient les symptômes. RATISS voit la structure. "
               "La fusion voit les deux — et chaque alerte est prouvée (SHA-256).")

    data, detectors, engine, threshold, ref_corr = load_engine()
    X, labels = data["X"], data["labels"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Poids fusion", f"{engine.w_classical:.1f} classique / {engine.w_topo:.1f} topo")
    col2.metric("Seuil adaptatif (FPR 2%)", f"{threshold:.3f}")
    col3.metric("Canaux", "9 dont PR · frustration · cumul KZ")

    st.divider()
    st.subheader("Simuler une fenêtre de trafic")
    scenario = st.selectbox(
        "Type de trafic injecté",
        ["normal", "weaving (tissage)", "phase_transition (transition de phase)",
         "slow_mutation (APT lent)"],
    )
    cat = scenario.split(" ")[0]
    campagne = st.checkbox("Mode campagne (séquence de 4 fenêtres — cumul KZ)",
                           value=(cat in ("weaving", "slow_mutation")))

    if st.button("🔍 Analyser", type="primary"):
        pool = X[labels == cat]
        rng = np.random.default_rng()
        prev_corr = window_correlation(X[labels == "normal"][:WINDOW])
        kz = KibbleZurekTracker(window=12)
        kz.set_reference(ref_corr)

        n_win = 4 if campagne else 1
        results = []
        for w in range(n_win):
            start = int(rng.integers(0, len(pool) - WINDOW))
            win = pool[start : start + WINDOW]
            scores, combined, _ = score_window(win, detectors, engine, prev_corr, kz)
            results.append((scores, combined))

        scores, combined = results[-1]
        alert = combined >= threshold

        if alert:
            st.error(f"🚨 ALERTE — score fusion {combined:.3f} ≥ seuil {threshold:.3f}")
        else:
            st.success(f"✅ Trafic sain — score fusion {combined:.3f} < seuil {threshold:.3f}")

        st.write(f"**Vérité terrain** : `{cat}` — "
                 + ("✔️ détection correcte" if (alert == (cat != "normal")) else "❌ erreur"))

        if campagne and len(results) > 1:
            st.write("**Trajectoire de la campagne (mémoire Kibble-Zurek)**")
            traj = pd.DataFrame({
                "fenêtre": list(range(1, len(results) + 1)),
                "score fusion": [r[1] for r in results],
                "cumul_drift": [r[0]["cumul_drift"] for r in results],
            }).set_index("fenêtre")
            st.line_chart(traj)
            st.caption("Le cumul_drift s'accumule si l'attaque persiste — "
                       "le système 'se souvient' de la transition (hystérésis).")

        c1, c2 = st.columns(2)
        with c1:
            st.write("**Canaux (scores bruts)**")
            df = pd.DataFrame({
                "canal": list(scores.keys()),
                "score": [round(v, 4) for v in scores.values()],
            })
            st.bar_chart(df.set_index("canal"))
        with c2:
            st.write("**Preuve SHA-256 de l'alerte**")
            proof = window_proof(win, scores, "ALERTE" if alert else "OK")
            st.code(proof, language=None)
            st.caption("Hash des données brutes + scores + décision. "
                       "Vérifiable par un tiers sans nous faire confiance.")

    st.divider()
    st.subheader("Ce que montre cette démo")
    st.markdown("""
- **Attaques invisibles aux statistiques** : les trois attaques synthétiques
  passent les tests KS (≥ 90% des features indistinguables du normal)
- **Chaque attaque a son observable** : PR voit la transition de phase
  (rappel 0.95), le cumul Kibble-Zurek voit le tissage en campagne (0.79),
  la frustration voit les triangles frustrés
- **Arsenal RATISS** : hystérésis (mémoire), Kibble-Zurek (gel + dérive),
  tissage KTN (frustration des triades)
- **Preuve vérifiable** : chaque alerte embarque un hash SHA-256
""")


if __name__ == "__main__":
    main()
