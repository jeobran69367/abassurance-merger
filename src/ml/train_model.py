"""
Entraîne le modèle de **prédiction du risque client** à partir du dataset consolidé
(historique contrats/sinistres/paiements du data lake).

Pour la démonstration du repository, un dataset synthétique mais réaliste est généré
(cf. `_generate_synthetic_dataset`) : en production, ces features proviendraient de
`data/hdfs_sim/clients.parquet` enrichi par le job Spark (nombre de sinistres, montant total
réclamé, ancienneté du contrat, retards de paiement, etc.).

Le modèle est un RandomForestClassifier : bon compromis performance / interprétabilité
(feature_importances_) et robuste sur données tabulaires hétérogènes issues de deux
systèmes sources différents.
"""
from __future__ import annotations

import random
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

MODEL_DIR = Path(__file__).resolve().parent / "artifacts"
FEATURE_COLUMNS = [
    "anciennete_contrat_mois",
    "nb_sinistres_12m",
    "montant_total_sinistres",
    "nb_paiements_retard",
    "age_client",
    "prime_annuelle",
]


def _generate_synthetic_dataset(n: int = 5000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    anciennete = rng.integers(1, 240, n)
    nb_sinistres = rng.poisson(1.2, n)
    montant_sinistres = np.round(nb_sinistres * rng.gamma(2.0, 800, n), 2)
    nb_retards = rng.poisson(0.5, n)
    age = rng.integers(18, 85, n)
    prime = np.round(rng.normal(650, 200, n).clip(100, 3000), 2)

    # Risque = combinaison logique de sinistralité, retards de paiement et jeunesse du client,
    # + bruit aléatoire (aucun modèle n'est parfaitement déterministe).
    risk_score = (
        0.35 * (nb_sinistres / (nb_sinistres.max() + 1))
        + 0.25 * (montant_sinistres / (montant_sinistres.max() + 1))
        + 0.25 * (nb_retards / (nb_retards.max() + 1))
        + 0.15 * ((85 - age) / 67)
        + rng.normal(0, 0.08, n)
    )
    risque_client = (risk_score > np.quantile(risk_score, 0.7)).astype(int)

    return pd.DataFrame(
        {
            "anciennete_contrat_mois": anciennete,
            "nb_sinistres_12m": nb_sinistres,
            "montant_total_sinistres": montant_sinistres,
            "nb_paiements_retard": nb_retards,
            "age_client": age,
            "prime_annuelle": prime,
            "risque_client": risque_client,
        }
    )


def train() -> dict:
    df = _generate_synthetic_dataset()
    X = df[FEATURE_COLUMNS]
    y = df["risque_client"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200, max_depth=8, random_state=42, class_weight="balanced"
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    report = classification_report(y_test, y_pred, output_dict=True)
    auc = roc_auc_score(y_test, y_proba)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / "risk_model.joblib")

    return {"roc_auc": auc, "report": report, "n_train": len(X_train), "n_test": len(X_test)}


if __name__ == "__main__":
    metrics = train()
    print(f"Modèle entraîné. ROC AUC = {metrics['roc_auc']:.3f} "
          f"(train={metrics['n_train']}, test={metrics['n_test']})")
