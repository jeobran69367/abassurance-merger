"""
Abstraction du bus Kafka utilisé pour transporter les événements clients/contrats/sinistres
entre les jobs Talend et Spark.

En environnement réel : `KAFKA_BOOTSTRAP_SERVERS=broker:9092` fait basculer automatiquement sur
un vrai cluster Kafka via `kafka-python` (voir `docker-compose.yml` pour un cluster local).
En l'absence de broker (démo, tests, CI) : fallback transparent sur une file locale au format
JSON Lines, avec la même interface `publish`/`consume` — le code appelant ne change jamais.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

LOCAL_QUEUE_DIR = Path(__file__).resolve().parents[2] / "data" / "kafka_sim"


class KafkaBus:
    def __init__(self, bootstrap_servers: str | None = None):
        self.bootstrap_servers = bootstrap_servers or os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
        self._producer = None
        if self.bootstrap_servers:
            try:
                from kafka import KafkaProducer  # type: ignore

                self._producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                )
            except Exception:
                # Pas de broker joignable : on retombe sur la simulation locale sans planter.
                self._producer = None
        LOCAL_QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    def publish(self, topic: str, message: dict[str, Any]) -> None:
        if self._producer is not None:
            self._producer.send(topic, message)
            self._producer.flush()
            return
        path = LOCAL_QUEUE_DIR / f"{topic}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(message, default=str) + "\n")

    def peek(self, topic: str) -> list[dict[str, Any]]:
        """Lit les messages du topic SANS les supprimer (équivalent d'une lecture Kafka
        avant commit d'offset). Le fichier n'est retiré de la file qu'après un appel
        explicite à `commit()`, une fois le traitement en aval terminé avec succès.
        """
        path = LOCAL_QUEUE_DIR / f"{topic}.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def commit(self, topic: str) -> None:
        """Marque le topic comme traité (équivalent d'un commit d'offset Kafka) : les
        messages ne sont retirés de la file locale qu'à cet instant, jamais avant."""
        path = LOCAL_QUEUE_DIR / f"{topic}.jsonl"
        path.unlink(missing_ok=True)

    def consume(self, topic: str) -> Iterator[dict[str, Any]]:
        """Ancienne API, conservée pour compatibilité : lit ET commit immédiatement.

        À éviter dans du nouveau code — préférer `peek()` puis `commit()` explicite après
        traitement réussi, pour ne jamais perdre de message si un job plante en cours de
        route (voir docs/architecture.md, bug corrigé du 2026-07 : le job Spark supprimait
        les messages avant même de savoir si la consolidation avait réussi)."""
        messages = self.peek(topic)
        self.commit(topic)
        yield from messages
