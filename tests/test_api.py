from fastapi.testclient import TestClient

from src.api.main import app
from src.ml.train_model import MODEL_DIR, train

client = TestClient(app)


def _get_token(username: str, password: str) -> str:
    response = client.post("/token", data={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_endpoint():
    assert client.get("/health").json() == {"status": "ok"}


def test_frontend_served_at_root():
    """US 6.2 -- la petite application web de démo doit être servie à la racine,
    séparément de la documentation Swagger (/docs)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AbAssurance" in response.text


def test_static_assets_are_served():
    css_response = client.get("/static/style.css")
    js_response = client.get("/static/app.js")
    assert css_response.status_code == 200
    assert js_response.status_code == 200


def test_startup_trains_model_automatically_if_missing():
    """Nécessaire pour les déploiements à disque éphémère (Render, Railway) : si l'artefact
    n'existe pas au démarrage du serveur, l'API doit s'auto-entraîner plutôt que de planter."""
    model_path = MODEL_DIR / "risk_model.joblib"
    model_path.unlink(missing_ok=True)
    assert not model_path.exists()

    with TestClient(app):  # déclenche l'event "startup"
        pass

    assert model_path.exists()


def test_login_rejects_wrong_password():
    response = client.post("/token", data={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_predict_requires_authentication():
    """US 5.3 -- l'API ne doit exposer aucune prédiction sans authentification."""
    payload = {
        "anciennete_contrat_mois": 24,
        "nb_sinistres_12m": 1,
        "montant_total_sinistres": 500,
        "nb_paiements_retard": 0,
        "age_client": 35,
        "prime_annuelle": 600,
    }
    response = client.post("/predict/risk-client", json=payload)
    assert response.status_code == 401


def test_predict_with_valid_user_token():
    """US 5.3 -- critère d'acceptation : l'API expose la prédiction du modèle,
    documentée (OpenAPI/Swagger généré automatiquement par FastAPI sur /docs)."""
    train()  # s'assure que le modèle est bien présent pour ce test isolé
    token = _get_token("user", "User@2026")
    payload = {
        "anciennete_contrat_mois": 3,
        "nb_sinistres_12m": 5,
        "montant_total_sinistres": 8000,
        "nb_paiements_retard": 4,
        "age_client": 22,
        "prime_annuelle": 400,
    }
    response = client.post(
        "/predict/risk-client", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "risque_eleve" in body
    assert 0.0 <= body["probabilite_risque"] <= 1.0


def test_admin_only_endpoint_rejects_simple_user():
    """EPIC 4 / RBAC -- un utilisateur simple ne doit pas accéder aux informations
    internes du modèle réservées à l'administrateur."""
    user_token = _get_token("user", "User@2026")
    response = client.get(
        "/admin/model-info", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403


def test_admin_only_endpoint_allows_admin():
    admin_token = _get_token("admin", "Admin@2026")
    response = client.get(
        "/admin/model-info", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert "feature_importances" in response.json()
