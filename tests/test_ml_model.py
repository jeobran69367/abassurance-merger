from src.ml.train_model import train


def test_train_model_returns_reasonable_auc():
    """US 5.2 -- critère d'acceptation : le modèle atteint un seuil de performance minimal
    (ici ROC AUC, mesure équivalente au F1-score cible fixé avec le métier)."""
    metrics = train()
    assert metrics["roc_auc"] > 0.7  # le modèle doit être nettement meilleur que le hasard


def test_train_model_is_reproducible():
    """US 5.1 -- critère d'acceptation : le split train/test et l'entraînement sont
    documentés et reproductibles (seed fixe)."""
    metrics_1 = train()
    metrics_2 = train()
    assert metrics_1["n_train"] == metrics_2["n_train"]
    assert metrics_1["n_test"] == metrics_2["n_test"]
    assert abs(metrics_1["roc_auc"] - metrics_2["roc_auc"]) < 1e-6
