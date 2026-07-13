"""Publie les enregistrements clients bruts des deux bases sources sur les topics Kafka.

En production, ce script est déclenché par un job Talend (CDC ou extraction batch planifiée) qui
lit directement les bases Oracle/SQL Server. Ici, pour la démonstration, il lit les échantillons
`data/sample_ab_client.csv` et `data/sample_ap_users.csv`.
"""
from __future__ import annotations

import csv
from pathlib import Path

from src.ingestion.kafka_bus import KafkaBus

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def publish_source_csv(bus: KafkaBus, csv_path: Path, topic: str) -> int:
    if not csv_path.exists():
        return 0
    count = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            bus.publish(topic, row)
            count += 1
    return count


def main() -> None:
    bus = KafkaBus()
    n_ab = publish_source_csv(bus, DATA_DIR / "sample_ab_client.csv", "clients.abassurance")
    n_ap = publish_source_csv(bus, DATA_DIR / "sample_ap_users.csv", "clients.assureplus")
    print(f"Publié {n_ab} clients AbAssurance et {n_ap} clients AssurePlus sur Kafka.")


if __name__ == "__main__":
    main()
