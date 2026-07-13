"""
Authentification simple par JWT pour l'API de démonstration (2 rôles : admin / user).

En production, ces comptes seraient gérés par un IAM d'entreprise (Azure AD / Keycloak) et
non en dur dans le code — ceci est un mock volontairement minimal pour permettre à
l'évaluateur de tester l'application avec des identifiants de démonstration (cf. README).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

SECRET_KEY = os.environ.get("APP_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def _hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def _verify_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed)


# Comptes de démonstration (cf. README pour les identifiants en clair fournis à l'évaluateur).
# NB : utilise directement la librairie `bcrypt` (plutôt que passlib) pour éviter les problèmes
# de compatibilité entre versions récentes de passlib et bcrypt>=4.
_USERS_DB = {
    "admin": {"username": "admin", "role": "admin", "hashed_password": _hash_password("Admin@2026")},
    "user": {"username": "user", "role": "user", "hashed_password": _hash_password("User@2026")},
}


def authenticate_user(username: str, password: str) -> dict | None:
    user = _USERS_DB.get(username)
    if not user or not _verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None or username not in _USERS_DB:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return _USERS_DB[username]


def require_role(*roles: str):
    def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Accès refusé pour ce rôle")
        return current_user

    return checker
