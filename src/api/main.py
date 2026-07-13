"""
API de démonstration exposant le modèle de prédiction du risque client.

Lancer en local :  uvicorn src.api.main:app --reload
Documentation Swagger : http://127.0.0.1:8000/docs
Identifiants : voir README.md (admin/Admin@2026, user/User@2026)
"""
from __future__ import annotations

import joblib
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from src.auth.auth import authenticate_user, create_access_token, get_current_user, require_role
from src.ml.train_model import FEATURE_COLUMNS, MODEL_DIR

app = FastAPI(
    title="AbAssurance — API de prédiction du risque client",
    description="Fusion AbAssurance / AssurePlus — Bloc 3 IA",
    version="1.0.0",
)

_model = None


def get_model():
    global _model
    if _model is None:
        model_path = MODEL_DIR / "risk_model.joblib"
        if not model_path.exists():
            raise HTTPException(
                status_code=503,
                detail="Modèle non entraîné. Lancer `python -m src.ml.train_model` d'abord.",
            )
        _model = joblib.load(model_path)
    return _model


class ClientRiskFeatures(BaseModel):
    anciennete_contrat_mois: int = Field(..., ge=0, description="Ancienneté du contrat en mois")
    nb_sinistres_12m: int = Field(..., ge=0, description="Nombre de sinistres sur 12 mois")
    montant_total_sinistres: float = Field(..., ge=0)
    nb_paiements_retard: int = Field(..., ge=0)
    age_client: int = Field(..., ge=18, le=120)
    prime_annuelle: float = Field(..., ge=0)


class RiskPrediction(BaseModel):
    risque_eleve: bool
    probabilite_risque: float


@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Nom d'utilisateur ou mot de passe incorrect")
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict/risk-client", response_model=RiskPrediction)
def predict_risk(
    features: ClientRiskFeatures,
    current_user: dict = Depends(get_current_user),
    model=Depends(get_model),
):
    """Accessible à `admin` et `user` : consultation d'une prédiction (lecture)."""
    X = [[getattr(features, col) for col in FEATURE_COLUMNS]]
    proba = float(model.predict_proba(X)[0][1])
    return RiskPrediction(risque_eleve=proba > 0.5, probabilite_risque=round(proba, 4))


@app.get("/admin/model-info")
def model_info(current_user: dict = Depends(require_role("admin")), model=Depends(get_model)):
    """Réservé au rôle `admin` : informations internes sur le modèle déployé."""
    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist()))
    return {"n_estimators": model.n_estimators, "feature_importances": importances}
