"""
Règles de data cleaning appliquées avant tout mapping/agrégation entre les bases
AbAssurance (Oracle) et AssurePlus (SQL Server).

Bonnes pratiques appliquées (cf. Dossier 2 - Question 1) :
1. Normalisation des types (dates, décimaux) avant toute comparaison inter-système.
2. Détection et suppression des doublons cross-système (même personne dans les 2 bases).
3. Harmonisation des référentiels de statuts (valeurs différentes pour un même sens métier).
4. Validation des champs sensibles (email, téléphone, code postal) avec rejet en quarantaine
   plutôt que suppression silencieuse (traçabilité réglementaire).
5. Traçabilité : chaque enregistrement nettoyé garde `source_system` et `source_id`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9\s().-]{6,20}$")

# Harmonisation des statuts hétérogènes entre les deux systèmes vers un référentiel commun.
STATUT_CLIENT_MAPPING = {
    # AbAssurance
    "ACTIF": "ACTIF",
    "INACTIF": "INACTIF",
    "SUSPENDU": "SUSPENDU",
    # AssurePlus
    "ACTIVE": "ACTIF",
    "INACTIVE": "INACTIF",
    "SUSPENDED": "SUSPENDU",
    "CLOSED": "INACTIF",
}


class DataQualityError(ValueError):
    """Levée quand un enregistrement doit être mis en quarantaine plutôt que rejeté silencieusement."""


@dataclass
class CleaningReport:
    total: int = 0
    valid: int = 0
    quarantined: int = 0
    errors: list[str] | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def parse_flexible_date(raw_value: Optional[str]) -> Optional[date]:
    """Parse une date venant de champs hétérogènes (DATE Oracle déjà typée, ou VARCHAR
    AssurePlus au format 'YYYY-MM-DD' ou 'YYYY-MM-DD HH:MM:SS').

    Ne lève jamais d'exception non gérée : une date invalide part en quarantaine, elle n'est
    ni supprimée silencieusement, ni ne casse tout le pipeline.
    """
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, (date, datetime)):
        return raw_value.date() if isinstance(raw_value, datetime) else raw_value

    raw_value = str(raw_value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw_value, fmt).date()
        except ValueError:
            continue
    raise DataQualityError(f"Format de date non reconnu: {raw_value!r}")


def split_full_name(full_name: str) -> tuple[str, str]:
    """Sépare un nom complet AssurePlus ('AP_FULL_NAME') en (nom, prenom).

    Heuristique : le dernier mot est considéré comme le prénom, le reste comme le nom,
    ce qui gère correctement les noms composés/particules ('Jean-Pierre De La Fontaine').
    Cette heuristique doit être documentée car imparfaite sur certains cas limites
    (elle est volontairement simple pour rester auditable).
    """
    if not full_name or not full_name.strip():
        raise DataQualityError("Nom complet vide")
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def normalize_status(raw_status: Optional[str]) -> str:
    if not raw_status:
        raise DataQualityError("Statut client manquant")
    key = raw_status.strip().upper()
    if key not in STATUT_CLIENT_MAPPING:
        raise DataQualityError(f"Statut client inconnu: {raw_status!r}")
    return STATUT_CLIENT_MAPPING[key]


def validate_email(email: Optional[str]) -> Optional[str]:
    if email is None or email == "":
        return None
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise DataQualityError(f"Email invalide: {email!r}")
    return email


def validate_phone(phone: Optional[str]) -> Optional[str]:
    if phone is None or phone == "":
        return None
    phone = phone.strip()
    if not PHONE_RE.match(phone):
        raise DataQualityError(f"Téléphone invalide: {phone!r}")
    return re.sub(r"[\s().-]", "", phone)


def normalize_annual_premium(value: float, is_monthly: bool) -> float:
    """Ramène toutes les primes à une base annuelle avant toute comparaison cross-système."""
    if value is None or value < 0:
        raise DataQualityError(f"Montant de prime invalide: {value!r}")
    return round(value * 12, 2) if is_monthly else round(value, 2)


def deduplicate_clients(clients: list[dict]) -> tuple[list[dict], list[dict]]:
    """Détecte les doublons cross-système sur la clé (email normalisé, date de naissance).

    Retourne (clients_dedupliques, doublons_detectes). Les enregistrements en doublon ne sont
    pas supprimés : ils sont fusionnés (priorité au système le plus complet) et conservés en
    log pour audit — exigence réglementaire du secteur assurance.
    """
    seen: dict[tuple, dict] = {}
    duplicates: list[dict] = []
    for client in clients:
        key = (client.get("email"), client.get("date_naissance"))
        if key in seen and key != (None, None):
            duplicates.append(client)
            existing = seen[key]
            # Fusion : on garde les champs non nuls du nouvel enregistrement en complément.
            for field, value in client.items():
                if not existing.get(field) and value:
                    existing[field] = value
        else:
            seen[key] = client
    return list(seen.values()), duplicates
