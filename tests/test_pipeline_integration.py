import shutil

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


def test_kafka_bus_local_fallback_roundtrip():
    bus = KafkaBus()
    bus.publish("test.topic", {"foo": "bar"})
    messages = list(bus.consume("test.topic"))
    assert messages == [{"foo": "bar"}]
    # Le topic doit être vidé après consommation (comme un vrai groupe de consommateurs Kafka).
    assert list(bus.consume("test.topic")) == []
