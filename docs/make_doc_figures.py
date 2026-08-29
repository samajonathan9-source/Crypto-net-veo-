"""Figures de documentation — architecture, pipeline, installation, résultats."""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "figures"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.dpi": 130})


def architecture():
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.axis("off")
    boxes = [
        (0.5, 5.6, "FLUX RÉSEAU\n(connexions)", "#34495e"),
        (2.6, 5.6, "FENÊTRAGE\n30 conn. / pas 15", "#2c3e50"),
        (5.2, 7.0, "CLASSIQUES\nIF · OC-SVM · PCA-AE\n(symptômes)", "#7f8c8d"),
        (5.2, 4.2, "TOPOLOGIE RATISS\nP_sig · PR · edge\nentropie · KZ · frustration\n(structure)", "#2980b9"),
        (8.2, 5.6, "FUSION ADAPTATIVE\nrouteur centroïdes\n(bon canal/famille)", "#27ae60"),
        (10.9, 5.6, "ALERTE\n+ preuve SHA-256", "#c0392b"),
    ]
    for x, y, txt, col in boxes:
        ax.text(x, y, txt, ha="center", va="center", fontsize=10, fontweight="bold",
                color="white",
                bbox=dict(boxstyle="round,pad=0.45", facecolor=col, edgecolor="none"))
    arrows = [(0.5, 5.6, 2.2, 5.6), (2.6, 5.6, 4.7, 7.0), (2.6, 5.6, 4.7, 4.2)]
    arrows += [(5.2, 7.0, 7.75, 5.8), (5.2, 4.2, 7.75, 5.4), (8.2, 5.6, 10.4, 5.6)]
    for x0, y0, x1, y1 in arrows:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", lw=1.8, color="#2c3e50"))
    ax.set_xlim(-0.2, 11.6)
    ax.set_ylim(3.2, 8.2)
    ax.set_title("Architecture RATISS-Cyber — symptômes + structure → fusion adaptative",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "doc_architecture.png")
    plt.close(fig)


def installation():
    code = """$ git clone https://github.com/samajonathan9-source/Crypto-net-veo-.git
$ cd Crypto-net-veo-
$ pip install -r requirements.txt

# benchmark complet (synthétique)
$ PYTHONPATH=. python benchmarks/run_synthetic_validation.py

# validation trafic réel UNSW-NB15
$ PYTHONPATH=. python benchmarks/run_adaptive_fusion.py

# API (port 12000) + dashboard (port 12001)
$ PYTHONPATH=. python -m uvicorn api.server:app --port 12000
$ PYTHONPATH=. python -m streamlit run dashboard/app.py --server.port 12001
"""
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    ax.axis("off")
    ax.text(0.5, 0.5, code, family="monospace", fontsize=9.5, va="center", ha="center",
            bbox=dict(boxstyle="round,pad=0.8", facecolor="#2d2d2d", edgecolor="#444"))
    for t in ax.texts:
        t.set_color("#e6e6e6")
    ax.set_title("Schéma d'installation — 6 commandes du clone à la démo", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "doc_installation.png")
    plt.close(fig)


def results_summary():
    fig, ax = plt.subplots(figsize=(10, 5))
    groups = ["Synthétique\n(KS-validé)", "UNSW-NB15\n(trafic réel)"]
    classical = [0.44, 0.13]
    topo_adaptive = [0.61, 0.33]
    x = np.arange(len(groups))
    w = 0.36
    ax.bar(x - w / 2, classical, w, label="Classique", color="#7f8c8d")
    ax.bar(x + w / 2, topo_adaptive, w, label="RATISS-Cyber (fusion adaptative)", color="#2980b9")
    ax.set_ylabel("Rappel moyen")
    ax.set_title("Le système complet surpasse le classique — synthétique et réel",
                 fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylim(0, 0.75)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    for i, v in enumerate(classical):
        ax.text(i - w / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=9)
    for i, v in enumerate(topo_adaptive):
        ax.text(i + w / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "doc_results_summary.png")
    plt.close(fig)


def main():
    architecture()
    installation()
    results_summary()
    print(f"figures -> {FIG}/")
    for f in sorted(FIG.glob("doc_*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
