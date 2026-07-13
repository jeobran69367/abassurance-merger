"""
Framework de mapping et migration : transforme les enregistrements bruts issus de
AB_CLIENT (Oracle) et AP_USERS (SQL Server) vers l'entité unifiée CLIENT du docs/MCD.md.

Ce module fait le pont entre les jobs Talend (qui gèrent l'extraction/orchestration côté
infrastructure) et la logique métier de mapping, testable unitairement en Python — c'est le
"framework adapté" demandé au Dossier 2 - Question 2 : pandas pour la manipulation tabulaire,
des fonctions de mapping pures et testées pour la logique métier, orchestrées par Talend.
"""
from __future__ import annotations

import uuid
from typing import Any

from src.cleaning.data_cleaning import (
    DataQualityError,
    normalize_status,
    parse_flexible_date,
    split_full_name,
    validate_email,
    validate_phone,
)


def map_ab_client(row: dict[str, Any]) -> dict[str, Any]:
    """Mappe un enregistrement AB_CLIENT (Oracle) vers le modèle CLIENT unifié."""
    return {
        "client_id": str(uuid.uuid4()),
        "source_system": "ABASSURANCE",
        "source_id": str(row["AB_CLIENT_ID"]),
        "nom": row["AB_NOM"],
        "prenom": row["AB_PRENOM"],
        "date_naissance": parse_flexible_date(row.get("AB_DATE_NAISSANCE")),
        "email": validate_email(row.get("AB_EMAIL")),
        "telephone": validate_phone(row.get("AB_TELEPHONE")),
        "adresse": row.get("AB_ADRESSE"),
        "code_postal": row.get("AB_CODE_POSTAL"),
        "date_creation": row.get("AB_DATE_CREATION"),
        "statut_client": normalize_status(row.get("AB_STATUT_CLIENT")),
        "score_fidelite": None,
        "num_fiscal": row.get("AB_NUM_FISCAL"),
    }


def map_ap_user(row: dict[str, Any]) -> dict[str, Any]:
    """Mappe un enregistrement AP_USERS (SQL Server) vers le modèle CLIENT unifié."""
    nom, prenom = split_full_name(row["AP_FULL_NAME"])
    return {
        "client_id": str(uuid.uuid4()),
        "source_system": "ASSUREPLUS",
        "source_id": str(row["AP_USER_ID"]),
        "nom": nom,
        "prenom": prenom,
        "date_naissance": parse_flexible_date(row.get("AP_BIRTH_DATE")),
        "email": validate_email(row.get("AP_MAIL_ADDRESS")),
        "telephone": validate_phone(row.get("AP_PHONE_NUMBER")),
        "adresse": row.get("AP_STREET_ADDRESS"),
        "code_postal": row.get("AP_ZIP_CODE"),
        "date_creation": row.get("AP_CREATED_AT"),
        "statut_client": normalize_status(row.get("AP_CUSTOMER_STATUS")),
        "score_fidelite": row.get("AP_LOYALTY_SCORE"),
        "num_fiscal": None,
    }


def map_batch(rows: list[dict[str, Any]], mapper) -> tuple[list[dict], list[dict]]:
    """Applique un mapper sur un lot d'enregistrements, en isolant les lignes en erreur
    dans une file de quarantaine plutôt que d'interrompre tout le traitement (résilience
    exigée pour un volume de plusieurs centaines de téraoctets où l'erreur ponctuelle est
    la norme, pas l'exception)."""
    mapped: list[dict] = []
    quarantine: list[dict] = []
    for row in rows:
        try:
            mapped.append(mapper(row))
        except DataQualityError as exc:
            quarantine.append({"row": row, "error": str(exc)})
    return mapped, quarantine
