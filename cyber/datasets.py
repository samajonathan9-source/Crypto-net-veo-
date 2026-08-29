"""Chargeurs de datasets cybersécurité — Phase 1 RATISS-Cyber.

NSL-KDD : 41 features + label + difficulté. Binaire (normal/attaque) ou
multi-classe (DoS, Probe, R2L, U2R). Les features catégorielles
(protocol_type, service, flag) sont one-hot encodées.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

NSL_KDD_COLUMNS = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in",
    "num_compromised", "root_shell", "su_attempted", "num_root",
    "num_file_creations", "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count", "serror_rate",
    "srv_serror_rate", "rerror_rate", "srv_rerror_rate", "same_srv_rate",
    "diff_srv_rate", "srv_diff_host_rate", "dst_host_count",
    "dst_host_srv_count", "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate", "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label", "difficulty",
]

ATTACK_CATEGORIES = {
    "normal": "normal",
    # DoS
    "back": "DoS", "land": "DoS", "neptune": "DoS", "pod": "DoS",
    "smurf": "DoS", "teardrop": "DoS", "mailbomb": "DoS", "apache2": "DoS",
    "processtable": "DoS", "udpstorm": "DoS", "worm": "DoS",
    # Probe
    "ipsweep": "Probe", "nmap": "Probe", "portsweep": "Probe",
    "satan": "Probe", "mscan": "Probe", "saint": "Probe",
    # R2L
    "ftp_write": "R2L", "guess_passwd": "R2L", "imap": "R2L",
    "multihop": "R2L", "phf": "R2L", "spy": "R2L", "warezclient": "R2L",
    "warezmaster": "R2L", "sendmail": "R2L", "named": "R2L",
    "snmpgetattack": "R2L", "snmpguess": "R2L", "xlock": "R2L",
    "xsnoop": "R2L", "httptunnel": "R2L",
    # U2R
    "buffer_overflow": "U2R", "loadmodule": "U2R", "perl": "U2R",
    "rootkit": "U2R", "ps": "U2R", "sqlattack": "U2R", "xterm": "U2R",
}

CATEGORICAL = ["protocol_type", "service", "flag"]


def load_nsl_kdd(
    train_path: str | Path,
    test_path: str | Path | None = None,
    binary: bool = True,
) -> dict:
    """Charge NSL-KDD. Retourne X_train, y_train (+ X_test, y_test si fourni).

    binary=True : y = 0 (normal) / 1 (attaque). Sinon y = catégorie (str).
    Le one-hot est ajusté sur train+test réunis pour des colonnes stables.
    """
    train = pd.read_csv(train_path, header=None, names=NSL_KDD_COLUMNS)
    test = (
        pd.read_csv(test_path, header=None, names=NSL_KDD_COLUMNS)
        if test_path
        else None
    )

    frames = [train] + ([test] if test is not None else [])
    combined = pd.concat(frames, ignore_index=True)
    dummies = pd.get_dummies(combined[CATEGORICAL], dtype=np.float32)
    numeric = combined.drop(columns=CATEGORICAL + ["label", "difficulty"])
    X_all = np.hstack([numeric.to_numpy(np.float32), dummies.to_numpy()])

    labels = combined["label"].map(ATTACK_CATEGORIES).fillna("other")
    if binary:
        y_all = (labels != "normal").to_numpy(np.int64)
    else:
        y_all = labels.to_numpy()

    n_train = len(train)
    out = {
        "X_train": X_all[:n_train],
        "y_train": y_all[:n_train],
        "feature_names": list(numeric.columns) + list(dummies.columns),
    }
    if test is not None:
        out["X_test"] = X_all[n_train:]
        out["y_test"] = y_all[n_train:]
    return out
