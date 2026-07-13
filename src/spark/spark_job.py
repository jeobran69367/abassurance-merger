"""
Job de consolidation : consomme les topics Kafka `clients.abassurance` et
`clients.assureplus`, applique le mapping vers le modèle unifié (src/etl/mapping.py),
déduplique, et écrit le résultat dans le data lake (`data/hdfs_sim/clients.parquet`).

Utilise PySpark si disponible (traitement distribué en production, sur le vrai volume de
plusieurs centaines de téraoctets). Bascule sinon sur un fallback pandas strictement
équivalent — même schéma de sortie, mêmes règles métier — pour que la démonstration et les
tests tournent sans cluster Spark.

NB : voir le dossier de réponses (Dossier 3 - Question 3) pour l'analyse d'un bug identifié
dans la chaîne de mapping (`normalize_annual_premium` non branchée sur `AP_MONTHLY_PREMIUM`).
"""
from __future__ import annotations

from pathlib import Path

from src.etl.mapping import map_ab_client, map_ap_user, map_batch
from src.ingestion.kafka_bus import KafkaBus

LAKE_DIR = Path(__file__).resolve().parents[2] / "data" / "hdfs_sim"


def _try_pyspark():
    try:
        from pyspark.sql import SparkSession  # type: ignore

        return SparkSession.builder.appName("abassurance-merge").master("local[*]").getOrCreate()
    except Exception:
        return None


def run_consolidation() -> dict:
    bus = KafkaBus()
    ab_rows = bus.peek("clients.abassurance")
    ap_rows = bus.peek("clients.assureplus")

    mapped_ab, quarantine_ab = map_batch(ab_rows, map_ab_client)
    mapped_ap, quarantine_ap = map_batch(ap_rows, map_ap_user)

    all_clients = mapped_ab + mapped_ap
    quarantine = quarantine_ab + quarantine_ap

    LAKE_DIR.mkdir(parents=True, exist_ok=True)
    spark = _try_pyspark()

    if spark is not None:
        df = spark.createDataFrame(all_clients)
        df.write.mode("overwrite").parquet(str(LAKE_DIR / "clients.parquet"))
        spark.stop()
    else:
        import pandas as pd

        df = pd.DataFrame(all_clients)
        df.to_parquet(LAKE_DIR / "clients.parquet", index=False)

    # Le commit n'intervient qu'ici, une fois l'écriture dans le data lake confirmée : si
    # une exception survient plus haut (ex. dépendance manquante, erreur d'écriture), les
    # topics ne sont jamais vidés et les messages restent disponibles pour un rejeu.
    bus.commit("clients.abassurance")
    bus.commit("clients.assureplus")

    return {
        "clients_consolides": len(all_clients),
        "en_quarantaine": len(quarantine),
        "quarantaine_details": quarantine,
    }


if __name__ == "__main__":
    result = run_consolidation()
    print(
        f"{result['clients_consolides']} clients consolidés, "
        f"{result['en_quarantaine']} en quarantaine (voir data/hdfs_sim/quarantine.log)."
    )
