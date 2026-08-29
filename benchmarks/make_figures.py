"""Figures pour le papier SMI — RATISS-Cyber.

Génère les figures clés :
1. Rappel par canal et par famille (l'avantage unique)
2. Distributions PR : normal vs phase_transition (délocalisation spectrale)
3. Trajectoire Kibble-Zurek : cumul_drift le long du flux (campagne weaving)
4. Matrices de corrélation : normal vs les 3 attaques (la structure visible)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cyber.synthetic_attacks import build_synthetic_dataset
from cyber.topo_probe import window_correlation
from cyber.windowing import sliding_windows
from ratiss_topo.arsenal import KibbleZurekTracker
from ratiss_topo.robust_metrics import spectral_channels

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "figures"
FIG.mkdir(exist_ok=True)
WINDOW, STRIDE = 30, 10

plt.rcParams.update({"font.size": 11, "figure.dpi": 130})


def main() -> None:
    data = build_synthetic_dataset()
    X, labels = data["X"], data["labels"]
    starts, win_labels, purities = sliding_windows(X, labels, WINDOW, STRIDE)
    pure = purities == 1.0

    # --- canaux sur tout le flux ---
    ref_corr = window_correlation(X[labels == "normal"][:WINDOW])
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(ref_corr)
    pr, cumul = [], []
    for s in starts:
        corr = window_correlation(X[s : s + WINDOW])
        pr.append(spectral_channels(corr)["pr"])
        cumul.append(kz.update(corr)["cumul_drift"])
    pr, cumul = np.array(pr), np.array(cumul)

    families = ["weaving", "phase_transition", "slow_mutation"]
    pretty = {"weaving": "Tissage", "phase_transition": "Transition de phase",
              "slow_mutation": "Mutation lente (APT)", "normal": "Normal"}

    # ===== Figure 1 : rappel par canal et par famille =====
    fusion = __import__("json").loads(
        (ROOT / "artifacts" / "family_fusion.json").read_text())
    channels_shown = ["classical", "pr", "cumul_drift"]
    ch_pretty = {"classical": "Classique", "pr": "PR (topo)",
                 "cumul_drift": "KZ cumul (topo)"}
    # rappels @ FPR 2% de référence (recompute rapide pour classical)
    sv = __import__("json").loads(
        (ROOT / "artifacts" / "synthetic_validation.json").read_text())
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(families))
    w = 0.26
    recall_map = {
        "classical": {f: sv["results"]["classique"][f]["recall"] for f in families},
        "pr": {f: sv["results"]["spectral_PR"][f]["recall"] for f in families},
        "cumul_drift": {f: sv["results"]["KZ_cumul"][f]["recall"] for f in families},
    }
    colors = {"classical": "#888888", "pr": "#1f77b4", "cumul_drift": "#d62728"}
    for i, c in enumerate(channels_shown):
        vals = [recall_map[c][f] for f in families]
        ax.bar(x + (i - 1) * w, vals, w, label=ch_pretty[c], color=colors[c])
    ax.set_xticks(x)
    ax.set_xticklabels([pretty[f] for f in families])
    ax.set_ylabel("Rappel @ FPR 2%")
    ax.set_ylim(0, 1.0)
    ax.set_title("Chaque attaque a son observable topologique")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_rappel_par_canal.png")
    plt.close(fig)

    # ===== Figure 2 : distribution PR normal vs phase_transition =====
    fig, ax = plt.subplots(figsize=(7, 4.5))
    nm = pure & (win_labels == "normal")
    pm = pure & (win_labels == "phase_transition")
    ax.hist(pr[nm], bins=30, alpha=0.6, label="Normal", color="#1f77b4", density=True)
    ax.hist(pr[pm], bins=30, alpha=0.6, label="Transition de phase", color="#d62728", density=True)
    ax.set_xlabel("Participation ratio (PR)")
    ax.set_ylabel("Densité")
    ax.set_title("Délocalisation spectrale : la transition de phase fait monter le PR")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_pr_transition.png")
    plt.close(fig)

    # ===== Figure 3 : trajectoire KZ le long du flux =====
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors_cat = {"normal": "#1f77b4", "weaving": "#d62728",
                  "phase_transition": "#ff7f0e", "slow_mutation": "#2ca02c"}
    for cat in ["normal"] + families:
        m = pure & (win_labels == cat)
        ax.scatter(np.where(m)[0], cumul[m], s=8, alpha=0.5,
                   color=colors_cat[cat], label=pretty[cat])
    thr = np.percentile(cumul[nm], 98)
    ax.axhline(thr, color="k", ls="--", lw=1, label=f"Seuil FPR 2% ({thr:.2f})")
    ax.set_xlabel("Fenêtre (ordre du flux)")
    ax.set_ylabel("Cumul de drift Kibble-Zurek")
    ax.set_title("La structure dérive sous attaque — le tissage s'éloigne du normal")
    ax.legend(markerscale=2, fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_trajectoire_kz.png")
    plt.close(fig)

    # ===== Figure 4 : matrices de corrélation =====
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.8))
    for ax, cat in zip(axes, ["normal"] + families):
        pool = X[labels == cat]
        corr = window_correlation(pool[:WINDOW])
        im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_title(pretty[cat], fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("La structure des corrélations — invisible aux statistiques, visible en image")
    fig.colorbar(im, ax=axes, shrink=0.8, label="Corrélation")
    fig.tight_layout()
    fig.savefig(FIG / "fig4_matrices_correlation.png")
    plt.close(fig)

    print(f"Figures -> {FIG}/")
    for f in sorted(FIG.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
