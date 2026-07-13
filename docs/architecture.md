# Architecture cible

```
 ┌────────────────┐        ┌────────────────┐
 │ BDD AbAssurance │        │ BDD AssurePlus  │
 │   (Oracle)       │        │  (SQL Server)   │
 └────────┬────────┘        └────────┬────────┘
          │  extraction CDC/batch            │
          ▼                                   ▼
 ┌──────────────────────────────────────────────┐
 │   Talend (ETL) : mapping + data cleaning       │
 │   -> applique docs/MCD.md, produit des events  │
 └───────────────────────┬────────────────────────┘
                          ▼
                ┌─────────────────────┐
                │   Apache Kafka        │
                │  topics: clients,     │
                │  contrats, sinistres, │
                │  paiements            │
                └──────────┬───────────┘
                            ▼
                ┌─────────────────────────────┐
                │  Spark Structured Streaming   │
                │  (batch ici en simulation)      │
                │  -> consolidation, dédoublonnage │
                └──────────────┬───────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │   Hadoop / Data Lake     │
                    │  (simulation locale:      │
                    │   parquet partitionné)    │
                    └────────────┬──────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │  Nettoyage / Feature eng.   │
                    │  -> Dataset d'entraînement   │
                    └────────────┬──────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │   Modèle IA (scikit-learn)  │
                    │  Prédiction du risque client │
                    └────────────┬──────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │  API FastAPI (auth admin/user)│
                    │  POST /predict/risk-client      │
                    └───────────────────────────────┘
```

## Choix techniques et justification

| Brique | Outil | Justification |
|---|---|---|
| Ingestion des changements | Apache Kafka | Découple les deux bases sources de la couche de traitement, permet le temps réel et absorbe les pics de charge (exigé par le cahier des charges) |
| ETL / mapping | Talend | Outil low-code imposé par la direction technique, permet aux équipes non-dev de maintenir les mappings Oracle/SQL Server → modèle unifié |
| Stockage distribué | Hadoop (HDFS) | Stocke à moindre coût les historiques volumineux (contrats, sinistres sur plusieurs décennies) tout en restant compatible Spark |
| Traitement | Apache Spark | Traitement distribué du volume (centaines de To), dédoublonnage, agrégations, feature engineering pour le ML |
| Modèle IA | scikit-learn (RandomForest) | Modèle interprétable, robuste sur données tabulaires hétérogènes, rapide à ré-entraîner en continu |
| API de prédiction | FastAPI | Framework Python performant, typage fort (Pydantic), documentation Swagger générée automatiquement |

## Simulation locale (pour la démonstration / les tests du repository)

Faire tourner un vrai cluster Kafka/Hadoop/Spark n'est pas réaliste pour un dépôt de démonstration.
Le code du repository reproduit donc fidèlement les **contrats d'interface** de chaque brique :

- `src/ingestion/kafka_producer.py` / `kafka_consumer.py` utilisent `kafka-python` si un broker
  est disponible (variable d'env `KAFKA_BOOTSTRAP_SERVERS`), sinon basculent sur une file locale
  (`data/kafka_sim/*.jsonl`) — même interface, donc le code de production ne change pas.
- `src/spark/spark_job.py` utilise PySpark s'il est installé, sinon un fallback pandas strictement
  équivalent (même transformations, même schéma de sortie) écrit dans `data/hdfs_sim/` (parquet).
- `docker-compose.yml` (fourni) permet de lancer un vrai Kafka + Zookeeper en local pour aller plus
  loin que la simulation.
