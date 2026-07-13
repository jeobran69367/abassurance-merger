import shutil

import pytest

from src.ingestion.kafka_bus import LOCAL_QUEUE_DIR, KafkaBus
from src.ingestion.kafka_producer import DATA_DIR, main as run_producer
from src.spark.spark_job import LAKE_DIR, run_consolidation


def setup_module(_module):
    # Repart d'un état propre pour ne pas dépendre d'une exécution précédente.
    shutil.rmtree(LOCAL_QUEUE_DIR, ignore_errors=True)
    shutil.rmtree(LAKE_DIR, ignore_errors=True)


def teardown_module(_module):
    shutil.rmtree(LOCAL_QUEUE_DIR, ignore_errors=True)
    shutil.rmtree(LAKE_DIR, ignore_errors=True)


def test_end_to_end_ingestion_and_consolidation():
    assert (DATA_DIR / "sample_ab_client.csv").exists()
    assert (DATA_DIR / "sample_ap_users.csv").exists()

    run_producer()
    result = run_consolidation()

    # 5 clients AbAssurance + 5 AssurePlus, dont 1 en quarantaine (téléphone invalide côté AP).
    assert result["clients_consolides"] == 9
    assert result["en_quarantaine"] == 1
    assert (LAKE_DIR / "clients.parquet").exists()


def test_messages_are_not_lost_when_consolidation_fails(monkeypatch):
    """Non-régression du bug corrigé : si l'écriture dans le data lake échoue après la
    lecture des topics, les messages ne doivent PAS être perdus (pas de commit avant succès)."""
    run_producer()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("panne simulée d'écriture dans le data lake")

    import pandas as pd

    original_to_parquet = pd.DataFrame.to_parquet
    monkeypatch.setattr(pd.DataFrame, "to_parquet", _boom, raising=False)

    bus = KafkaBus()
    assert len(bus.peek("clients.abassurance")) == 5  # messages présents avant l'échec

    with pytest.raises(RuntimeError):
        run_consolidation()

    # Les messages doivent toujours être là : aucun commit n'a eu lieu puisque l'écriture a échoué.
    assert len(bus.peek("clients.abassurance")) == 5
    assert len(bus.peek("clients.assureplus")) == 5

    # Un rejeu (une fois la panne résolue) doit ensuite fonctionner normalement.
    monkeypatch.setattr(pd.DataFrame, "to_parquet", original_to_parquet, raising=False)
    result = run_consolidation()
    assert result["clients_consolides"] == 9


def test_kafka_bus_local_fallback_roundtrip():
    bus = KafkaBus()
    bus.publish("test.topic", {"foo": "bar"})

    # peek() ne doit jamais vider la file tant qu'on n'a pas explicitement commit.
    assert bus.peek("test.topic") == [{"foo": "bar"}]
    assert bus.peek("test.topic") == [{"foo": "bar"}]

    bus.commit("test.topic")
    assert bus.peek("test.topic") == []
